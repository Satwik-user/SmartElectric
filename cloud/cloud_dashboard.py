import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="SmartElectric Cloud",
    page_icon="☁️",
    layout="wide"
)

# API Endpoint config
CLOUD_API_URL = st.sidebar.text_input("Cloud API URL", "http://localhost:8002")

# Custom Styling for Cloud Platform (Sleek deep blue theme)
st.markdown("""
<style>
    .stApp {
        background-color: #050811;
        color: #e2e8f0;
    }
    .cloud-header {
        background: linear-gradient(135deg, #1e3a8a 0%, #0b1329 100%);
        padding: 24px;
        border-radius: 12px;
        border: 1px solid #1d4ed8;
        margin-bottom: 25px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
    }
    .cloud-title {
        color: #60a5fa;
        font-family: 'Outfit', sans-serif;
        font-weight: 800;
        font-size: 2.5rem;
        margin: 0;
    }
    .cloud-sub {
        color: #94a3b8;
        font-size: 1.05rem;
        margin-top: 5px;
    }
    .device-card {
        background: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(30, 58, 138, 0.4);
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 15px;
    }
    .kpi-card {
        background: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(255,255,255,0.05);
        border-radius: 12px;
        padding: 18px;
        text-align: center;
    }
    .kpi-label {
        font-size: 0.8rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .kpi-val {
        font-size: 1.8rem;
        font-weight: 700;
        color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)

# Main Title Block
st.markdown("""
    <div class="cloud-header">
        <h1 class="cloud-title">SmartElectric Cloud Platform</h1>
        <p class="cloud-sub">☁️ Global Fleet Management and Remote Diagnostic Dashboard</p>
    </div>
""", unsafe_allow_html=True)

# Helper function to get API data
def fetch_cloud_data(endpoint):
    try:
        response = requests.get(f"{CLOUD_API_URL}{endpoint}", timeout=4.0)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None

# Fetch devices
devices = fetch_cloud_data("/api/cloud/devices")

if not devices:
    st.error("⚠️ Connection to Cloud API failed. Make sure the cloud server is running and database initialized.")
    if st.button("Retry Connection"):
        st.rerun()
else:
    # Build device options
    device_opts = {f"{d['name']} ({d['location']})": d for d in devices}
    selected_name = st.selectbox("Select Target Edge Gateway", options=list(device_opts.keys()))
    
    selected_device = device_opts[selected_name]
    device_id = selected_device["device_id"]

    # 1. Device Metadata Panel
    st.markdown(f"""
        <div class="device-card">
            <h4 style="color:#60a5fa; margin-top:0; margin-bottom:10px;">📟 Device Configuration & Sync Status</h4>
            <table style="width:100%; font-size:0.9rem; color:#cbd5e1;">
                <tr>
                    <td><b>Hardware Device ID:</b> <code>{device_id}</code></td>
                    <td><b>Gateway Name:</b> {selected_device['name']}</td>
                    <td><b>Registered At:</b> {selected_device['registered_at']}</td>
                </tr>
                <tr>
                    <td><b>Installation Location:</b> {selected_device['location']}</td>
                    <td><b>Last Database Sync:</b> {selected_device['last_sync'] or 'Never'}</td>
                    <td><b>Synced Records:</b> Sensors: {selected_device['telemetry_counts']['sensors']} | Climate: {selected_device['telemetry_counts']['dht']}</td>
                </tr>
            </table>
        </div>
    """, unsafe_allow_html=True)

    # Fetch telemetry for this device
    telemetry = fetch_cloud_data(f"/api/cloud/telemetry?device_id={device_id}")

    if not telemetry:
        st.warning("Could not fetch remote telemetry logs for this device.")
    else:
        sensor_records = telemetry.get("sensor_data", [])
        dht_records = telemetry.get("dht_data", [])
        logs = telemetry.get("logs", [])

        # Calculate metrics if telemetry exists
        if sensor_records:
            df_sensor = pd.DataFrame(sensor_records)
            df_sensor["timestamp"] = pd.to_datetime(df_sensor["timestamp"])
            avg_power = df_sensor["power"].mean()
            max_power = df_sensor["power"].max()
        else:
            avg_power = 0.0
            max_power = 0.0
            df_sensor = pd.DataFrame()

        if dht_records:
            df_dht = pd.DataFrame(dht_records)
            df_dht["timestamp"] = pd.to_datetime(df_dht["timestamp"])
            latest_temp = df_dht.iloc[0]["temperature"]
            latest_hum = df_dht.iloc[0]["humidity"]
        else:
            latest_temp = 0.0
            latest_hum = 0.0
            df_dht = pd.DataFrame()

        # 2. KPI Cards
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        with kpi1:
            st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-label">Average Power Load</div>
                    <div class="kpi-val" style="color: #60a5fa;">{avg_power:.1f} W</div>
                </div>
            """, unsafe_allow_html=True)
        with kpi2:
            st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-label">Peak Power Recorded</div>
                    <div class="kpi-val" style="color: #fbbf24;">{max_power:.1f} W</div>
                </div>
            """, unsafe_allow_html=True)
        with kpi3:
            st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-label">Indoor Temp (Last Sync)</div>
                    <div class="kpi-val" style="color: #f87171;">{latest_temp:.1f} °C</div>
                </div>
            """, unsafe_allow_html=True)
        with kpi4:
            st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-label">Indoor Humidity (Last Sync)</div>
                    <div class="kpi-val" style="color: #38bdf8;">{latest_hum:.0f} %</div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # 3. Charts & Analytics
        char_col1, char_col2 = st.columns(2)

        with char_col1:
            st.subheader("📈 Historical Power Load Timeline (Cloud Sync)")
            if not df_sensor.empty:
                df_sensor_sorted = df_sensor.sort_values("timestamp")
                fig_line = px.line(
                    df_sensor_sorted,
                    x="timestamp",
                    y="power",
                    color="appliance_name",
                    template="plotly_dark",
                    labels={"power": "Power Draw (Watts)", "timestamp": "Sync Timestamp", "appliance_name": "Appliance"}
                )
                fig_line.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    yaxis_gridcolor='rgba(255,255,255,0.05)',
                    xaxis_gridcolor='rgba(255,255,255,0.05)',
                    margin=dict(l=20, r=20, t=10, b=10)
                )
                st.plotly_chart(fig_line, use_container_width=True)
            else:
                st.info("Waiting for historical sensor telemetry uploads from edge device.")

        with char_col2:
            st.subheader("🌡️ Climate Analytics Timeline")
            if not df_dht.empty:
                df_dht_sorted = df_dht.sort_values("timestamp")
                fig_climate = go.Figure()
                fig_climate.add_trace(go.Scatter(
                    x=df_dht_sorted["timestamp"], 
                    y=df_dht_sorted["temperature"],
                    mode='lines',
                    name='Temp (°C)',
                    line=dict(color='#f87171', width=2)
                ))
                fig_climate.add_trace(go.Scatter(
                    x=df_dht_sorted["timestamp"], 
                    y=df_dht_sorted["humidity"],
                    mode='lines',
                    name='Humidity (%)',
                    line=dict(color='#38bdf8', width=2),
                    yaxis='y2'
                ))
                
                fig_climate.update_layout(
                    template="plotly_dark",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    margin=dict(l=20, r=20, t=10, b=10),
                    yaxis=dict(title='Temperature (°C)', titlefont=dict(color='#f87171'), tickfont=dict(color='#f87171')),
                    yaxis2=dict(title='Humidity (%)', titlefont=dict(color='#38bdf8'), tickfont=dict(color='#38bdf8'), overlaying='y', side='right'),
                    showlegend=True
                )
                st.plotly_chart(fig_climate, use_container_width=True)
            else:
                st.info("Waiting for historical climate uploads from edge device.")

        st.markdown("---")

        # 4. Logs feed
        st.subheader("📋 Remote System Log Feed (Last 50 Entries)")
        if logs:
            df_logs = pd.DataFrame(logs)
            df_logs = df_logs[["timestamp", "level", "message"]]
            df_logs.columns = ["Timestamp", "Level", "Log Message"]
            
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
            st.info("No system event logs uploaded from this edge device yet.")
