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

# ✅ **Ensure Session State Variables Exist**
saved_settings = load_settings()
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
if "selected_edge" not in st.session_state:
    st.session_state.selected_edge = "Summit (3CM)"  # ✅ Default edge profile

# ✅ Load and clean the Excel file
@st.cache_data
def load_data():
    try:
        response = requests.get(file_url, timeout=10)
        if response.status_code != 200:
            st.error(f"⚠️ Error loading file: HTTP {response.status_code}")
            return None
        xls = pd.ExcelFile(BytesIO(response.content), engine="openpyxl")
        df = pd.read_excel(xls, sheet_name='Sheet1')
        df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=True)
        df[['Material', 'Color_Thickness']] = df['Product Variant'].str.split(' - ', n=1, expand=True)
        df[['Color', 'Thickness']] = df['Color_Thickness'].str.rsplit(' ', n=1, expand=True)
        df['Thickness'] = df['Thickness'].str.replace("cm", " cm", regex=False).str.strip()
        valid_thicknesses = ["1.2 cm", "2 cm", "3 cm"]
        df = df[df['Thickness'].isin(valid_thicknesses)]
        numeric_cols = ['Available Qty', 'SQ FT PRICE']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        df_grouped = df.groupby(["Color", "Thickness"], as_index=False).agg({
            "Available Qty": "sum",
            "SQ FT PRICE": "mean",
            "Serial Number": lambda x: ', '.join(map(str, x.dropna().unique()))
        })
        st.session_state.df_inventory = df_grouped
        return df_grouped
    except Exception as e:
        st.error(f"❌ Error loading the file: {e}")
        return None

df_inventory = load_data() if st.session_state.df_inventory.empty else st.session_state.df_inventory

# 🎨 **Main UI**
st.title("🛠 Countertop Cost Estimator")

square_feet = st.number_input("📐 Square Feet:", min_value=1, step=1)
thickness_options = ["1.2 cm", "2 cm", "3 cm"]
st.session_state.selected_thickness = st.selectbox("🔲 Thickness:", thickness_options, index=thickness_options.index(st.session_state.selected_thickness))

available_colors = df_inventory[df_inventory["Thickness"] == st.session_state.selected_thickness]["Color"].dropna().unique()
if len(available_colors) > 0:
    st.session_state.selected_color = st.selectbox("🎨 Color:", sorted(available_colors))
else:
    st.warning("⚠️ No colors available for this thickness.")
    st.session_state.selected_color = None

# 🏗️ **Edge Profile Selection**
st.markdown("### 🏗️ Select Edge Profile")
edge_profiles = {
    "Crescent (3CM)": "crescent.png",
    "Basin (3CM)": "basin.png",
    "Boulder (3CM)": "boulder.png",
    "Volcanic (3CM & 6CM)": "volcanic.png",
    "Summit (3CM)": "summit.png",
    "Seacliff (3CM & 6CM)": "seacliff.png"
}
st.session_state.selected_edge = st.selectbox("🏗️ Edge Profile:", list(edge_profiles.keys()))
st.image(edge_profiles[st.session_state.selected_edge], caption=f"{st.session_state.selected_edge} Edge Profile")

if st.button("📊 Estimate Cost"):
    if st.session_state.selected_color is None:
        st.error("❌ Please select a valid color.")
    else:
        selected_slab = df_inventory[(df_inventory["Color"] == st.session_state.selected_color) & (df_inventory["Thickness"] == st.session_state.selected_thickness)]
        total_available_sqft = selected_slab["Available Qty"].sum()
        required_sqft = square_feet * 1.2  
        if required_sqft > total_available_sqft:
            st.error(f"🚨 Not enough material available! ({total_available_sqft} sq ft available, {required_sqft} sq ft needed)")
        material_cost = required_sqft * selected_slab.iloc[0]["SQ FT PRICE"]
        fabrication_cost = st.session_state.fab_cost * required_sqft
        install_cost = st.session_state.install_cost * required_sqft
        ib_cost = (material_cost + fabrication_cost) * (1 + st.session_state.ib_margin)
        sale_price = (ib_cost + install_cost) * (1 + st.session_state.sale_margin)
        st.success(f"💰 **Estimated Sale Price: ${sale_price:.2f}**")
        st.markdown(f"🔍 [View Images](https://www.google.com/search?tbm=isch&q={st.session_state.selected_color} {st.session_state.selected_thickness} countertop)", unsafe_allow_html=True)
        with st.expander("🧐 Show Full Cost Breakdown"):
            st.markdown(f"""
            - **Material Cost:** ${material_cost:.2f}  
            - **Fabrication Cost:** ${fabrication_cost:.2f}  
            - **IB Cost:** ${ib_cost:.2f}  
            - **Installation Cost:** ${install_cost:.2f}  
            - **Total Sale Price:** ${sale_price:.2f}  
            - **Edge Profile:** {st.session_state.selected_edge}
            """)
