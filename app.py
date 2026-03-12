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
import requests
from bs4 import BeautifulSoup

# -----------------------------
# 1. Helper Functions
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

def scrape_booking_rate(hotel_name):
    """Fetches live price for a hotel from Booking.com search results."""
    search_query = f"{hotel_name} Washington DC"
    url = f"https://www.booking.com/searchresults.html?ss={search_query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        price_element = soup.find("span", {"data-testid": "price-and-discounted-price"})
        return price_element.text if price_element else "Rate Hidden"
    except:
        return "N/A"

# -----------------------------
# 2. Page Configuration
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
# 3. Data Loading & Cleaning
# -----------------------------
@st.cache_data(ttl=600)
def load_all_data():
    # 1. Load Competitor Rates
    comp = pd.read_csv("competitor_rates.csv")
    comp = comp[comp["Date"] != "Date"]
    comp["Date"] = pd.to_datetime(comp["Date"], errors='coerce')
    comp["Rate"] = pd.to_numeric(comp["Rate"], errors='coerce')
    comp = comp.dropna(subset=["Date", "Rate"])
    
    # 2. Load Events
    try:
        events = pd.read_csv("events_dc.csv")
        events["Date"] = pd.to_datetime(events["Date"], errors='coerce')
        events = events.dropna(subset=["Date"])
    except FileNotFoundError:
        events = pd.DataFrame([
            {"Date": "2026-03-20", "Event": "Cherry Blossom Festival", "Impact_Level": "High"},
            {"Date": "2026-07-04", "Event": "Independence Day", "Impact_Level": "High"}
        ])
        events["Date"] = pd.to_datetime(events["Date"])
    
    # 3. Load Internal Data
    try:
        df = pd.read_csv("georgetown_inn_data.csv")
        df["Date"] = pd.to_datetime(
