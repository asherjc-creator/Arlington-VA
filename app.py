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
from datetime import datetime, timedelta

# -----------------------------
# Helper Functions
# -----------------------------
def get_image_base64(image_path):
    try:
        img = Image.open(image_path)
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    except Exception:
        return ""

# -----------------------------
# Page configuration
# -----------------------------
st.set_page_config(page_title="Georgetown Inn Revenue Portal", layout="wide", page_icon="🏨")

st.markdown("""
<style>
.main { background-color:#f5f7f9; }
.stMetric { background-color:white; padding:15px; border-radius:10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
.event-card { padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 5px solid #007bff; background: #ffffff; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Data Loading & Cleaning
# -----------------------------
@st.cache_data
def load_all_data():
    # 1. Competitor Rates
    comp = pd.read_csv("competitor_rates.csv")
    comp = comp[comp["Date"] != "Date"]
    comp["Date"] = pd.to_datetime(comp["Date"], errors='coerce')
    comp["Rate"] = pd.to_numeric(comp["Rate"], errors='coerce')
    comp = comp.dropna(subset=["Date", "Rate"])
    
    # 2. Events (with fallback)
    try:
        events = pd.read_csv("events_dc.csv")
        events["Date"] = pd.to_datetime(events["Date"], errors='coerce')
    except FileNotFoundError:
        events = pd.DataFrame([{"Date": "2026-07-04", "Event": "Independence Day", "Impact_Level": "High"}])
        events["Date"] = pd.to_datetime(events["Date"])
    
    # 3. Internal Data
    try:
        df = pd.read_csv("georgetown_inn_data.csv")
        df["Date"] = pd.to_datetime(df["Date"], errors='coerce')
        for col in ["Room_Revenue", "Rooms_Sold", "Total_Rooms", "Market_Occ", "Market_ADR"]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    except FileNotFoundError:
        dates = pd.date_range(start=comp["Date"].min(), end=comp["Date"].max())
        df = pd.DataFrame({
            "Date": dates,
            "Room_Revenue": np.random.randint(5000, 9000, len(dates)),
            "Rooms_Sold": np.random.randint(18, 28, len(dates)),
            "Total_Rooms": [30]*len(dates),
            "Market_Occ": np.random.uniform(0.65, 0.85, len(dates)),
            "Market_ADR": np.random.uniform(450, 600, len(dates)),
            "Lat": [38.9055]*len(dates), "Lon": [-77.0620]*len(dates)
        })

    df["ADR"] = df["Room_Revenue"] / df["Rooms_Sold"]
    df["Occupancy"] = df["Rooms_Sold"] / df["Total_Rooms"]
    df["RevPAR"] = df["Room_Revenue"] / df["Total_Rooms"]
    df["MPI"] = (df["Occupancy"] / df["Market_Occ"]) * 100
    df["RGI"] = (df["RevPAR"] / (df["Market_ADR"] * df["Market_Occ"])) * 100
    
    return df, comp, events

df, comp, events = load_all_data()

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.markdown("## Asher Jannu")
    st.markdown("### **Revenue Analyst**")
    st.markdown("---")
    
    # Fixed Date Selection Logic
    date_val = st.date_input("Select Date Range", [df["Date"].min(), df["Date"].max()])
    if isinstance(date_val, list) and len(date_val) == 2:
        start_date, end_date = date_val
    else:
        start_date = end_date = (date_val[0] if isinstance(date_val, list) else date_val)

filtered = df[(df["Date"].dt.date >= start_date) & (df["Date"].dt.date <= end_date)]
comp_filtered = comp[(comp["Date"].dt.date >= start_date) & (comp["Date"].dt.date <= end_date)]

# -----------------------------
# KPI Metrics
# -----------------------------
st.title("🏨 Georgetown Inn Dashboard")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Average ADR", f"${filtered['ADR'].mean():.2f}")
k2.metric("Occupancy", f"{filtered['Occupancy'].mean()*100:.1f}%")
k3.metric("RevPAR", f"${filtered['RevPAR'].mean():.2f}")
k4.metric("Market Share (RGI)", f"{filtered['RGI'].mean():.1f}")

# -----------------------------
# Forecast Logic
# -----------------------------
st.header("📈 90-Day Forecast")
last_data_date = df["Date"].max()
future_dates = pd.date_range(start=last_data_date + timedelta(days=1), periods=90)

# Fixed fillna and reindexing logic
future_baseline = comp.groupby("Date")["Rate"].mean().reindex(future_dates).ffill().fillna(df["ADR"].mean())

forecast_df = pd.DataFrame({"Date": future_dates, "Market_Baseline": future_baseline.values})
forecast_df = forecast_df.merge(events, on="Date", how="left").fillna({"Impact_Level": "None", "Event": "No Major Event"})

multipliers = {"High": 1.25, "Medium": 1.12, "Low": 1.05, "None": 1.0}
forecast_df["Predicted_Rate"] = forecast_df.apply(lambda x: x["Market_Baseline"] * multipliers.get(x["Impact_Level"], 1.0), axis=1)

# Forecast Chart
fig_forecast = go.Figure()
fig_forecast.add_trace(go.Scatter(x=forecast_df["Date"], y=forecast_df["Predicted_Rate"], name="AI Suggested Rate", line=dict(color='#2ca02c', width=4)))
fig_forecast.add_trace(go.Scatter(x=forecast_df["Date"], y=forecast_df["Market_Baseline"], name="Market Baseline", line=dict(dash='dash', color='gray')))
st.plotly_chart(fig_forecast, use_container_width=True)

# -----------------------------
# Heatmaps
# -----------------------------
st.write("### 📅 Pricing & Demand Heatmaps")
h_col1, h_col2 = st.columns(2)
with h_col1:
    forecast_df['Weekday'] = forecast_df['Date'].dt.day_name()
    forecast_df['Week'] = forecast_df['Date'].dt.isocalendar().week
    pivot = forecast_df.pivot_table(index='Weekday', columns='Week', values='Predicted_Rate')
    pivot = pivot.reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])
    st.plotly_chart(px.imshow(pivot, color_continuous_scale="YlOrRd"), use_container_width=True)

with h_col2:
    m_heat = folium.Map(location=[38.9055,-77.0620], zoom_start=12)
    HeatMap(df[["Lat","Lon"]].dropna().values.tolist()).add_to(m_heat)
    st_folium(m_heat, width=600, height=350)import streamlit as st

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

from datetime import datetime, timedelta


# -----------------------------

# Helper Functions

# -----------------------------

def get_image_base64(image_path):

    """Loads an image and converts it to a base64 string for HTML embed."""

    try:

        img = Image.open(image_path)

        buffered = BytesIO()

        img.save(buffered, format="PNG")

        img_str = base64.b64encode(buffered.getvalue()).decode()

        return f"data:image/png;base64,{img_str}"

    except Exception:

        return ""


# -----------------------------

# Page configuration

# -----------------------------

st.set_page_config(

    page_title="Georgetown Inn Revenue Portal",

    layout="wide",

    page_icon="🏨"

)


# -----------------------------

# Custom Styling

# -----------------------------

st.markdown("""

<style>

.main { background-color:#f5f7f9; }

.stMetric {

    background-color:white;

    padding:15px;

    border-radius:10px;

    box-shadow: 2px 2px 5px rgba(0,0,0,0.05);

}

[data-testid="stSidebar"] { background-color: #ffffff; }

[data-testid="stSidebar"] .stMarkdown { text-align: center; }

.title-container {

    display: flex;

    align-items: center;

    gap: 20px;

    margin-bottom: 20px;

}

.event-card {

    padding: 12px;

    border-radius: 8px;

    margin-bottom: 10px;

    border-left: 5px solid #007bff;

    background: #ffffff;

    box-shadow: 0 2px 4px rgba(0,0,0,0.05);

}

</style>

""", unsafe_allow_html=True)


# -----------------------------

# Data Loading & Cleaning

# -----------------------------

@st.cache_data

def load_all_data():

    # 1. Load Competitor Rates

    comp = pd.read_csv("competitor_rates.csv")

    comp = comp[comp["Date"] != "Date"] # Clean duplicate headers

    comp["Date"] = pd.to_datetime(comp["Date"], errors='coerce')

    comp["Rate"] = pd.to_numeric(comp["Rate"], errors='coerce')

    comp = comp.dropna(subset=["Date", "Rate"])

    

    # 2. Load Events

    events = pd.read_csv("events_dc.csv")

    events = events[events["Date"] != "Date"]

    events["Date"] = pd.to_datetime(events["Date"], errors='coerce')

    events = events.dropna(subset=["Date"])

    

    # 3. Load Internal Data (with Fallback)

    try:

        df = pd.read_csv("georgetown_inn_data.csv")

        df = df[df["Date"] != "Date"]

        df["Date"] = pd.to_datetime(df["Date"], errors='coerce')

        for col in ["Room_Revenue", "Rooms_Sold", "Total_Rooms", "Market_Occ", "Market_ADR"]:

            if col in df.columns:

                df[col] = pd.to_numeric(df[col], errors='coerce')

        df = df.dropna(subset=["Date"])

    except FileNotFoundError:

        # Generate dummy data for the sake of dashboard continuity if file is missing

        dates = pd.date_range(start=comp["Date"].min(), periods=60)

        df = pd.DataFrame({

            "Date": dates,

            "Room_Revenue": np.random.randint(5000, 9000, len(dates)),

            "Rooms_Sold": np.random.randint(18, 28, len(dates)),

            "Total_Rooms": [30]*len(dates),

            "Market_Occ": np.random.uniform(0.65, 0.85, len(dates)),

            "Market_ADR": np.random.uniform(450, 600, len(dates)),

            "Lat": [38.9055]*len(dates),

            "Lon": [-77.0620]*len(dates)

        })


    # Core Performance Metrics

    df["ADR"] = df["Room_Revenue"] / df["Rooms_Sold"]

    df["Occupancy"] = df["Rooms_Sold"] / df["Total_Rooms"]

    df["RevPAR"] = df["Room_Revenue"] / df["Total_Rooms"]

    df["MPI"] = (df["Occupancy"] / df["Market_Occ"]) * 100

    df["RGI"] = (df["RevPAR"] / (df["Market_ADR"] * df["Market_Occ"])) * 100

    

    return df, comp, events


df, comp, events = load_all_data()


# -----------------------------

# Sidebar Profile & Control

# -----------------------------

asher_pic_base64 = get_image_base64("asher_picture.png")

github_url = "https://github.com/asherjc-creator/georgetown-revenue-dashboard"


with st.sidebar:

    if asher_pic_base64:

        st.markdown(f'<img src="{asher_pic_base64}" style="border-radius: 50%; width: 140px; height: 140px; object-fit: cover; display: block; margin: 0 auto 10px auto; border: 3px solid #eee;">', unsafe_allow_html=True)


    st.markdown("## Asher Jannu")

    st.markdown("### **Revenue Analyst**")

    st.markdown(f'<a href="{github_url}" target="_blank"><button style="background-color: #24292e; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; width: 100%;">View GitHub Code</button></a>', unsafe_allow_html=True)

    st.markdown("---")

    

    st.header("Control Panel")

    date_range = st.date_input("Select Date Range", [df["Date"].min(), df["Date"].max()])

    if len(date_range) == 2:

        start_date, end_date = date_range

    else:

        start_date = end_date = date_range[0]


# Filter Data based on Sidebar

filtered = df[(df["Date"] >= pd.to_datetime(start_date)) & (df["Date"] <= pd.to_datetime(end_date))]

comp_filtered = comp[(comp["Date"] >= pd.to_datetime(start_date)) & (comp["Date"] <= pd.to_datetime(end_date))]


# -----------------------------

# Header / Title Section

# -----------------------------

logo_base64 = get_image_base64("logo.png")

if logo_base64:

    st.markdown(f'<div class="title-container"><img src="{logo_base64}" style="width: 120px;"><div style="flex-grow: 1;"><h1 style="margin: 0; color: #333;">Georgetown Inn</h1><h3 style="margin: 0; color: #666; font-weight: normal;">Revenue Management Dashboard</h3></div></div>', unsafe_allow_html=True)

else:

    st.title("🏨 Georgetown Inn | Revenue Dashboard")


# -----------------------------

# KPI Metrics Row

# -----------------------------

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

kpi1.metric("Average ADR", f"${filtered['ADR'].mean():.2f}")

kpi2.metric("Occupancy", f"{filtered['Occupancy'].mean()*100:.1f}%")

kpi3.metric("RevPAR", f"${filtered['RevPAR'].mean():.2f}")

kpi4.metric("Market Share (RGI)", f"{filtered['RGI'].mean():.1f}")


# -----------------------------

# Main Charts

# -----------------------------

c1, c2 = st.columns(2)

with c1:

    st.write("### Revenue & RevPAR Trend")

    fig = px.line(filtered, x="Date", y=["Room_Revenue", "RevPAR"], title="Daily Performance History", color_discrete_sequence=['#1f77b4', '#ff7f0e'])

    st.plotly_chart(fig, use_container_width=True)


with c2:

    st.write("### Market Penetration (MPI)")

    fig2 = px.bar(filtered, x="Date", y="MPI", color="MPI", color_continuous_scale="RdYlGn", title="Occupancy vs. Market Average")

    st.plotly_chart(fig2, use_container_width=True)


st.write("### Competitor Rate Benchmarking")

fig_comp = px.line(comp_filtered, x="Date", y="Rate", color="Hotel", title="Direct Competitor Daily Rates")

st.plotly_chart(fig_comp, use_container_width=True)


# -----------------------------

# 📈 90-Day Predictive Analysis

# -----------------------------

st.write("---")

st.header("📈 90-Day Forecast & Predictive Pricing")


# Prediction logic

last_data_date = df["Date"].max()

future_dates = pd.date_range(start=last_data_date + timedelta(days=1), periods=90)


# Use competitor averages as a future baseline

future_baseline = comp[comp["Date"].isin(future_dates)].groupby("Date")["Rate"].mean().reindex(future_dates).fillna(method='ffill').fillna(df["ADR"].mean())

forecast_df = pd.DataFrame({"Date": future_dates, "Market_Baseline": future_baseline.values})

forecast_df = forecast_df.merge(events, on="Date", how="left").fillna({"Impact_Level": "None", "Event": "No Major Event"})


# Weighting Logic

multipliers = {"High": 1.25, "Medium": 1.12, "Low": 1.05, "None": 1.0}

forecast_df["Predicted_Rate"] = forecast_df.apply(lambda x: x["Market_Baseline"] * multipliers[x["Impact_Level"]], axis=1)


# Forecast Chart

fig_forecast = go.Figure()

fig_forecast.add_trace(go.Scatter(x=forecast_df["Date"], y=forecast_df["Predicted_Rate"], name="AI Suggested Rate", line=dict(color='#2ca02c', width=4)))

fig_forecast.add_trace(go.Scatter(x=forecast_df["Date"], y=forecast_df["Market_Baseline"], name="Market Baseline", line=dict(dash='dash', color='gray')))


# Annotate Top Events on Chart

high_impact = forecast_df[forecast_df["Impact_Level"] == "High"]

for idx, row in high_impact.iterrows():

    fig_forecast.add_annotation(x=row["Date"], y=row["Predicted_Rate"], text=row["Event"], showarrow=True, arrowhead=1)


st.plotly_chart(fig_forecast, use_container_width=True)


# -----------------------------

# Heatmaps Section

# -----------------------------

st.write("### 📅 Pricing & Demand Heatmaps")

h_col1, h_col2 = st.columns(2)


with h_col1:

    st.write("#### Temporal Rate Intensity")

    forecast_df['Weekday'] = forecast_df['Date'].dt.day_name()

    forecast_df['Week'] = forecast_df['Date'].dt.isocalendar().week

    pivot = forecast_df.pivot_table(index='Weekday', columns='Week', values='Predicted_Rate')

    pivot = pivot.reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])

    fig_h = px.imshow(pivot, color_continuous_scale="YlOrRd", labels=dict(color="Rate ($)"))

    st.plotly_chart(fig_h, use_container_width=True)


with h_col2:

    st.write("#### Guest Origin (Geographic Heatmap)")

    m_heat = folium.Map(location=[38.9055,-77.0620], zoom_start=4)

    heat_data = df[["Lat","Lon"]].dropna().values.tolist()

    HeatMap(heat_data).add_to(m_heat)

    st_folium(m_heat, width=600, height=350)


# -----------------------------

# AI Engine & Events Feed

# -----------------------------

st.write("---")

f_col1, f_col2 = st.columns([2, 1])


with f_col1:

    st.write("### 🤖 AI Pricing Recommendation Engine")

    check_date = st.date_input("Query a Specific Future Date:", last_data_date + timedelta(days=7))

    target_row = forecast_df[forecast_df["Date"] == pd.to_datetime(check_date)]

    

    if not target_row.empty:

        row = target_row.iloc[0]

        rec_price = row["Predicted_Rate"]

        base = row["Market_Baseline"]

        event = row["Event"]

        impact = row["Impact_Level"]

        

        st.metric(f"Recommended ADR for {check_date.strftime('%b %d')}", f"${rec_price:.0f}", 

                  delta=f"{((rec_price/base)-1)*100:.1f}% Yield Increase")

        

        if impact != "None":

            st.info(f"**Event Factor:** {event} is driving high demand ({impact} Impact).")

        else:

            st.write("Recommendation based on standard market trends.")

    else:

        st.warning("Selected date is outside the 90-day forecast range.")


with f_col2:

    st.write("### 🚩 Upcoming DC Events")

    upcoming = events[events["Date"] >= pd.to_datetime(datetime.now())].sort_values("Date").head(5)

    if upcoming.empty:

        st.write("No upcoming events found in database.")

    else:

        for _, row in upcoming.iterrows():

            st.markdown(f"""

            <div class="event-card">

                <strong>{row['Date'].strftime('%b %d, %Y')}</strong><br>

                {row['Event']} <br>

                <span style="color: {'#d9534f' if row['Impact_Level'] == 'High' else '#f0ad4e'}; font-weight: bold;">

                    Impact: {row['Impact_Level']}

                </span>

            </div>

            """, unsafe_allow_html=True)


