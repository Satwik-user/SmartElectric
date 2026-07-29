import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Control Panel - SmartElectric",
    page_icon="🔌",
    layout="wide"
)

# Sidebar configurations
API_BASE_URL = st.sidebar.text_input("API Base URL", "http://localhost:8000", key="control_api")

# Custom CSS for Control page
st.markdown("""
<style>
    .stApp {
        background-color: #0b0f19;
        color: #e2e8f0;
    }
    .header-container {
        background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #312e81;
        margin-bottom: 25px;
    }
    .control-title {
        color: #818cf8;
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        font-size: 2.2rem;
        margin: 0;
    }
    .control-sub {
        color: #94a3b8;
        font-size: 1rem;
        margin-top: 5px;
    }
    .control-card {
        background: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .card-title {
        font-size: 1.5rem;
        font-weight: 600;
        color: #f8fafc;
        margin-bottom: 5px;
    }
    .card-pin {
        font-size: 0.8rem;
        color: #64748b;
        margin-bottom: 15px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .state-indicator {
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 20px;
    }
    .state-on {
        color: #34d399;
    }
    .state-off {
        color: #f87171;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
    <div class="header-container">
        <h1 class="control-title">Appliance Control Panel</h1>
        <p class="control-sub">🔌 Remotely actuate relays with built-in hardware chattering prevention locks</p>
    </div>
""", unsafe_allow_html=True)

# Helper function to get API data
def fetch_api_data(endpoint):
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", timeout=2.0)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None

# Helper function to send command
def post_api_control(appliance_name, state):
    try:
        payload = {"appliance": appliance_name, "state": state}
        response = requests.post(f"{API_BASE_URL}/api/control", json=payload, timeout=3.0)
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Connection Error: {e}")
        return None

# Fetch statuses
status_data = fetch_api_data("/api/status")
logs_data = fetch_api_data("/api/logs?limit=15")

if not status_data:
    st.error("⚠️ Connection to Edge API failed. Make sure the backend service is running.")
    if st.button("Retry"):
        st.rerun()
else:
    appliances = status_data.get("appliances", [])
    telemetry = status_data.get("latest_telemetry", {})

    # Grid of control cards
    cols = st.columns(4)
    
    for i, app in enumerate(appliances):
        name = app["name"]
        db_state = app["status"]
        pin = app["relay_pin"]
        app_tel = telemetry.get(name, {})
        power = app_tel.get("power", 0.0)

        with cols[i]:
            st.markdown(f"""
                <div class="control-card">
                    <div class="card-title">{name}</div>
                    <div class="card-pin">Relay Pin: GPIO {pin}</div>
                    <div class="state-indicator {'state-on' if db_state == 1 else 'state-off'}">
                        ● {'ON' if db_state == 1 else 'OFF'} ({power:.1f} W)
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # The Toggle Switch
            toggle_key = f"toggle_{name}_{db_state}" # Key incorporates state to align starting state
            new_state = st.toggle(
                f"Toggle {name}", 
                value=(db_state == 1), 
                key=toggle_key, 
                label_visibility="collapsed"
            )
            
            # Action on state difference
            if new_state != (db_state == 1):
                target_state = 1 if new_state else 0
                res = post_api_control(name, target_state)
                
                if res and res.get("status") == "success":
                    # Check if command went through MQTT successfully
                    if res.get("mqtt_published"):
                        st.success(f"⚡ {name} switched {'ON' if target_state == 1 else 'OFF'}")
                    else:
                        st.warning(f"⚠️ State recorded locally, but failed to reach ESP32 broker.")
                    # Sleep briefly and rerun to refresh state indicators
                    st.rerun()
                else:
                    st.error("🔒 Blocked: Safety Lockout Cooldown in progress. Wait 3 seconds.")

    st.markdown("---")
    
    # 2. Live Logs section
    st.subheader("📋 Gateway Event Logs")
    if logs_data and len(logs_data) > 0:
        df_logs = pd.DataFrame(logs_data)
        
        # Stylize logs dataframe
        df_logs = df_logs[["timestamp", "level", "message"]]
        df_logs.columns = ["Timestamp", "Level", "Log Message"]
        
        # Color coding function for display
        def color_logs(val):
            if val == "ERROR" or "crashed" in str(val).lower():
                return 'color: #f87171; font-weight: bold;'
            elif val == "WARNING":
                return 'color: #fbbf24; font-weight: bold;'
            elif val == "INFO":
                return 'color: #60a5fa;'
            return ''
            
        st.dataframe(
            df_logs.style.map(color_logs, subset=['Level']),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No system events logged in SQLite yet.")

    # Refresh logs button
    if st.button("Refresh Event Logs"):
        st.rerun()
