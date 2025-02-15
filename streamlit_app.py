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

        # ✅ Clean column names
        df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=True)

        # ✅ Ensure required columns exist
        required_columns = ["Product", "Available Qty", "Serialized On Hand Cost", "Serial Number"]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            st.error(f"⚠️ Missing required columns: {missing_columns}")
            return None

        # ✅ Extract Brand, Color, and Thickness
        def extract_product_details(product_str):
            """Extracts Brand, Color, and Thickness from Product column."""
            if not isinstance(product_str, str):
                return "Unknown", "Unknown", "Unknown"
            product_str = re.sub(r"^\d+\s*-\s*", "", product_str)  # Remove leading numbers
            product_str = re.sub(r"\(\w+\)", "", product_str).strip()  # Remove "(ABB)"
            brand = product_str.split(" ")[0].strip()
            match = re.search(r"(\d+cm)$", product_str)
            thickness = match.group(1) if match else None
            color = product_str.replace(brand, "").replace(thickness, "").strip() if thickness else product_str[len(brand):].strip()
            return brand, color, thickness.replace("cm", " cm") if thickness else "Unknown"

        df[["Brand", "Color", "Thickness"]] = df["Product"].apply(lambda x: pd.Series(extract_product_details(str(x))))

        # ✅ Filter valid thicknesses
        valid_thicknesses = ["1.2 cm", "2 cm", "3 cm"]
        df = df[df['Thickness'].isin(valid_thicknesses)]

        # ✅ Calculate SQ FT PRICE safely
        df["SQ FT PRICE"] = df["Serialized On Hand Cost"] / df["Available Qty"]
        df["SQ FT PRICE"] = df["SQ FT PRICE"].fillna(0).replace([float("inf"), -float("inf")], 0)

        # ✅ Group by Color & Thickness
        df_grouped = df.groupby(["Color", "Thickness"], as_index=False).agg({
            "Available Qty": "sum",
            "SQ FT PRICE": "max",
            "Serial Number": lambda x: ', '.join(map(str, x.dropna().unique()))
        })

        return df_grouped

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

# 🎨 **Main UI**
st.title("🛠 Countertop Cost Estimator")

square_feet = st.number_input("📐 Square Feet:", min_value=1, step=1)
selected_thickness = st.selectbox("🔲 Thickness:", ["1.2 cm", "2 cm", "3 cm"], index=2)

# Ensure colors exist for the selected thickness
available_colors = df_inventory[df_inventory["Thickness"] == selected_thickness]["Color"].dropna().unique()
selected_color = st.selectbox("🎨 Color:", sorted(available_colors) if len(available_colors) > 0 else [])

if st.button("📊 Estimate Cost"):
    if not selected_color:
        st.error("❌ Please select a valid color.")
    else:
        selected_slab = df_inventory[(df_inventory["Color"] == selected_color) & (df_inventory["Thickness"] == selected_thickness)]
        total_available_sqft = selected_slab["Available Qty"].sum()
        required_sqft = square_feet * 1.2  # Including waste factor

        if required_sqft > total_available_sqft:
            st.error(f"🚨 Not enough material available! ({total_available_sqft} sq ft available, {required_sqft} sq ft needed)")
        else:
            st.success(f"✅ **You have enough material for this job!**")