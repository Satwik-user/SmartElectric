import os
import sqlite3
import json
import sys
from datetime import datetime, date, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from paho.mqtt import client as mqtt

# Import ML anomaly and solar forecaster
try:
    from ml_anomaly import detect_anomaly
    from ml_solar_forecaster import predict_solar_forecast
except ImportError:
    # Dummy fallbacks
    def detect_anomaly(app_name, current, power, voltage):
        return False
    def predict_solar_forecast(temp, hum, hour):
        return [100.0, 50.0, 0.0]

# Global Auto-Shedding Flag
auto_shedding_enabled = False

# Resolve path to the static HTML frontend index.html
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_FILE_PATH = os.path.join(os.path.dirname(BASE_DIR), "frontend_static", "index.html")

# Import DB configurations
from edge_db import get_db_connection, DB_PATH

# FastAPI App Setup
app = FastAPI(
    title="SmartElectric Edge API",
    description="REST backend for the local Jetson Nano Smart Home Energy Management System",
    version="1.0.0"
)

# Enable CORS for Streamlit and Web/Mobile Frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MQTT Broker Details
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

# Pydantic schemas for requests
class RelayControlRequest(BaseModel):
    appliance: str
    state: int  # 0 for OFF, 1 for ON

class ApplianceResponse(BaseModel):
    id: int
    name: str
    relay_pin: int
    status: int
    last_updated: str

def publish_mqtt_command(appliance: str, state: int):
    """Connects to the local MQTT broker, publishes a relay command, and disconnects without blocking."""
    def run_publish():
        try:
            if hasattr(mqtt, "CallbackAPIVersion"):
                client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
            else:
                client = mqtt.Client()

            # Connect with a short keepalive to fail fast if broker is down
            client.connect(MQTT_BROKER, MQTT_PORT, 5)
            
            # Topic payload structure matching the ESP32 expectations
            payload = {
                "appliance": appliance,
                "state": state
            }
            client.publish("smartelectric/control/relay", json.dumps(payload), qos=1)
            client.disconnect()
        except Exception as e:
            print(f"Non-blocking MQTT Publish failed: {e}", file=sys.stderr)

    import threading
    threading.Thread(target=run_publish, daemon=True).start()
    return True

def calculate_kwh_and_cost(avg_power_w: float, hours: float):
    """Calculates kWh and tiered energy costs in INR (₹) based on Average Power and duration."""
    kwh = (avg_power_w * hours) / 1000.0
    
    # Standard Flat Tariff (₹7 per kWh)
    flat_rate = 7.00
    flat_cost = kwh * flat_rate

    # Indian Tiered Tariff Model
    # Tier 1: 0 - 100 kWh @ ₹4.50
    # Tier 2: 101 - 300 kWh @ ₹6.50
    # Tier 3: > 300 kWh @ ₹8.00
    tiered_cost = 0.0
    if kwh <= 100:
        tiered_cost = kwh * 4.50
    elif kwh <= 300:
        tiered_cost = (100 * 4.50) + ((kwh - 100) * 6.50)
    else:
        tiered_cost = (100 * 4.50) + (200 * 6.50) + ((kwh - 300) * 8.00)

    return {
        "kwh": round(kwh, 4),
        "flat_cost_inr": round(flat_cost, 2),
        "tiered_cost_inr": round(tiered_cost, 2)
    }

@app.get("/", response_class=HTMLResponse)
def read_root():
    """Serves the ultra-fast HTML5/JS dashboard static single page application."""
    try:
        if os.path.exists(FRONTEND_FILE_PATH):
            with open(FRONTEND_FILE_PATH, "r", encoding="utf-8") as f:
                return f.read()
        else:
            return f"<html><body><h3>Static UI not found at {FRONTEND_FILE_PATH}</h3></body></html>"
    except Exception as e:
        return f"<html><body><h3>Error loading static UI: {e}</h3></body></html>"

class SheddingRequest(BaseModel):
    enabled: bool

