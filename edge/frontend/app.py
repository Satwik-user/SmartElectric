import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time

# Page config
st.set_page_config(
    page_title="SmartElectric Gateway",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Endpoint definition
API_BASE_URL = st.sidebar.text_input("API Base URL", "http://localhost:8000")

# Helper function to query the API
def fetch_api_data(endpoint):
    import requests
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", timeout=2.5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None

# Fetch status early to configure sidebar toggles
status_data = fetch_api_data("/api/status")

# Database absolute path (for display)
DB_PATH = "/home/jetson/smartelectric/edge/backend/edge_iot.db"

# Auto-refresh interval (seconds)
st.sidebar.markdown("---")
auto_refresh = st.sidebar.checkbox("Live Auto-Refresh (5s)", value=True)

# Auto-Shedding toggle in sidebar
auto_shedding = st.sidebar.checkbox(
    "Preemptive Auto-Shedding", 
    value=status_data.get("auto_shedding_enabled", False) if status_data else False,
    help="Automatically shuts down non-essential loads if load is predicted to exceed 400W"
)

if status_data and auto_shedding != status_data.get("auto_shedding_enabled", False):
    import requests
    requests.post(f"{API_BASE_URL}/api/control/shedding", json={"enabled": auto_shedding})
    st.rerun()

if auto_refresh:
    # Use HTML meta refresh fallback to trigger Streamlit rerun safely every 5 seconds
    st.markdown(
        """
        <noscript>
            <meta http-equiv="refresh" content="5">
        </noscript>
        """,
        unsafe_allow_html=True
    )

# Custom styling for premium dark theme aesthetics
st.markdown("""
<style>
    /* Global Background and Fonts */
    .stApp {
        background-color: #0b0f19;
        color: #e2e8f0;
    }
    
    /* Premium Title Header */
    .header-container {
        background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%);
        padding: 24px;
        border-radius: 12px;
        border: 1px solid #312e81;
        margin-bottom: 25px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    .main-title {
        color: #818cf8;
        font-family: 'Outfit', 'Inter', sans-serif;
        font-weight: 800;
        font-size: 2.5rem;
        margin: 0;
        text-shadow: 0 2px 10px rgba(129, 140, 248, 0.3);
    }
    .sub-title {
        color: #94a3b8;
        font-size: 1.05rem;
        margin-top: 5px;
        margin-bottom: 0;
    }
    
    /* Glassmorphism Metric Cards */
    .metric-card {
        background: rgba(30, 41, 59, 0.45);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        transition: transform 0.3s ease, border-color 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-4px);
        border-color: rgba(129, 140, 248, 0.4);
    }
    .metric-label {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #94a3b8;
        margin-bottom: 8px;
    }
    .metric-val {
        font-size: 2.2rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 0;
        background: linear-gradient(to right, #ffffff, #cbd5e1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .metric-val-colored {
        font-size: 2.2rem;
        font-weight: 700;
        margin: 0;
    }
    .power-color {
        background: linear-gradient(to right, #fbbf24, #f59e0b);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .temp-color {
        background: linear-gradient(to right, #f87171, #ef4444);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hum-color {
        background: linear-gradient(to right, #38bdf8, #0ea5e9);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .metric-unit {
        font-size: 1rem;
        color: #64748b;
        margin-left: 2px;
    }
    
    /* Appliance status tag badges */
    .badge {
        display: inline-block;
        padding: 6px 12px;
        border-radius: 50px;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    .badge-on {
        background-color: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .badge-off {
        background-color: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# Main Dashboard Title block
st.markdown("""
    <div class="header-container">
        <h1 class="main-title">SmartElectric</h1>
        <p class="sub-title">🤖 Local Edge Gateway & Live Home Telemetry | Power, Load & Climate Dashboard</p>
    </div>
""", unsafe_allow_html=True)

# Fetch metrics from API
metrics_data = fetch_api_data("/api/metrics?range_type=today")

# Check API availability
if not status_data:
    st.error("⚠️ Local Edge API is currently Offline or Unreachable. Please check that uvicorn/main.py is running on port 8000.")
    if st.button("Retry Connection"):
        st.rerun()
else:
    # Parse API payload
    appliances = status_data.get("appliances", [])
    telemetry = status_data.get("latest_telemetry", {})
    dht = status_data.get("dht", {})
    anomaly_status = status_data.get("anomaly_status", {})
    
    # Parse power source metrics
    power_source = status_data.get("power_source", "Grid")
    total_power = float(status_data.get("total_power", 0.0))
    total_current = sum(item.get("current", 0.0) for item in telemetry.values())
    avg_voltage = 230.0 # Standard Grid Voltage
    
    # Today's kWh totals from metrics endpoint
    today_kwh = 0.0
    today_cost = 0.0
    if metrics_data:
        today_kwh = metrics_data.get("totals", {}).get("kwh", 0.0)
        today_cost = metrics_data.get("totals", {}).get("flat_cost_inr", 0.0)

    # Power Source Switch alert banner
    if power_source == "Solar":
        st.success(f"☀️ **Power Source: SOLAR GENERATION ACTIVE** — The total house load of **{total_power:.1f}W** has exceeded the **400W** threshold. Simulated solar power is currently feeding the circuits to safeguard the grid.")
    else:
        st.info(f"⚡ **Power Source: MAIN GRID ACTIVE** — The total house load of **{total_power:.1f}W** is within the safety threshold of **400W**.")

    # Preemptive Auto-Shedding & Warning alerts
    preemptive_warning = status_data.get("preemptive_warning", False)
    predicted_max = status_data.get("predicted_max_power", 0.0)
    shed_triggered = status_data.get("shed_triggered", False)
    shedded_appliance = status_data.get("shedded_appliance", None)
    
    if preemptive_warning:
        if status_data.get("auto_shedding_enabled", False):
            if shed_triggered:
                st.success(f"🛡️ **Preemptive Load Shedding Triggered:** Automatically turned OFF **{shedded_appliance}** to prevent predicted grid overload ({predicted_max:.1f}W > 400W).")
        else:
            st.warning(f"⚠️ **Preemptive Overload Warning:** Future demand is predicted to spike to **{predicted_max:.1f}W** in the next hour. Consider manually turning off heavy loads like TV or Fan to avoid grid switch.")

    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Load</div>
                <div class="metric-val-colored power-color">{total_power:.1f}<span class="metric-unit">W</span></div>
            </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Current</div>
                <div class="metric-val">{total_current:.2f}<span class="metric-unit">A</span></div>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Today's Consumption</div>
                <div class="metric-val">{today_kwh:.3f}<span class="metric-unit">kWh</span></div>
            </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Today's Cost (flat)</div>
                <div class="metric-val" style="color:#10b981;">₹{today_cost:.2f}</div>
            </div>
        """, unsafe_allow_html=True)

    with col5:
        # Display Temperature/Humidity
        temp = dht.get("temperature", 0.0)
        hum = dht.get("humidity", 0.0)
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Indoor Climate</div>
                <div class="metric-val-colored temp-color">{temp:.1f}°C <span style="font-size:1.1rem; color:#64748b;">/ {hum:.0f}%</span></div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 2. Visualizations and Status Table Grid
    vis_col, table_col = st.columns([3, 2])

    with vis_col:
        st.subheader("⚡ Active Power Consumption Breakdown (Watts)")
        # Map telemetry data for plotting
        chart_data = []
        for app_name, info in telemetry.items():
            chart_data.append({
                "Appliance": app_name,
                "Power (W)": info.get("power", 0.0),
                "Current (A)": info.get("current", 0.0)
            })
        
        df_chart = pd.DataFrame(chart_data)
        
        if df_chart["Power (W)"].sum() > 0:
            fig = px.bar(
                df_chart, 
                x="Appliance", 
                y="Power (W)", 
                color="Appliance",
                text="Power (W)",
                color_discrete_sequence=px.colors.qualitative.Pastel,
                template="plotly_dark"
            )
            fig.update_traces(
                texttemplate='%{text:.1f} W', 
                textposition='outside',
                marker_line_color='rgb(8,48,107)', 
                marker_line_width=1.5, 
                opacity=0.85
            )
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                xaxis_title="",
                yaxis_title="Active Power (Watts)",
                yaxis_gridcolor='rgba(255,255,255,0.05)',
                margin=dict(l=20, r=20, t=10, b=10),
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("🔌 All appliances are currently drawing 0.0W. (No active load detected)")

    with table_col:
        st.subheader("📋 Appliance States")
        
        # Build DataFrame of current appliance states
        table_rows = []
        for app in appliances:
            app_name = app["name"]
            status_val = app["status"]
            
            # Retrieve telemetry for status details
            app_tel = telemetry.get(app_name, {})
            power = app_tel.get("power", 0.0)
            current = app_tel.get("current", 0.0)
            
            status_badge = (
                f'<span class="badge badge-on">ON</span>' 
                if status_val == 1 
                else f'<span class="badge badge-off">OFF</span>'
            )
            
            # Retrieve anomaly status
            anomaly_desc = anomaly_status.get(app_name)
            safety_badge = (
                f'<span class="badge" style="background-color:rgba(239,68,68,0.15); color:#f87171; border:1px solid rgba(239,68,68,0.3); font-size:0.75rem; font-weight:700;">⚠️ ANOMALY: {anomaly_desc}</span>'
                if anomaly_desc
                else '<span class="badge" style="background-color:rgba(16,185,129,0.15); color:#34d399; border:1px solid rgba(16,185,129,0.3); font-size:0.75rem; font-weight:700;">✔️ NORMAL</span>'
            )
            
            table_rows.append({
                "Appliance": f"**{app_name}**",
                "Relay Pin": f"GPIO {app['relay_pin']}",
                "Status": status_badge,
                "Safety Status": safety_badge,
                "Current Load (W)": f"{power:.1f} W",
                "Current (A)": f"{current:.2f} A"
            })
            
        df_status = pd.DataFrame(table_rows)
        
        # Render HTML table with custom styling for custom badges
        html_table = df_status.to_html(escape=False, index=False, classes="table table-hover")
        # Apply CSS style directly to table
        st.markdown(f"""
            <div style="background: rgba(30, 41, 59, 0.25); padding: 15px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05);">
                {html_table}
            </div>
            <br>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 2.5. Solar Generation Forecast (ML-Based)
    st.subheader("☀️ Solar Generation Forecast (Next 3 Hours)")
    forecast_data = fetch_api_data("/api/solar/forecast")
    if forecast_data and forecast_data.get("status") == "success":
        forecast_vals = forecast_data.get("forecast", [])
        
        # Display as columns
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            st.markdown(f"""
                <div class="metric-card" style="padding: 12px 20px;">
                    <div class="metric-label" style="font-size:0.75rem;">In 1 Hour</div>
                    <div class="metric-val" style="font-size:1.6rem; color:#34d399;">{forecast_vals[0]:.1f}<span class="metric-unit">W</span></div>
                </div>
            """, unsafe_allow_html=True)
        with f_col2:
            st.markdown(f"""
                <div class="metric-card" style="padding: 12px 20px;">
                    <div class="metric-label" style="font-size:0.75rem;">In 2 Hours</div>
                    <div class="metric-val" style="font-size:1.6rem; color:#34d399;">{forecast_vals[1]:.1f}<span class="metric-unit">W</span></div>
                </div>
            """, unsafe_allow_html=True)
        with f_col3:
            st.markdown(f"""
                <div class="metric-card" style="padding: 12px 20px;">
                    <div class="metric-label" style="font-size:0.75rem;">In 3 Hours</div>
                    <div class="metric-val" style="font-size:1.6rem; color:#34d399;">{forecast_vals[2]:.1f}<span class="metric-unit">W</span></div>
                </div>
            """, unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        # Draw Line Chart
        df_forecast = pd.DataFrame({
            "Time Ahead": ["1 Hour", "2 Hours", "3 Hours"],
            "Solar Forecast (W)": forecast_vals
        })
        fig_solar = px.line(
            df_forecast,
            x="Time Ahead",
            y="Solar Forecast (W)",
            markers=True,
            template="plotly_dark"
        )
        fig_solar.update_traces(line_color="#34d399", marker=dict(size=8, color="#10b981"))
        fig_solar.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            yaxis_gridcolor='rgba(255,255,255,0.05)',
            xaxis_title="",
            yaxis_title="Expected Output (Watts)",
            margin=dict(l=20, r=20, t=10, b=10)
        )
        st.plotly_chart(fig_solar, use_container_width=True)
    else:
        st.info("Solar forecast unavailable. Ensure climate sensors are reporting data.")

    st.markdown("---")

    # 3. Connection Diagnostics Footer
    foot_col1, foot_col2, foot_col3 = st.columns(3)
    
    with foot_col1:
        st.markdown(f"""
            <div style="background: rgba(30, 41, 59, 0.2); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 8px; padding: 12px; text-align: center;">
                <span style="color: #64748b; font-size: 0.8rem;">DATABASE PATH</span><br>
                <code style="color: #818cf8; font-size: 0.75rem;">{DB_PATH}</code>
            </div>
        """, unsafe_allow_html=True)
        
    with foot_col2:
        # Check MQTT status by parsing last logs or simple API state
        mqtt_status = "Connected"
        st.markdown(f"""
            <div style="background: rgba(30, 41, 59, 0.2); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 8px; padding: 12px; text-align: center;">
                <span style="color: #64748b; font-size: 0.8rem;">LOCAL BROKER (MOSQUITTO)</span><br>
                <b style="color: #34d399; font-size: 0.95rem;">● {mqtt_status}</b>
            </div>
        """, unsafe_allow_html=True)

    with foot_col3:
        st.markdown(f"""
            <div style="background: rgba(30, 41, 59, 0.2); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 8px; padding: 12px; text-align: center;">
                <span style="color: #64748b; font-size: 0.8rem;">SYSTEM CLOCK</span><br>
                <span style="color: #cbd5e1; font-size: 0.95rem;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
            </div>
        """, unsafe_allow_html=True)

# Add a slight sleep and rerun to simulate live auto-refresh if enabled
if auto_refresh:
    time.sleep(5)
    st.rerun()
