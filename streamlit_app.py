import os
import pandas as pd
import streamlit as st
import requests
from io import BytesIO
import json
import re

# ✅ Google Sheets URLs
VERNON_SHEET_URL = "https://docs.google.com/spreadsheets/d/17uClLZ2FpynR6Qck_Vq-OkLetvxGv_w0VLQFVct0GHQ/export?format=xlsx"
ABBOTSFORD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1KO_O43o5y8O5NF9X6hxYiQFxSJPAJm6-2gcOXgCRPMg/export?format=xlsx"

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
if "selected_location" not in st.session_state:
    st.session_state.selected_location = "Vernon"

# ✅ **Function to Extract Product Details**
def extract_product_details(product_name):
    if not isinstance(product_name, str):
        return None, None, None, "Polished"  # Default to Polished if missing

    product_name = re.sub(r"^\d+\s*-\s*", "", product_name)  # Remove leading numbers
    brand = product_name.split()[0]  # Extract brand
    product_name = re.sub(r"\(.*?\)", "", product_name).strip()  # Remove location codes
    thickness_match = re.search(r"(\d+\.?\d*)\s*cm", product_name)
    thickness = thickness_match.group(0) if thickness_match else None
    color = product_name.replace(brand, "").replace(thickness if thickness else "", "").strip()
    finishes = ["Matte", "Brushed", "Satin"]
    finish = "Polished"
    for f in finishes:
        if f in color:
            finish = f
            color = color.replace(f, "").strip()
    return brand, color, thickness, finish

# ✅ **Function to Load and Process Google Sheet Data**
@st.cache_data
def load_data(sheet_url):
    try:
        response = requests.get(sheet_url, timeout=10)
        if response.status_code != 200:
            st.error(f"⚠️ Error loading file: HTTP {response.status_code}")
            return None
        xls = pd.ExcelFile(BytesIO(response.content), engine="openpyxl")
        df = pd.read_excel(xls, sheet_name="Sheet1")
        df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=True)
        df[['Brand', 'Color', 'Thickness', 'Finish']] = df['Product'].apply(lambda x: pd.Series(extract_product_details(x)))
        df['SQ FT PRICE'] = df['Serialized On Hand Cost'] / df['Available Qty']
        df = df.dropna(subset=['SQ FT PRICE'])  # Remove invalid rows
        return df
    except Exception as e:
        st.error(f"❌ Error loading the file: {e}")
        return None

# ✅ Load Data Based on Selected Location
if st.session_state.selected_location == "Vernon":
    df_inventory = load_data(VERNON_SHEET_URL)
else:
    df_inventory = load_data(ABBOTSFORD_SHEET_URL)

st.session_state.df_inventory = df_inventory if df_inventory is not None else pd.DataFrame()

# 🎨 **Main UI**
st.title("🛠 Countertop Cost Estimator")
st.session_state.selected_location = st.radio("🌍 Select Location:", ["Vernon", "Abbotsford"])
square_feet = st.number_input("📐 Square Feet:", min_value=1, step=1)
selected_thickness = st.selectbox("🔲 Thickness:", ["1.2 cm", "2 cm", "3 cm"], index=2)
available_colors = df_inventory[df_inventory["Thickness"] == selected_thickness]["Color"].dropna().unique()
selected_color = st.selectbox("🎨 Color:", sorted(available_colors) if len(available_colors) > 0 else [])

if st.button("📊 Estimate Cost"):
    if not selected_color:
        st.error("❌ Please select a valid color.")
    else:
        selected_slab = df_inventory[(df_inventory["Color"] == selected_color) & (df_inventory["Thickness"] == selected_thickness)]
        total_available_sqft = selected_slab["Available Qty"].sum()
        required_sqft = square_feet * 1.2
        if required_sqft > total_available_sqft:
            st.error(f"🚨 Not enough material available! ({total_available_sqft} sq ft available, {required_sqft} sq ft needed)")
        else:
            sq_ft_price = selected_slab.iloc[0]["SQ FT PRICE"]
            material_cost = required_sqft * sq_ft_price
            fabrication_cost = st.session_state.fab_cost * required_sqft
            install_cost = st.session_state.install_cost * required_sqft
            ib_cost = (material_cost + fabrication_cost) * (1 + st.session_state.ib_margin)
            sale_price = (ib_cost + install_cost) * (1 + st.session_state.sale_margin)
            st.success(f"💰 **Estimated Sale Price: ${sale_price:.2f}**")