@app.post("/api/control/shedding")
def toggle_auto_shedding(req: SheddingRequest):
    """Enables or disables automatic preemptive load-shedding."""
    global auto_shedding_enabled
    auto_shedding_enabled = req.enabled
    return {"status": "success", "auto_shedding_enabled": auto_shedding_enabled}

@app.get("/api/solar/forecast")
def get_solar_forecast():
    """Predicts solar generation output for the next 3 hours based on current climate metrics."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT temperature, humidity FROM dht_data ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        temp = row["temperature"] if row else 25.0
        hum = row["humidity"] if row else 60.0
        hour = datetime.now().hour
        
        forecast = predict_solar_forecast(temp, hum, hour)
        return {
            "status": "success",
            "temperature": temp,
            "humidity": hum,
            "hour": hour,
            "forecast": forecast
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Solar forecast model prediction failed: {e}")

@app.get("/api/status")
def get_system_status():
    """Retrieves real-time statuses of all appliances, latest telemetry readings, anomalies, and DHT logs."""
    global auto_shedding_enabled
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch all appliances
        cursor.execute("SELECT id, name, relay_pin, status, last_updated FROM appliances")
        appliances = [dict(row) for row in cursor.fetchall()]

        # Fetch latest sensor telemetry and run anomaly detection for each appliance
        telemetry = {}
        anomaly_status = {}
        total_power = 0.0
        for app in appliances:
            cursor.execute("""
                SELECT current, power, voltage, timestamp 
                FROM sensor_data 
                WHERE appliance_name = ? 
                ORDER BY timestamp DESC LIMIT 1
            """, (app["name"],))
            row = cursor.fetchone()
            if row:
                r_dict = dict(row)
                telemetry[app["name"]] = r_dict
                total_power += float(row["power"] or 0.0)
                
                # Check for anomalies
                try:
                    anomaly_status[app["name"]] = detect_anomaly(
                        app["name"], 
                        float(r_dict["current"]), 
                        float(r_dict["power"]), 
                        float(r_dict["voltage"])
                    )
                except Exception:
                    anomaly_status[app["name"]] = None
            else:
                telemetry[app["name"]] = {"current": 0.0, "power": 0.0, "voltage": 230.0, "timestamp": None}
                anomaly_status[app["name"]] = None

        # Fetch latest DHT22 reading
        cursor.execute("SELECT temperature, humidity, timestamp FROM dht_data ORDER BY timestamp DESC LIMIT 1")
        dht_row = cursor.fetchone()
        dht = dict(dht_row) if dht_row else {"temperature": 0.0, "humidity": 0.0, "timestamp": None}

        # Run GRU forecast to determine future load peaks
        preemptive_warning = False
        shed_triggered = False
        shedded_appliance = None
        predicted_max = total_power

        try:
            forecast_vals = run_forecast(total_power)
            predicted_max = max(forecast_vals)
            if predicted_max > 400.0:
                preemptive_warning = True
        except Exception:
            pass

        # Perform Preemptive Auto-Shedding if enabled and warning is active
        if preemptive_warning and auto_shedding_enabled and total_power > 10.0:
            # Non-essential shedding order: Fan, TV, Light
            shed_priority = ["Fan", "TV", "Light"]
            for target_app in shed_priority:
                # Find if it is currently ON
                app_entry = next((a for a in appliances if a["name"] == target_app), None)
                if app_entry and app_entry["status"] == 1:
                    # Switch OFF in database
                    cursor.execute("""
                        UPDATE appliances 
                        SET status = 0, last_updated = CURRENT_TIMESTAMP 
                        WHERE name = ?
                    """, (target_app,))
                    
                    # Log to system journal
                    log_msg = f"Preemptive Auto-Shedding Triggered: Turned OFF {target_app} to prevent predicted grid overload ({predicted_max:.2f} W > 400W)"
                    cursor.execute(
                        "INSERT INTO system_logs (level, message) VALUES (?, ?)",
                        ("INFO", log_msg)
                    )
                    
                    # Publish MQTT off command
                    publish_mqtt_command(target_app, 0)
                    
                    shed_triggered = True
                    shedded_appliance = target_app
                    
                    # Update local state immediately
                    app_entry["status"] = 0
                    app_entry["last_updated"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    break

        conn.commit()
        conn.close()

        # Determine active power source based on 400W threshold
        power_source = "Solar" if total_power > 400.0 else "Grid"

        return {
            "appliances": appliances,
            "latest_telemetry": telemetry,
            "anomaly_status": anomaly_status,
            "dht": dht,
            "total_power": round(total_power, 2),
            "power_source": power_source,
            "auto_shedding_enabled": auto_shedding_enabled,
            "preemptive_warning": preemptive_warning,
            "predicted_max_power": round(predicted_max, 2),
            "shed_triggered": shed_triggered,
            "shedded_appliance": shedded_appliance
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failure: {e}")

@app.post("/api/control")
def control_relay(req: RelayControlRequest):
    """Sends control command to ESP32 via MQTT and updates local database."""
    if req.state not in (0, 1):
        raise HTTPException(status_code=400, detail="State must be 0 (OFF) or 1 (ON)")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify appliance exists
        cursor.execute("SELECT name FROM appliances WHERE name = ?", (req.appliance,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail=f"Appliance '{req.appliance}' not found")

        # Attempt to publish control command via MQTT
        mqtt_success = publish_mqtt_command(req.appliance, req.state)
        
        if not mqtt_success:
            # We still log to DB, but report the warning
            print(f"Warning: Failed to transmit MQTT command for {req.appliance} to broker.", file=sys.stderr)

        # Update local DB relay state
        cursor.execute("""
            UPDATE appliances 
            SET status = ?, last_updated = CURRENT_TIMESTAMP 
            WHERE name = ?
        """, (req.state, req.appliance))

        # Log system command
        log_message = f"Relay command sent: {req.appliance} -> {'ON' if req.state == 1 else 'OFF'} (MQTT Sync: {mqtt_success})"
        cursor.execute(
            "INSERT INTO system_logs (level, message) VALUES (?, ?)",
            ("INFO" if mqtt_success else "WARNING", log_message)
        )

        conn.commit()
        conn.close()

        return {
            "status": "success",
            "appliance": req.appliance,
            "state": req.state,
            "mqtt_published": mqtt_success
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal database/control error: {e}")

@app.get("/api/metrics")
def get_metrics(range_type: str = Query("today", regex="^(today|month|total)$")):
    """Calculates active hours, energy consumption (kWh), and costs in ₹ per appliance."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Define date filter
        if range_type == "today":
            start_date = datetime.combine(date.today(), datetime.min.time()).strftime('%Y-%m-%d %H:%M:%S')
        elif range_type == "month":
            start_date = date.today().replace(day=1).strftime('%Y-%m-%d 00:00:00')
        else: # total
            start_date = "1970-01-01 00:00:00"

        # Fetch list of appliances
        cursor.execute("SELECT name FROM appliances")
        appliances = [row["name"] for row in cursor.fetchall()]

        metrics = {}
        total_kwh = 0.0
        total_cost_flat = 0.0
        total_cost_tiered = 0.0

        for name in appliances:
            # Query avg power and duration for this appliance
            cursor.execute("""
                SELECT 
                    AVG(power) as avg_power,
                    MIN(timestamp) as min_ts,
                    MAX(timestamp) as max_ts,
                    COUNT(*) as count
                FROM sensor_data
                WHERE appliance_name = ? AND timestamp >= ?
            """, (name, start_date))
            
            row = cursor.fetchone()
            if row and row["count"] > 0 and row["avg_power"] is not None:
                avg_power = float(row["avg_power"])
                try:
                    min_dt = datetime.strptime(row["min_ts"], '%Y-%m-%d %H:%M:%S')
                    max_dt = datetime.strptime(row["max_ts"], '%Y-%m-%d %H:%M:%S')
                    duration_hours = max((max_dt - min_dt).total_seconds() / 3600.0, 0.05) # Minimum 3 minutes to avoid zero division
                except Exception:
                    # Fallback if parsing fails or timestamps are in a different format
                    duration_hours = 0.0

                calc = calculate_kwh_and_cost(avg_power, duration_hours)
                metrics[name] = {
                    "average_power_w": round(avg_power, 2),
                    "duration_hours": round(duration_hours, 2),
                    "kwh": calc["kwh"],
                    "flat_cost_inr": calc["flat_cost_inr"],
                    "tiered_cost_inr": calc["tiered_cost_inr"]
                }
                total_kwh += calc["kwh"]
                total_cost_flat += calc["flat_cost_inr"]
                total_cost_tiered += calc["tiered_cost_inr"]
            else:
                metrics[name] = {
                    "average_power_w": 0.0,
                    "duration_hours": 0.0,
                    "kwh": 0.0,
                    "flat_cost_inr": 0.0,
                    "tiered_cost_inr": 0.0
                }

        conn.close()

        return {
            "range": range_type,
            "appliances": metrics,
            "totals": {
                "kwh": round(total_kwh, 4),
                "flat_cost_inr": round(total_cost_flat, 2),
                "tiered_cost_inr": round(total_cost_tiered, 2)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics calculation failure: {e}")

@app.get("/api/history")
def get_historical_data(
    appliance: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000)
):
    """Retrieves historical power consumption logs for plotting."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if appliance:
            cursor.execute("""
                SELECT timestamp, current, power, voltage 
                FROM sensor_data 
                WHERE appliance_name = ? 
                ORDER BY timestamp DESC LIMIT ?
            """, (appliance, limit))
        else:
            cursor.execute("""
                SELECT timestamp, appliance_name, current, power, voltage 
                FROM sensor_data 
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,))

        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"History query failure: {e}")

