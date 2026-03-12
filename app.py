import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from datetime import timedelta, datetime
from PIL import Image
import base64
from io import BytesIO

# --------------------------------------------------
# 1. CORE LOGIC (Integrated for reliability)
# --------------------------------------------------

def dynamic_pricing_logic(occupancy, market_adr, event_multiplier=1):
    """Calculates suggested ADR based on occupancy levels."""
    if occupancy > 0.90:
        price = market_adr * 1.20
    elif occupancy > 0.80:
        price = market_adr * 1.10
    elif occupancy > 0.70:
        price = market_adr * 1.05
    else:
        price = market_adr * 0.95
    return price * event_multiplier

# --------------------------------------------------
# 2. PAGE CONFIG & STYLING
# --------------------------------------------------

st.set_page_config(
    page_title="Georgetown Inn Revenue Portal",
    layout="wide",
    page_icon="🏨"
)

st.markdown("""
<style>
.main {background-color:#f5f7f9;}
.stMetric {
    background: white;
    padding: 15px;
    border-radius: 10px;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
}
.event-card {
    padding: 10px;
    border-left: 5px solid #ff4b4b;
    background: white;
    margin-bottom: 8px;
    font-size: 0.9rem;
}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# 3. HELPER FUNCTIONS
# --------------------------------------------------

def get_image_base64(image_path):
    try:
        img = Image.open(image_path)
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}"
    except:
        return ""

# --------------------------------------------------
# 4. DATA LOADING & CLEANING
# --------------------------------------------------

@st.cache_data
def load_data():
    # Load Internal Data
    df = pd.read_csv("georgetown_inn_data.csv")
    df.columns = df.columns.str.strip()
    df["Date"] = pd.to_datetime(df["Date"])
    
    # Core hotel metrics
    df["ADR"] = df["Room_Revenue"] / df["Rooms_Sold"]
    df["Occupancy"] = df["Rooms_Sold"] / df["Total_Rooms"]
    df["RevPAR"] = df["Room_Revenue"] / df["Total_Rooms"]
    df["MPI"] = (df["Occupancy"] / df["Market_Occ"]) * 100
    df["RGI"] = (df["RevPAR"] / (df["Market_ADR"] * df["Market_Occ"])) * 100

    # Load & Clean Competitor Data (Handles duplicate header strings)
    comp = pd.read_csv("competitor_rates.csv")
    comp = comp[comp["Date"].str.contains("/") == True] # Keep only rows with real dates
    comp["Date"] = pd.to_datetime(comp["Date"])
    comp["Rate"] = pd.to_numeric(comp["Rate"], errors='coerce')

    # Load & Clean Events
    try:
        events = pd.read_csv("events_dc.csv")
        events["Date"] = pd.to_datetime(events["Date"])
    except:
        # Fallback if file is missing
        events = pd.DataFrame([
            {"Date": pd.to_datetime("2026-03-20"), "Event": "Cherry Blossom Peak", "Impact_Level": "High"},
            {"Date": pd.to_datetime("2026-07-04"), "Event": "Independence Day", "Impact_Level": "High"}
        ])

    return df, comp, events

df, comp, events = load_data()

# --------------------------------------------------
# 5. SIDEBAR & DATE FILTERING (Fixed TypeError)
# --------------------------------------------------

with st.sidebar:
    profile = get_image_base64("asher_picture.png")
    if profile:
        st.markdown(f'<img src="{profile}" style="border-radius:50%;width:120px;display:block;margin:auto;">', unsafe_allow_html=True)
    
    st.markdown("<h3 style='text-align:center;'>Asher Jannu</h3>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>Revenue Analyst</p>", unsafe_allow_html=True)
    st.markdown("---")

    # Handling the Streamlit Date Input safely
    try:
        date_range = st.date_input(
            "Select Analysis Range",
            [df["Date"].min().date(), df["Date"].max().date()]
        )
        
        if isinstance(date_range, list) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            # Fallback if only one date is clicked or range is incomplete
            start_date = end_date = date_range[0] if isinstance(date_range, list) else date_range
    except Exception:
        start_date = df["Date"].min().date()
        end_date = df["Date"].max().date()

# Apply filters (Comparing date objects to date objects)
filtered = df[(df["Date"].dt.date >= start_date) & (df["Date"].dt.date <= end_date)].copy()
comp_filtered = comp[(comp["Date"].dt.date >= start_date) & (comp["Date"].dt.date <= end_date)]

# --------------------------------------------------
# 6. HEADER & KPIs
# --------------------------------------------------

logo = get_image_base64("logo.png")
if logo:
    st.markdown(f'<div style="display:flex;align-items:center;gap:20px;"><img src="{logo}" width="100"><h1>Georgetown Inn Revenue</h1></div>', unsafe_allow_html=True)
else:
    st.title("🏨 Georgetown Inn Revenue Dashboard")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Avg ADR", f"${filtered['ADR'].mean():.2f}")
c2.metric("Occupancy", f"{filtered['Occupancy'].mean()*100:.1f}%")
c3.metric("RevPAR", f"${filtered['RevPAR'].mean():.2f}")
c4.metric("RGI (Market Share)", f"{filtered['RGI'].mean():.1f}")

st.markdown("---")

# --------------------------------------------------
# 7. VISUAL ANALYTICS
# --------------------------------------------------

row1_col1, row1_col2 = st.columns(2)

with row1_col1:
    st.subheader("📊 Booking Pickup & Revenue")
    filtered["Pickup"] = filtered["Rooms_Sold"].diff().fillna(0)
    fig_rev = px.line(filtered, x="Date", y=["Room_Revenue", "RevPAR"], title="Revenue Trends")
    st.plotly_chart(fig_rev, use_container_width=True)

with row1_col2:
    st.subheader("📈 Market Benchmarking (MPI/RGI)")
    fig_bench = px.line(filtered, x="Date", y=["MPI", "RGI"], title="Index Performance (100 = Fair Share)")
    fig_bench.add_hline(y=100, line_dash="dash", line_color="red")
    st.plotly_chart(fig_bench, use_container_width=True)

row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    st.subheader("📅 Rate Demand Heatmap")
    df["Weekday"] = df["Date"].dt.day_name()
    df["Week"] = df["Date"].dt.isocalendar().week
    pivot = df.pivot_table(index="Weekday", columns="Week", values="ADR")
    # Sort weekdays correctly
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    pivot = pivot.reindex(days)
    fig_heat = px.imshow(pivot, color_continuous_scale="Viridis")
    st.plotly_chart(fig_heat, use_container_width=True)

with row2_col2:
    st.subheader("🏢 Competitor Rate Position")
    fig_comp = px.line(comp_filtered, x="Date", y="Rate", color="Hotel")
    st.plotly_chart(fig_comp, use_container_width=True)

# --------------------------------------------------
# 8. AI FORECAST & PRICING
# --------------------------------------------------

st.markdown("---")
f_col1, f_col2 = st.columns([2, 1])

with f_col1:
    st.subheader("🔮 90-Day ADR Forecast")
    last_date = df["Date"].max()
    future_dates = pd.date_range(last_date + timedelta(days=1), periods=90)
    
    # Calculate baseline using new .ffill() syntax
    avg_market_base = comp.groupby("Date")["Rate"].mean()
    forecast_df = pd.DataFrame({"Date": future_dates})
    forecast_df["Market_Trend"] = avg_market_base.reindex(future_dates).ffill().values
    
    # Apply Multipliers
    forecast_df = forecast_df.merge(events, on="Date", how="left")
    forecast_df["Impact_Level"] = forecast_df["Impact_Level"].fillna("None")
    mults = {"High": 1.25, "Medium": 1.1, "Low": 1.05, "None": 1.0}
    forecast_df["Predicted_ADR"] = forecast_df.apply(lambda x: x["Market_Trend"] * mults[x["Impact_Level"]], axis=1)

    fig_forecast = go.Figure()
    fig_forecast.add_trace(go.Scatter(x=forecast_df["Date"], y=forecast_df["Predicted_ADR"], name="Predicted ADR", line=dict(color='green', width=3)))
    fig_forecast.add_trace(go.Scatter(x=forecast_df["Date"], y=forecast_df["Market_Trend"], name="Market Baseline", line=dict(dash='dash', color='gray')))
    st.plotly_chart(fig_forecast, use_container_width=True)

with f_col2:
    st.subheader("🤖 AI Pricing Engine")
    latest_occ = df["Occupancy"].iloc[-1]
    latest_m_adr = df["Market_ADR"].iloc[-1]
    rec_adr = dynamic_pricing_logic(latest_occ, latest_m_adr)
    
    st.metric("Recommended ADR", f"${rec_adr:.0f}", delta=f"${rec_adr - df['ADR'].iloc[-1]:.2f} vs Last Actual")
    
    st.write("**Upcoming High Impact Events**")
    upcoming = events[events["Date"] >= datetime.now()].sort_values("Date").head(3)
    for _, row in upcoming.iterrows():
        st.markdown(f'<div class="event-card"><b>{row["Date"].strftime("%b %d")}</b>: {row["Event"]} ({row["Impact_Level"]} Impact)</div>', unsafe_allow_html=True)

# --------------------------------------------------
# 9. MAPS
# --------------------------------------------------

st.markdown("---")
st.subheader("📍 Geographic Demand & Competition")
m_col1, m_col2 = st.columns(2)

with m_col1:
    m = folium.Map(location=[38.9055, -77.0620], zoom_start=14)
    folium.Marker([38.9055, -77.0620], popup="Georgetown Inn", icon=folium.Icon(color="blue", icon="home")).add_to(m)
    # Add comps
    comps = [("Four Seasons", [38.9052, -77.0581]), ("Rosewood", [38.9045, -77.0625])]
    for n, l in comps:
        folium.Marker(l, popup=n, icon=folium.Icon(color="red")).add_to(m)
    st_folium(m, width="100%", height=400)

with m_col2:
    m_heat = folium.Map(location=[38.9055, -77.0620], zoom_start=4)
    heat_data = df[["Lat", "Lon"]].dropna().values.tolist()
    HeatMap(heat_data).add_to(m_heat)
    st_folium(m_heat, width="100%", height=400)
