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
    """Load slab data from Google Sheets and clean column names."""
    try:
        file_url = BASE_GOOGLE_SHEETS_URL.format(sheet_id)
        df = pd.read_csv(file_url)

        if df.empty:
            st.error("⚠️ Data failed to load. Check if the sheet is public.")
            return None

        # ✅ Debug: Show raw column names
        st.write("📊 **Raw Loaded Columns:**", df.columns.tolist())

        # ✅ Clean column names (remove spaces & hidden characters)
        df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=True)

        # ✅ Expected column mappings
        column_mappings = {
            "Product Variant": "Product",
            "Available Qty": "Available Qty",
            "Serialized On Hand Cost": "Serialized On Hand Cost",
            "Serial Number": "Serial Number"
        }

        # ✅ Rename columns if they exist in the raw data
        df.rename(columns=column_mappings, inplace=True)

        # ✅ Show final column names for debugging
        st.write("📊 **Final Cleaned Columns:**", df.columns.tolist())

        # ✅ Ensure required columns exist
        required_columns = ["Product", "Available Qty", "Serialized On Hand Cost", "Serial Number"]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            st.error(f"⚠️ Missing required columns after cleaning: {missing_columns}")
            return None

        return df  # ✅ Return cleaned data

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