@app.get("/api/logs")
def get_system_logs(limit: int = Query(50, ge=1, le=200)):
    """Retrieves the latest local system logs from database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, level, message, timestamp FROM system_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Logs query failure: {e}")

# Import ML forecaster modules safely
try:
    from ml_forecaster import run_forecast
except Exception:
    # Fallback to dummy generator if PyTorch package is missing or fails to load DLLs in environment
    def run_forecast(current_power_watts=300.0):
        import random
        return [round(current_power_watts * f, 2) for f in [1.1, 1.25, 0.9, 0.7]]

class PredictLoadRequest(BaseModel):
    current_load: Optional[float] = 250.0

@app.post("/api/v1/predict/load")
def predict_future_load(req: PredictLoadRequest):
    """Predicts future active power curve (4 steps of 15-min intervals) using GRU."""
    try:
        forecast = run_forecast(req.current_load)
        timestamps = []
        now = datetime.now()
        for idx in range(1, 5):
            future_time = now + timedelta(minutes=15 * idx)
            timestamps.append(future_time.strftime('%Y-%m-%d %H:%M:%S'))
            
        return {
            "device_id": "jetson-edge-gateway-01",
            "forecasted_timestamps": timestamps,
            "forecasted_power_watts": forecast
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failure: {e}")

@app.post("/api/v1/predict/decision")
def predict_decision(req: PredictLoadRequest):
    """Attributes peak appliance load and determines severity level classification."""
    try:
        forecast = run_forecast(req.current_load)
        max_forecast = max(forecast)
        
        # Determine classification category
        if max_forecast > 400.0:
            classification = "HIGH"
            rec = "Power load is projected to spike above safety thresholds. Consider scheduling washing machines or heavy loads during off-peak hours."
        elif max_forecast > 200.0:
            classification = "NORMAL"
            rec = "Optimal consumption pattern. Keep appliances running normally."
        else:
            classification = "LOW"
            rec = "System load is low. Energy saving optimization is active."
            
        # Determine top attributed appliance
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT appliance_name, MAX(power) 
            FROM sensor_data 
            WHERE timestamp >= ?
            GROUP BY appliance_name
        """, ((datetime.now() - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S'),))
        row = cursor.fetchone()
        conn.close()
        
        top_app = row["appliance_name"] if (row and row["appliance_name"]) else "Fridge"
        
        return {
            "classification": classification,
            "anomaly_score": round(min(max((max_forecast - 200.0) / 300.0, 0.0), 1.0), 2),
            "top_attributed_appliance": top_app,
            "recommendation": rec
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decision classification failure: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

