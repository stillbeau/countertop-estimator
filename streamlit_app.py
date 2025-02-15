import os
import pandas as pd
import streamlit as st
import requests
from io import BytesIO
import json

# ✅ GitHub RAW File URL (Your Excel Data)
file_url = "https://raw.githubusercontent.com/stillbeau/countertop-estimator/main/deadfeb.xlsx"

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
    st.session_state.selected_thickness = "3 cm"  # ✅ Default thickness to 3 cm

# ✅ Load and clean the Excel file
@st.cache_data
def load_data():
    """Load slab data from the Excel sheet."""
    try:
        response = requests.get(file_url, timeout=10)
        if response.status_code != 200:
            st.error(f"⚠️ Error loading file: HTTP {response.status_code}")
            return None

        xls = pd.ExcelFile(BytesIO(response.content), engine="openpyxl")
        df = pd.read_excel(xls, sheet_name='Sheet1')

        # ✅ Clean column names (remove hidden spaces)
        df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=True)

        # ✅ Extract Material, Color, Thickness, and Serial Number
        df[['Material', 'Color_Thickness']] = df['Product Variant'].str.split(' - ', n=1, expand=True)
        df[['Color', 'Thickness']] = df['Color_Thickness'].str.rsplit(' ', n=1, expand=True)
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
            "SQ FT PRICE": "mean",
            "Serial Number": lambda x: ', '.join(map(str, x.dropna().unique()))  # ✅ Combine Serial Numbers
        })

        # ✅ Store DataFrame in session state
        st.session_state.df_inventory = df_grouped

        return df_grouped

    except Exception as e:
        st.error(f"❌ Error loading the file: {e}")
        return None

# Load the data if not already loaded
if st.session_state.df_inventory.empty:
    df_inventory = load_data()
else:
    df_inventory = st.session_state.df_inventory

# ✅ Show Full Cost Breakdown
with st.expander("🧐 Show Full Cost Breakdown"):
    st.markdown(
        f"""
        **Material Cost:** ${material_cost:.2f}  
        **Fabrication Cost:** ${fabrication_cost:.2f}  
        **IB Cost:** ${ib_cost:.2f}  
        **Installation Cost:** ${install_cost:.2f}  
        **Total Sale Price:** ${sale_price:.2f}  
        **Slab Serial Number(s):** {serial_numbers}  
        """
    )
