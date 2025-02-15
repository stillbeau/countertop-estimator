import os
import pandas as pd
import streamlit as st
import requests
import json
from io import BytesIO

# ✅ Google Sheets URLs for Vernon & Abbotsford Inventory
VERNON_SHEET_ID = "17uClLZ2FpynR6Qck_Vq-OkLetvxGv_w0VLQFVct0GHQ"
ABBOTSFORD_SHEET_ID = "1KO_O43o5y8O5NF9X6hxYiQFxSJPAJm6-2gcOXgCRPMg"

BASE_GOOGLE_SHEETS_URL = "https://docs.google.com/spreadsheets/d/{}/gviz/tq?tqx=out:csv"

# 🔑 Admin Password
ADMIN_PASSWORD = "floform2024"

# 🔄 **Settings File to Persist Admin Rates**
SETTINGS_FILE = "settings.json"

# ✅ **Function to Load Saved Settings**
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {"fab_cost": 23, "install_cost": 23, "ib_margin": 0.15, "sale_margin": 0.15}

# ✅ **Function to Save Settings**
def save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump({
            "fab_cost": st.session_state.fab_cost,
            "install_cost": st.session_state.install_cost,
            "ib_margin": st.session_state.ib_margin,
            "sale_margin": st.session_state.sale_margin
        }, f)

# ✅ Load saved settings if they exist
saved_settings = load_settings()

# ✅ **Ensure Session State Variables Exist**
if "fab_cost" not in st.session_state:
    st.session_state.fab_cost = float(saved_settings["fab_cost"])
if "install_cost" not in st.session_state:
    st.session_state.install_cost = float(saved_settings["install_cost"])
if "ib_margin" not in st.session_state:
    st.session_state.ib_margin = float(saved_settings["ib_margin"])
if "sale_margin" not in st.session_state:
    st.session_state.sale_margin = float(saved_settings["sale_margin"])
if "admin_access" not in st.session_state:
    st.session_state.admin_access = False
if "df_inventory" not in st.session_state:
    st.session_state.df_inventory = pd.DataFrame()
if "selected_color" not in st.session_state:
    st.session_state.selected_color = None
if "selected_thickness" not in st.session_state:
    st.session_state.selected_thickness = "3 cm"  # Default thickness to 3 cm

# ✅ Load and clean the Excel file
@st.cache_data
def load_data(sheet_id):
    """Load slab data from the Google Sheet."""
    try:
        file_url = BASE_GOOGLE_SHEETS_URL.format(sheet_id)
        df = pd.read_csv(file_url)

        # ✅ Clean column names (remove hidden spaces)
        df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=True)

        # ✅ Ensure necessary columns exist
        required_columns = ["Product Variant", "Available Qty", "Serialized On Hand Cost", "Serial Number"]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            st.error(f"⚠️ Missing required columns: {missing_columns}")
            return None

        # ✅ Calculate SQ FT PRICE
        df["SQ FT PRICE"] = df["Serialized On Hand Cost"] / df["Available Qty"]
        df["SQ FT PRICE"] = df["SQ FT PRICE"].fillna(0)  # Replace NaN with 0
        df["SQ FT PRICE"] = df["SQ FT PRICE"].replace([float("inf"), -float("inf")], 0)  # Handle division errors

        # ✅ Extract Material, Color, and Thickness from "Product Variant"
        df[['Material', 'Color_Thickness']] = df['Product Variant'].str.split(' - ', n=1, expand=True)
        df[['Color', 'Thickness']] = df['Color_Thickness'].str.rsplit(' ', 1, expand=True)
        df['Thickness'] = df['Thickness'].str.replace("cm", " cm", regex=False).str.strip()

        # ✅ Filter thickness to only valid options (1.2 cm, 2 cm, 3 cm)
        valid_thicknesses = ["1.2 cm", "2 cm", "3 cm"]
        df = df[df['Thickness'].isin(valid_thicknesses)]

        # ✅ Convert numeric columns
        numeric_cols = ['Available Qty', 'SQ FT PRICE']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # ✅ Store serial numbers in a list for each Color + Thickness combination
        df_grouped = df.groupby(["Color", "Thickness"], as_index=False).agg({
            "Available Qty": "sum",
            "SQ FT PRICE": "max",  # ✅ Use highest price if duplicates exist