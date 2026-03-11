import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
import base64
from io import BytesIO
from PIL import Image

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
    except FileNotFoundError:
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
# Styling
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
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Sidebar Profile Section
# -----------------------------
asher_pic_base64 = get_image_base64("GTINN.jpeg") # Using uploaded profile pic
github_url = "https://github.com/asherjc-creator/georgetown-revenue-dashboard"

with st.sidebar:
    if asher_pic_base64:
        st.markdown(f"""
            <img src="{asher_pic_base64}" 
                 style="border-radius: 50%; width: 150px; height: 150px; object-fit: cover; display: block; margin-left: auto; margin-right: auto; border: 3px solid #eee;">
        """, unsafe_allow_html=True)

    st.markdown("## Asher Jannu")
    st.markdown("### **Revenue Analyst**")
    st.markdown("---")
    st.markdown("#### Code Repository")
    st.markdown(f'<a href="{github_url}" target="_blank" style="text-decoration: none;"><button style="background-color: #24292e; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 16px;">View on GitHub</button></a>', unsafe_allow_html=True)
    st.markdown("---")
    st.header("Control Panel")

# -----------------------------
# Header / Title Section
# -----------------------------
logo_base64 = get_image_base64("GTINN.jpeg")

if logo_base64:
    st.markdown(f"""
    <div class="title-container">
        <img src="{logo_base64}" style="width: 150px; height: auto; border-radius: 5px;">
        <div style="flex-grow: 1;">
            <h1 style="margin: 0; color: #333;">Georgetown Inn</h1>
            <h3 style="margin: 5px 0 0 0; color: #555; font-weight: normal;">Revenue Management Dashboard</h3>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.title("🏨 Georgetown Inn | Revenue Management Dashboard")

# -----------------------------
# Load Data
# -----------------------------
df = pd.read_csv("georgetown_inn_data.csv")
df["Date"] = pd.to_datetime(df["Date"])

comp = pd.read_csv("competitor_rates.csv")
comp["Date"] = pd.to_datetime(comp["Date"])

# -----------------------------
# Calculations
# -----------------------------
df["ADR"] = df["Room_Revenue"] / df["Rooms_Sold"]
df["Occupancy"] = df["Rooms_Sold"] / df["Total_Rooms"]
df["RevPAR"] = df["Room_Revenue"] / df["Total_Rooms"]

# Market benchmarking
df["MPI"] = (df["Occupancy"] / df["Market_Occ"]) * 100
df["RGI"] = (df["RevPAR"] / (df["Market_ADR"] * df["Market_Occ"])) * 100

# -----------------------------
# Sidebar filters
# -----------------------------
start_date, end_date = st.sidebar.date_input(
    "Select Date Range",
    [df["Date"].min(), df["Date"].max()]
)

filtered = df[(df["Date"] >= pd.to_datetime(start_date)) &
              (df["Date"] <= pd.to_datetime(end_date))]

comp_filtered = comp[(comp["Date"] >= pd.to_datetime(start_date)) &
                     (comp["Date"] <= pd.to_datetime(end_date))]

# -----------------------------
# KPI Metrics
# -----------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Average ADR", f"${filtered['ADR'].mean():.2f}")
col2.metric("Occupancy", f"{filtered['Occupancy'].mean()*100:.1f}%")
col3.metric("RevPAR", f"${filtered['RevPAR'].mean():.2f}")
col4.metric("Revenue Generation Index", f"{filtered['RGI'].mean():.1f}")

# -----------------------------
# Charts Section
# -----------------------------
c1, c2 = st.columns(2)
with c1:
    st.write("### Revenue & RevPAR Trend")
    fig = px.line(filtered, x="Date", y=["Room_Revenue","RevPAR"], title="Daily Performance")
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.write("### Market Penetration Index (MPI)")
    fig2 = px.bar(filtered, x="Date", y="MPI", color="MPI", color_continuous_scale="RdYlGn", title="Market Share Performance")
    st.plotly_chart(fig2, use_container_width=True)

# -----------------------------
# Competitor Rate Comparison
# -----------------------------
st.write("### Competitor Rate Comparison")
fig_comp = px.line(comp_filtered, x="Date", y="Rate", color="Hotel", title="Georgetown Competitive Rate Index")
st.plotly_chart(fig_comp, use_container_width=True)

# -----------------------------
# Map Sections
# -----------------------------
col_map1, col_map2 = st.columns(2)

with col_map1:
    st.write("### Competitive Landscape")
    m = folium.Map(location=[38.9055,-77.0620], zoom_start=15)
    folium.Marker([38.9055,-77.0620], popup="Georgetown Inn", icon=folium.Icon(color="blue")).add_to(m)
    
    competitors = [
        {"name":"Four Seasons DC","loc":[38.9052,-77.0581]},
        {"name":"Rosewood Washington DC","loc":[38.9045,-77.0625]},
        {"name":"Ritz Carlton Georgetown","loc":[38.9031,-77.0615]}
    ]
    for c in competitors:
        folium.CircleMarker(location=c["loc"], radius=8, popup=c["name"], color="red", fill=True).add_to(m)
    st_folium(m, width=500, height=400)

with col_map2:
    st.write("### Guest Origin Heatmap")
    # Ensure your CSV has "Lat" and "Lon" columns
    heat_data = df[["Lat","Lon"]].dropna().values.tolist()
    m2 = folium.Map(location=[38.9055,-77.0620], zoom_start=4)
    HeatMap(heat_data).add_to(m2)
    st_folium(m2, width=500, height=400)

# -----------------------------
# AI Pricing Engine (Updated)
# -----------------------------
st.write("### 🤖 AI Pricing Engine")

latest_occ = df["Occupancy"].iloc[-1]
latest_adr = df["ADR"].iloc[-1]

if latest_occ > 0.90:
    suggested_rate = latest_adr * 1.15
    st.success(f"High demand detected. Suggested ADR: ${suggested_rate:.0f}")
elif latest_occ > 0.75:
    suggested_rate = latest_adr * 1.05
    st.info(f"Moderate demand. Suggested ADR: ${suggested_rate:.0f}")
else:
    suggested_rate = latest_adr * 0.92
    st.warning(f"Low demand. Suggested ADR: ${suggested_rate:.0f}")