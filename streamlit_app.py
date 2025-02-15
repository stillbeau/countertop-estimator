import os
import pandas as pd
import streamlit as st
import requests
import json
import re
from io import BytesIO

# ✅ Google Sheets URLs for Vernon & Abbotsford Inventory
VERNON_SHEET_ID = "17uClLZ2FpynR6Qck_Vq-OkLetvxGv_w0VLQFVct0GHQ"
ABBOTSFORD_SHEET_ID = "1KO_O43o5y8O5NF9X6hxYiQFxSJPAJm6-2gcOXgCRPMg"

BASE_GOOGLE_SHEETS_URL = "https://docs.google.com/spreadsheets/d/{}/gviz/tq?tqx=out:csv"

# ✅ Function to Load Inventory Data
@st.cache_data
def load_data(sheet_id):
    """Load slab data from Google Sheets."""
    try:
        file_url = BASE_GOOGLE_SHEETS_URL.format(sheet_id)
        df = pd.read_csv(file_url)

        if df.empty:
            st.error("⚠️ Data failed to load. Check if the sheet is public.")
            return None

        # ✅ Debug: Show available columns
        st.write("📊 **Loaded Columns:**", df.columns.tolist())

        # ✅ Clean column names
        df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=True)

        # ✅ Ensure required columns exist
        required_columns = ["Product", "Available Qty", "Serialized On Hand Cost", "Serial Number"]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            st.error(f"⚠️ Missing required columns: {missing_columns}")
            return None

        return df  # ✅ Return raw data for now (debugging)

    except Exception as e:
        st.error(f"❌ Error loading the file: {e}")
        return None

# 🎨 **Select Location**
st.sidebar.header("📍 Select Location")
location = st.sidebar.radio("Choose a location:", ["Vernon", "Abbotsford"])

# ✅ Load inventory based on selected location
if location == "Vernon":
    df_inventory = load_data(VERNON_SHEET_ID)
else:
    df_inventory = load_data(ABBOTSFORD_SHEET_ID)

# ✅ Handle case where data didn't load
if df_inventory is None:
    st.error("❌ Data not available. Please check your Google Sheet settings.")
    st.stop()