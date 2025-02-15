import os
import pandas as pd
import streamlit as st
import requests
from io import BytesIO
import json

# ✅ Google Sheets Links
SHEET_URLS = {
    "Vernon": "https://docs.google.com/spreadsheets/d/{VERNON_SHEET_ID}/gviz/tq?tqx=out:csv",
    "Abbotsford": "https://docs.google.com/spreadsheets/d/{ABBOTSFORD_SHEET_ID}/gviz/tq?tqx=out:csv"
}

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

# ✅ Load saved settings
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

# ✅ Load and clean the Google Sheets data
@st.cache_data
def load_data(location):
    """Load inventory data from Google Sheets based on selected location."""
    try:
        url = SHEET_URLS.get(location)
        if not url:
            st.error("❌ Invalid location selected.")
            return None

        df = pd.read_csv(url)

        # ✅ Clean column names (remove hidden spaces)
        df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=True)

        # ✅ Extract Brand, Color, Thickness, Finish from "Product"
        df[['Brand', 'Color_Thickness']] = df['Product'].str.extract(r'(\D+?)\s+(.+)')
        df[['Color', 'Thickness']] = df['Color_Thickness'].str.rsplit(' ', 1, expand=True)

        # ✅ Filter thickness to only valid options (1.2 cm, 2 cm, 3 cm)
        valid_thicknesses = ["1.2 cm", "2 cm", "3 cm"]
        df = df[df['Thickness'].isin(valid_thicknesses)]

        # ✅ Ensure numeric conversions
        df["Available Qty"] = pd.to_numeric(df["Available Qty"], errors='coerce').fillna(0)
        df["Serialized On Hand Cost"] = pd.to_numeric(df["Serialized On Hand Cost"], errors='coerce').fillna(0)

        # ✅ Calculate SQ FT PRICE
        df["SQ FT PRICE"] = df["Serialized On Hand Cost"] / df["Available Qty"]
        df["SQ FT PRICE"] = df["SQ FT PRICE"].replace([float('inf'), -float('inf')], 0)

        # ✅ Store serial numbers for each Color + Thickness
        df_grouped = df.groupby(["Color", "Thickness"], as_index=False).agg({
            "Available Qty": "sum",
            "SQ FT PRICE": "mean",
            "Serial Number": lambda x: ', '.join(map(str, x.dropna().unique()))
        })

        return df_grouped

    except Exception as e:
        st.error(f"❌ Error loading the file: {e}")
        return None

# 🎨 **Main UI**
st.title("🛠 Countertop Cost Estimator")

# 🌍 **Select Location**
location = st.selectbox("📍 Select Location:", ["Vernon", "Abbotsford"])
df_inventory = load_data(location)

# 📏 **Square Feet Input**
square_feet = st.number_input("📐 Square Feet:", min_value=1, step=1)
selected_thickness = st.selectbox("🔲 Thickness:", ["1.2 cm", "2 cm", "3 cm"], index=2)

# Ensure colors exist for the selected thickness
if df_inventory is not None:
    available_colors = df_inventory[df_inventory["Thickness"] == selected_thickness]["Color"].dropna().unique()
    selected_color = st.selectbox("🎨 Color:", sorted(available_colors) if len(available_colors) > 0 else [])

# 📊 **Estimate Cost Button**
if st.button("📊 Estimate Cost"):
    if not selected_color or df_inventory is None:
        st.error("❌ Please select a valid color.")
    else:
        selected_slab = df_inventory[(df_inventory["Color"] == selected_color) & (df_inventory["Thickness"] == selected_thickness)]
        total_available_sqft = selected_slab["Available Qty"].sum()
        required_sqft = square_feet * 1.2  # Including waste factor

        if required_sqft > total_available_sqft:
            st.error(f"🚨 Not enough material available! ({total_available_sqft} sq ft available, {required_sqft} sq ft needed)")
        else:
            # ✅ Calculate Costs Based on Square Footage
            sq_ft_price = selected_slab.iloc[0]["SQ FT PRICE"]
            material_cost = required_sqft * sq_ft_price
            fabrication_cost = st.session_state.fab_cost * required_sqft
            install_cost = st.session_state.install_cost * required_sqft
            ib_cost = (material_cost + fabrication_cost) * (1 + st.session_state.ib_margin)
            sale_price = (ib_cost + install_cost) * (1 + st.session_state.sale_margin)

            st.success(f"💰 **Estimated Sale Price: ${sale_price:.2f}**")

            # ✅ Restore Google Search functionality
            query = f"{selected_color} {selected_thickness} countertop"
            google_url = f"https://www.google.com/search?tbm=isch&q={query.replace(' ', '+')}"
            st.markdown(f"🔍 [Click here to view {selected_color} images]({google_url})", unsafe_allow_html=True)

            # ✅ Display **Serial Numbers** in Breakdown
            serial_numbers = selected_slab["Serial Number"].iloc[0] if "Serial Number" in selected_slab.columns else "N/A"

            with st.expander("🧐 Show Full Cost Breakdown"):
                st.markdown(f"""
                - **Material Cost:** ${material_cost:.2f}  
                - **Fabrication Cost:** ${fabrication_cost:.2f}  
                - **IB Cost:** ${ib_cost:.2f}  
                - **Installation Cost:** ${install_cost:.2f}  
                - **Total Sale Price:** ${sale_price:.2f}  
                - **Slab Serial Number(s):** {serial_numbers}  
                """)