import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
import base64
from io import BytesIO
from PIL import Image
from datetime import timedelta

# -----------------------------
# Helper Functions
# -----------------------------
def get_image_base64(image_path):
    try:
        img = Image.open(image_path)
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}"
    except:
        return ""

# -----------------------------
# Page configuration
# -----------------------------
st.set_page_config(page_title="Georgetown Inn Revenue Portal", layout="wide", page_icon="🏨")

# Custom Styling
st.markdown("""
<style>
    .main { background-color:#f5f7f9; }
    .stMetric { background-color:white; padding:15px; border-radius:10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .event-card { padding: 10px; border-radius: 5px; margin-bottom: 10px; border-left: 5px solid #ff4b4b; background: #fff; }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Data Loading & Prep
# -----------------------------
@st.cache_data
def load_data():
    # Load Competitor Data
    comp = pd.read_csv("competitor_rates.csv")
    comp["Date"] = pd.to_datetime(comp["Date"])
    
    # Load Events Data
    events = pd.read_csv("events_dc.csv")
    events["Date"] = pd.to_datetime(events["Date"])
    
    # Load/Mock Internal Data
    try:
        df = pd.read_csv("georgetown_inn_data.csv")
        df["Date"] = pd.to_datetime(df["Date"])
    except FileNotFoundError:
        # Create dummy data if file is missing for demo purposes
        dates = pd.date_range(start="2026-01-01", end="2026-03-11")
        df = pd.DataFrame({
            "Date": dates,
            "Room_Revenue": np.random.randint(4000, 8000, len(dates)),
            "Rooms_Sold": np.random.randint(15, 25, len(dates)),
            "Total_Rooms": [30]*len(dates),
            "Market_Occ": np.random.uniform(0.6, 0.8, len(dates)),
            "Market_ADR": np.random.uniform(400, 550, len(dates)),
            "Lat": [38.9055]*len(dates),
            "Lon": [-77.0620]*len(dates)
        })

    # Basic Metrics Calculations
    df["ADR"] = df["Room_Revenue"] / df["Rooms_Sold"]
    df["Occupancy"] = df["Rooms_Sold"] / df["Total_Rooms"]
    df["RevPAR"] = df["Room_Revenue"] / df["Total_Rooms"]
    df["MPI"] = (df["Occupancy"] / df["Market_Occ"]) * 100
    df["RGI"] = (df["RevPAR"] / (df["Market_ADR"] * df["Market_Occ"])) * 100
    
    return df, comp, events

df, comp, events = load_data()

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.markdown("## Asher Jannu")
    st.markdown("### **Revenue Analyst**")
    st.markdown("---")
    start_date, end_date = st.date_input("Select Date Range", [df["Date"].min(), df["Date"].max()])
    st.header("Control Panel")

# Filtered Data
filtered = df[(df["Date"] >= pd.to_datetime(start_date)) & (df["Date"] <= pd.to_datetime(end_date))]
comp_filtered = comp[(comp["Date"] >= pd.to_datetime(start_date)) & (comp["Date"] <= pd.to_datetime(end_date))]

# -----------------------------
# Main Dashboard
# -----------------------------
st.title("🏨 Georgetown Inn | Revenue Management")

# KPI Row
c1, c2, c3, c4 = st.columns(4)
c1.metric("Average ADR", f"${filtered['ADR'].mean():.2f}")
c2.metric("Occupancy", f"{filtered['Occupancy'].mean()*100:.1f}%")
c3.metric("RevPAR", f"${filtered['RevPAR'].mean():.2f}")
c4.metric("Market Share (RGI)", f"{filtered['RGI'].mean():.1f}")

# -----------------------------
# Predictive Analysis (90 Days)
# -----------------------------
st.write("---")
st.header("📈 90-Day Predictive Analysis")

# Calculate 90-day forecast based on Competitor Trends + Event Weighting
last_date = df["Date"].max()
future_dates = pd.date_range(start=last_date + timedelta(days=1), periods=90)
avg_comp_future = comp[comp["Date"].isin(future_dates)].groupby("Date")["Rate"].mean().reindex(future_dates).fillna(method='ffill')

forecast_df = pd.DataFrame({"Date": future_dates, "Market_Trend": avg_comp_future.values})
forecast_df = forecast_df.merge(events, on="Date", how="left").fillna({"Impact_Level": "None"})

# Pricing Logic: Trend + Event Boost
event_multipliers = {"High": 1.25, "Medium": 1.10, "Low": 1.05, "None": 1.0}
forecast_df["Predicted_ADR"] = forecast_df.apply(
    lambda x: x["Market_Trend"] * event_multipliers[x["Impact_Level"]], axis=1
)

# Plotting Forecast
fig_forecast = go.Figure()
fig_forecast.add_trace(go.Scatter(x=forecast_df["Date"], y=forecast_df["Predicted_ADR"], name="Predicted ADR", line=dict(color='#1f77b4', width=3)))
fig_forecast.add_trace(go.Scatter(x=forecast_df["Date"], y=forecast_df["Market_Trend"], name="Market Baseline", line=dict(dash='dash', color='gray')))

# Annotate Events
for idx, row in forecast_df[forecast_df["Impact_Level"] != "None"].iterrows():
    fig_forecast.add_annotation(x=row["Date"], y=row["Predicted_ADR"], text=row["Event"], showarrow=True, arrowhead=1)

st.plotly_chart(fig_forecast, use_container_width=True)

# -----------------------------
# Heatmaps Section
# -----------------------------
col_h1, col_h2 = st.columns(2)

with col_h1:
    st.write("### 🗓️ Forward Rate Intensity")
    # Calendar Heatmap logic: Weekday vs Week Number
    forecast_df['Weekday'] = forecast_df['Date'].dt.day_name()
    forecast_df['WeekNo'] = forecast_df['Date'].dt.isocalendar().week
    pivot_heat = forecast_df.pivot_table(index='Weekday', columns='WeekNo', values='Predicted_ADR')
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    pivot_heat = pivot_heat.reindex(day_order)
    
    fig_heat = px.imshow(pivot_heat, color_continuous_scale="Viridis", labels=dict(color="Rate ($)"))
    st.plotly_chart(fig_heat, use_container_width=True)

with col_h2:
    st.write("### 📍 Geographic Demand")
    m2 = folium.Map(location=[38.9055,-77.0620], zoom_start=4)
    heat_data = df[["Lat","Lon"]].dropna().values.tolist()
    HeatMap(heat_data).add_to(m2)
    st_folium(m2, width=600, height=400)

# -----------------------------
# AI Pricing Engine & Events
# -----------------------------
st.write("---")
cp1, cp2 = st.columns([2, 1])

with cp1:
    st.write("### 🤖 Smart Pricing Recommendations")
    target_date = st.date_input("Check Recommendation for Date:", last_date + timedelta(days=5))
    
    # Analyze the target date
    day_event = events[events["Date"] == pd.to_datetime(target_date)]
    comp_at_date = comp[comp["Date"] == pd.to_datetime(target_date)]["Rate"].mean()
    
    base_price = comp_at_date if not np.isnan(comp_at_date) else df["ADR"].mean()
    
    if not day_event.empty:
        impact = day_event.iloc[0]["Impact_Level"]
        event_name = day_event.iloc[0]["Event"]
        rec_price = base_price * event_multipliers[impact]
        st.success(f"**Event Detected:** {event_name} ({impact} Impact)")
        st.metric("Suggested Rate", f"${rec_price:.0f}", delta=f"{((rec_price/base_price)-1)*100:.1f}% vs Market")
    else:
        st.info("No major events detected for this date. Aligning with market baseline.")
        st.metric("Suggested Rate", f"${base_price:.0f}")

with cp2:
    st.write("### 🚩 Upcoming High-Impact Events")
    upcoming = events[events["Date"] >= pd.to_datetime(last_date)].sort_values("Date").head(5)
    for _, row in upcoming.iterrows():
        st.markdown(f"""
        <div class="event-card">
            <strong>{row['Date'].strftime('%b %d')}</strong>: {row['Event']}<br>
            <small>Impact: {row['Impact_Level']}</small>
        </div>
        """, unsafe_allow_html=True)
