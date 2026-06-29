import os
import sys
import sqlite3
import random
import time
from datetime import datetime, timedelta

# Dynamically resolve DB path using the same logic as edge_db.py
DB_PATH = "/home/jetson/smartelectric/edge/backend/edge_iot.db"
db_dir = os.path.dirname(DB_PATH)
if db_dir and not os.path.exists(db_dir):
    # relative path on Windows fallback
    DB_PATH = "D:\\home\\jetson\\smartelectric\\edge\\backend\\edge_iot.db"
    if not os.path.exists(DB_PATH):
        DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "edge_iot.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def main():
    print(f"Starting SmartElectric Real-time Simulator...")
    print(f"Targeting database: {DB_PATH}")
    
    voltage = 230.0
    appliances = ["Light", "TV", "Fridge", "Fan"]

    while True:
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get current states of appliances from the database (so we respect user toggles!)
            cursor.execute("SELECT name, status FROM appliances")
            states = {row["name"]: row["status"] for row in cursor.fetchall()}

            current_time = datetime.now()
            timestamp_str = current_time.strftime('%Y-%m-%d %H:%M:%S')

            # 1. Generate and insert DHT sensor reading
            temp = 26.0 + random.uniform(-1.0, 1.0)
            hum = 62.0 + random.uniform(-4.0, 4.0)
            cursor.execute("""
                INSERT INTO dht_data (temperature, humidity, timestamp, synced)
                VALUES (?, ?, ?, 0)
            """, (temp, hum, timestamp_str))

            # 2. Generate and insert sensor data for each appliance
            for app in appliances:
                status = states.get(app, 0)
                if status == 1:
                    # Generate realistic active loads
                    if app == "Light":
                        current = random.uniform(0.12, 0.18)
                    elif app == "TV":
                        current = random.uniform(0.35, 0.52)
                    elif app == "Fridge":
                        current = random.uniform(0.70, 1.10)
                    elif app == "Fan":
                        current = random.uniform(0.22, 0.30)
                else:
                    # Leakage or zero load
                    current = random.uniform(0.0, 0.01)

                power = current * voltage
                cursor.execute("""
                    INSERT INTO sensor_data (appliance_name, current, power, voltage, timestamp, synced)
                    VALUES (?, ?, ?, ?, ?, 0)
                """, (app, current, power, voltage, timestamp_str))

            # 3. Keep database lightweight by removing logs/readings older than 24 hours
            cutoff_time = (current_time - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("DELETE FROM sensor_data WHERE timestamp < ?", (cutoff_time,))
            cursor.execute("DELETE FROM dht_data WHERE timestamp < ?", (cutoff_time,))

            conn.commit()
            conn.close()

            print(f"[{timestamp_str}] Inserted real-time telemetry (Temp: {temp:.1f}°C, Hum: {hum:.1f}%)")

        except Exception as e:
            print(f"Error in simulator: {e}", file=sys.stderr)

        # Sleep for 5 seconds before next update
        time.sleep(5)

if __name__ == "__main__":
    main()
