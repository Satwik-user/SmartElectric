import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import datetime

st.set_page_config(
    page_title="SmartElectric - AI Forecasting",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)


# API Endpoint details
API_BASE = "http://localhost:8000"

st.title("🤖 AI Energy Forecasting & Load Optimization")
st.markdown("---")

# Custom styled header card
st.markdown("""
<div style="background-color:#1e293b;padding:20px;border-radius:10px;border-left:5px solid #3b82f6;margin-bottom:20px;">
    <h3 style="color:#f8fafc;margin:0;">Time-Series Forecast Model (GRU)</h3>
    <p style="color:#94a3b8;margin:5px 0 0 0;">
        This page interfaces with the edge gateway's pre-trained <b>Gated Recurrent Unit (GRU)</b> model. 
        It evaluates the past 24 hours of aggregate load curves and projects energy consumption 1 hour into the future.
    </p>
</div>
""", unsafe_allow_html=True)

# Query current live load
live_load = 250.0
try:
    response = requests.get(f"{API_BASE}/api/status", timeout=2)
    if response.status_code == 200:
        data = response.json()
        telemetry = data.get("latest_telemetry", {})
        live_load = sum(float(v.get("power", 0.0)) for v in telemetry.values())
except Exception:
    pass # Fallback to default if API is not active

# Interactive Controls in Sidebar
st.sidebar.header("🤖 Model Inference Config")
sim_load = st.sidebar.slider(
    "Simulated Current Load (Watts)", 
    min_value=0.0, 
    max_value=1200.0, 
    value=float(live_load), 
    step=10.0,
    help="Adjust to simulate forecasting results for different energy usage states."
)

if st.sidebar.button("Re-train Local GRU Model"):
    with st.spinner("Executing model training pipeline on database..."):
        try:
            # We can invoke training by triggering python script if running locally,
            # or just show a success for the mock integration
            import subprocess
            import os
            script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backend", "ml_forecaster.py")
            res = subprocess.run(["python", script_path, "--train"], capture_output=True, text=True, timeout=30)
            if res.returncode == 0:
                st.sidebar.success("GRU model retrained and weights updated!")
            else:
                st.sidebar.error(f"Training failed: {res.stderr}")
        except Exception as e:
            st.sidebar.error(f"Error initiating training: {e}")

# Fetch predictions
try:
    load_res = requests.post(f"{API_BASE}/api/v1/predict/load", json={"current_load": sim_load}, timeout=2)
    dec_res = requests.post(f"{API_BASE}/api/v1/predict/decision", json={"current_load": sim_load}, timeout=2)
    
    if load_res.status_code == 200 and dec_res.status_code == 200:
        load_data = load_res.json()
        dec_data = dec_res.json()
        
        # Display KPIs
        col1, col2, col3 = st.columns(3)
        
        # Color code severity status
        severity = dec_data.get("classification", "NORMAL")
        sev_color = "#22c55e" # green
        if severity == "HIGH":
            sev_color = "#ef4444" # red
        elif severity == "WARNING":
            sev_color = "#f97316" # orange
            
        with col1:
            st.markdown(f"""
            <div style="background-color:#0f172a;padding:15px;border-radius:8px;text-align:center;border:1px solid #334155;">
                <span style="color:#64748b;font-size:14px;font-weight:bold;">LOAD SEVERITY STATE</span>
                <h2 style="color:{sev_color};margin:5px 0;">{severity}</h2>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown(f"""
            <div style="background-color:#0f172a;padding:15px;border-radius:8px;text-align:center;border:1px solid #334155;">
                <span style="color:#64748b;font-size:14px;font-weight:bold;">ANOMALY PROBABILITY SCORE</span>
                <h2 style="color:#3b82f6;margin:5px 0;">{int(dec_data.get("anomaly_score", 0.0) * 100)}%</h2>
            </div>
            """, unsafe_allow_html=True)
            
        with col3:
            st.markdown(f"""
            <div style="background-color:#0f172a;padding:15px;border-radius:8px;text-align:center;border:1px solid #334155;">
                <span style="color:#64748b;font-size:14px;font-weight:bold;">TOP ATTRIBUTED LOAD</span>
                <h2 style="color:#a855f7;margin:5px 0;">{dec_data.get("top_attributed_appliance", "N/A")}</h2>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Plot future power trend curve
        st.subheader("📈 Projected Power Consumption Curve (1-Hour Horizon)")
        
        timestamps = load_data.get("forecasted_timestamps", [])
        values = load_data.get("forecasted_power_watts", [])
        
        # Create dataframe
        df = pd.DataFrame({
            "Time": [datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S").strftime("%H:%M:%S") for t in timestamps],
            "Forecasted Load (W)": values
        })
        
        fig = px.area(
            df, 
            x="Time", 
            y="Forecasted Load (W)", 
            markers=True,
            color_discrete_sequence=["#3b82f6"]
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=True, gridcolor='#334155'),
            yaxis=dict(showgrid=True, gridcolor='#334155'),
            font=dict(color='#f8fafc')
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Recommendations card
        st.markdown(f"""
        <div style="background-color:#0f172a;padding:20px;border-radius:8px;border:1px solid #334155;">
            <h4 style="color:#3b82f6;margin:0 0 10px 0;">💡 AI Recommendation engine</h4>
            <p style="color:#cbd5e1;margin:0;font-size:16px;">{dec_data.get("recommendation", "")}</p>
        </div>
        """, unsafe_allow_html=True)

    else:
        st.error("Error: Local API returned an error code. Make sure the API server is active.")
except requests.exceptions.ConnectionError:
    st.error("🔌 Connection Error: Could not connect to the local FastAPI Backend on port 8000.")
    st.info("Please start the API service (e.g. run `./edge/scripts/5-start-all.sh`) to activate machine learning models.")
