import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="Analytics - SmartElectric",
    page_icon="📊",
    layout="wide"
)

# Sidebar configurations
API_BASE_URL = st.sidebar.text_input("API Base URL", "http://localhost:8000", key="analytics_api")

# Custom CSS for Analytics page
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
    .analytics-title {
        color: #818cf8;
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        font-size: 2.2rem;
        margin: 0;
    }
    .analytics-sub {
        color: #94a3b8;
        font-size: 1rem;
        margin-top: 5px;
    }
    .kpi-card {
        background: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 18px;
        text-align: center;
    }
    .kpi-label {
        font-size: 0.8rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    }
    .kpi-val {
        font-size: 1.8rem;
        font-weight: 700;
        color: #f8fafc;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
    <div class="header-container">
        <h1 class="analytics-title">Analytics & Billing Reports</h1>
        <p class="analytics-sub">⚡ Analyze historical power consumption patterns and estimate energy tariff costs in Indian Rupees (₹)</p>
    </div>
""", unsafe_allow_html=True)

# Helper function to get API data
def fetch_api_data(endpoint):
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", timeout=3.0)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None

# Time period selection
range_type = st.selectbox(
    "Select Calculation Period",
    options=["today", "month", "total"],
    format_func=lambda x: {"today": "Today (Since Midnight)", "month": "This Billing Month", "total": "All-Time Historical"}[x]
)

metrics_data = fetch_api_data(f"/api/metrics?range_type={range_type}")
history_data = fetch_api_data("/api/history?limit=300")

if not metrics_data:
    st.error("⚠️ Connection to Edge API failed. Make sure the backend service is running.")
else:
    totals = metrics_data.get("totals", {})
    appliances_metrics = metrics_data.get("appliances", {})
    
    # 1. Billing & Consumption Summary Cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Total Energy Consumed</div>
                <div class="kpi-val" style="color: #fbbf24;">{totals.get('kwh', 0.0):.3f} kWh</div>
            </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Estimated Bill (Flat Rate)</div>
                <div class="kpi-val" style="color: #34d399;">₹{totals.get('flat_cost_inr', 0.0):.2f}</div>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Estimated Bill (Tiered)</div>
                <div class="kpi-val" style="color: #60a5fa;">₹{totals.get('tiered_cost_inr', 0.0):.2f}</div>
            </div>
        """, unsafe_allow_html=True)

    with col4:
        # Carbon footprint (approx. 0.82 kg CO2 per kWh in Indian grid)
        carbon = totals.get('kwh', 0.0) * 0.82
        st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">CO₂ Carbon Footprint</div>
                <div class="kpi-val" style="color: #f87171;">{carbon:.2f} kg</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("### 🔍 Energy Breakdown & Tariff Comparisons")

    grid_col1, grid_col2 = st.columns(2)

    with grid_col1:
        st.subheader("💡 Appliance Consumption Comparison")
        # Build dataframe for chart
        app_list = []
        for name, data in appliances_metrics.items():
            app_list.append({
                "Appliance": name,
                "kWh": data.get("kwh", 0.0),
                "Hours Active": data.get("duration_hours", 0.0),
                "Cost (₹)": data.get("flat_cost_inr", 0.0)
            })
        df_app = pd.DataFrame(app_list)
        
        if df_app["kWh"].sum() > 0:
            fig_pie = px.pie(
                df_app, 
                values='kWh', 
                names='Appliance', 
                hole=0.4,
                title="Share of Energy Consumption (kWh)",
                template="plotly_dark",
                color_discrete_sequence=px.colors.qualitative.Safe
            )
            fig_pie.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No consumption data recorded during this period.")

    with grid_col2:
        st.subheader("📊 Cost Structure Analysis")
        # Horizontal bar chart comparing flat vs tiered cost by appliance
        df_cost = df_app.copy()
        if df_cost["kWh"].sum() > 0:
            # Generate tiered costs for appliances individually
            tiered_list = []
            for name, data in appliances_metrics.items():
                tiered_list.append(data.get("tiered_cost_inr", 0.0))
            df_cost["Tiered Cost (₹)"] = tiered_list
            df_cost.rename(columns={"Cost (₹)": "Flat Cost (₹)"}, inplace=True)
            
            fig_bar = go.Figure(data=[
                go.Bar(name='Flat Rate (₹7/kWh)', x=df_cost['Appliance'], y=df_cost['Flat Cost (₹)'], marker_color='#34d399'),
                go.Bar(name='Tiered Rate', x=df_cost['Appliance'], y=df_cost['Tiered Cost (₹)'], marker_color='#60a5fa')
            ])
            fig_bar.update_layout(
                barmode='group',
                title="Billing cost comparison (Flat vs Tiered)",
                template="plotly_dark",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                yaxis_gridcolor='rgba(255,255,255,0.05)',
                xaxis_title="",
                yaxis_title="Cost in Indian Rupees (₹)",
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No billing data recorded during this period.")

    # 2. Historical Load Curve
    st.markdown("### 📈 Live Historical Load Curves (Watts)")
    if history_data and len(history_data) > 0:
        df_hist = pd.DataFrame(history_data)
        
        # Convert timestamp to datetime
        df_hist["timestamp"] = pd.to_datetime(df_hist["timestamp"])
        df_hist.sort_values("timestamp", inplace=True)
        
        # Plot multi-line chart
        fig_line = px.line(
            df_hist, 
            x="timestamp", 
            y="power", 
            color="appliance_name",
            labels={"timestamp": "Time", "power": "Power Draw (Watts)", "appliance_name": "Appliance"},
            template="plotly_dark",
            title="Appliance Power Telemetry Timeline"
        )
        fig_line.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            yaxis_gridcolor='rgba(255,255,255,0.05)',
            xaxis_gridcolor='rgba(255,255,255,0.05)',
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("⌛ Waiting for telemetry logs to compile historical graphs...")

    # 3. Tariff Explanation block
    st.markdown("""
        <div style="background: rgba(30, 41, 59, 0.3); border: 1px solid rgba(129, 140, 248, 0.2); border-radius: 12px; padding: 20px; margin-top: 25px;">
            <h4 style="color: #818cf8; margin-top:0;">📋 Indian Tariff Billing Guide</h4>
            <p style="font-size: 0.9rem; color: #cbd5e1;">The cost calculators on this page comparison model utilize two common rate structures in India:</p>
            <ul style="font-size: 0.9rem; color: #cbd5e1;">
                <li><b>Flat Rate:</b> Charged at a uniform <b>₹7.00 per kWh</b>. Ideal for standard estimation.</li>
                <li><b>Tiered Slab Model:</b> Mimics residential electrical slabs:
                    <ul>
                        <li>First 100 kWh: <b>₹4.50 / kWh</b></li>
                        <li>101 to 300 kWh: <b>₹6.50 / kWh</b></li>
                        <li>Above 300 kWh: <b>₹8.00 / kWh</b></li>
                    </ul>
                </li>
            </ul>
        </div>
    """, unsafe_allow_html=True)
