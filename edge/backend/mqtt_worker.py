import json
import os
import sys
import sqlite3
from datetime import datetime
from paho.mqtt import client as mqtt

# Import DB configurations
from edge_db import get_db_connection, DB_PATH

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_KEEPALIVE = 60

# Define MQTT subscription topics
TOPIC_CURRENT = "smartelectric/sensors/current"
TOPIC_DHT = "smartelectric/sensors/dht"
TOPIC_LOGS = "smartelectric/logs"

# List of known appliances for validation
VALID_APPLIANCES = {"Light", "TV", "Fridge", "Fan"}

def log_system_event(level, message):
    """Logs system events directly to the SQLite system_logs table."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO system_logs (level, message) VALUES (?, ?)",
            (level, message)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[{datetime.now()}] ERROR: Failed to write system log to DB: {e}", file=sys.stderr)

# Define callbacks using Paho-MQTT v2.x Callback API syntax
def on_connect(client, userdata, flags, reason_code, properties=None):
    """Callback triggered upon establishing connection to Mosquitto broker."""
    # In paho-mqtt v2.x, reason_code is an object or int indicating connection success
    if isinstance(reason_code, int):
        rc = reason_code
    else:
        rc = reason_code.value

    if rc == 0:
        print(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT} successfully.")
        log_system_event("INFO", "Connected to MQTT broker.")
        
        # Subscribe to topics
        client.subscribe(TOPIC_CURRENT)
        client.subscribe(TOPIC_DHT)
        client.subscribe(TOPIC_LOGS)
        print(f"Subscribed to topics:\n - {TOPIC_CURRENT}\n - {TOPIC_DHT}\n - {TOPIC_LOGS}")
    else:
        print(f"Failed to connect to MQTT broker. Reason code: {rc}")
        log_system_event("ERROR", f"Failed to connect to MQTT broker. Reason code: {rc}")

def on_message(client, userdata, msg):
    """Callback triggered when a message is published to a subscribed topic."""
    payload_str = msg.payload.decode('utf-8', errors='ignore')
    topic = msg.topic

    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError as e:
        err_msg = f"Failed to parse JSON payload on {topic}: {payload_str}. Error: {e}"
        print(err_msg, file=sys.stderr)
        log_system_event("WARNING", err_msg)
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if topic == TOPIC_CURRENT:
            # Expected payload format:
            # {"Light": 0.15, "TV": 0.40, "Fridge": 1.10, "Fan": 0.25, "voltage": 230.0}
            voltage = float(payload.get("voltage", 230.0))
            
            for appliance, current_val in payload.items():
                if appliance in VALID_APPLIANCES:
                    current = float(current_val)
                    power = current * voltage
                    
                    cursor.execute("""
                        INSERT INTO sensor_data (appliance_name, current, power, voltage, synced)
                        VALUES (?, ?, ?, ?, 0)
                    """, (appliance, current, power, voltage))
            
            conn.commit()

        elif topic == TOPIC_DHT:
            # Expected payload format:
            # {"temperature": 27.5, "humidity": 65.2}
            temp = float(payload.get("temperature", 0.0))
            hum = float(payload.get("humidity", 0.0))
            
            cursor.execute("""
                INSERT INTO dht_data (temperature, humidity, synced)
                VALUES (?, ?, 0)
            """, (temp, hum))
            conn.commit()

        elif topic == TOPIC_LOGS:
            # Expected payload format:
            # {"level": "INFO", "message": "ESP32 status check"}
            level = payload.get("level", "INFO").upper()
            message = payload.get("message", "")
            
            cursor.execute("""
                INSERT INTO system_logs (level, message)
                VALUES (?, ?)
            """, (level, f"ESP32: {message}"))
            conn.commit()

        conn.close()

    except Exception as e:
        err_msg = f"Database insertion error processing topic {topic}: {e}"
        print(err_msg, file=sys.stderr)
        log_system_event("ERROR", err_msg)

def on_disconnect(client, userdata, flags, reason_code, properties=None):
    """Callback triggered when client disconnects from the broker."""
    print(f"Disconnected from MQTT broker. Reason: {reason_code}")
    log_system_event("WARNING", f"Disconnected from MQTT broker. Reason: {reason_code}")

def main():
    print("Starting SmartElectric MQTT Background Worker...")
    
    # Initialize Paho-MQTT Client with Callback API Version 2 (Explicit requirement)
    try:
        # Check if CallbackAPIVersion exists in paho.mqtt (v2.x check)
        if hasattr(mqtt, "CallbackAPIVersion"):
            client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        else:
            # Fallback to v1.x initialization if run in an environment with paho-mqtt < 2.0
            print("paho-mqtt version is < 2.0. Initializing client in legacy mode.")
            client = mqtt.Client()
    except Exception as e:
        print(f"Error initializing MQTT Client: {e}", file=sys.stderr)
        sys.exit(1)

    # Set callback functions
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    # Connect to the broker
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
    except Exception as e:
        err_msg = f"Could not connect to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}. Error: {e}"
        print(err_msg, file=sys.stderr)
        log_system_event("ERROR", err_msg)
        # We don't exit; client.loop_forever() handles auto-reconnections

    # Enter blocking network loop (auto-reconnects automatically)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nMQTT Worker stopped by user.")
        log_system_event("INFO", "MQTT Worker stopped by user manual interrupt.")
    except Exception as e:
        log_system_event("CRITICAL", f"MQTT Worker crashed: {e}")
        raise

if __name__ == "__main__":
    main()
