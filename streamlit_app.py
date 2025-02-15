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
if "selected_edge_profile" not in st.session_state:
    st.session_state.selected_edge_profile = "Summit (3CM)"  # ✅ Default edge profile

# ✅ Define Edge Profiles & Images
EDGE_PROFILES = {
    "Crescent (3CM)": "https://your-image-url.com/crescent.png",
    "Basin (3CM)": "https://your-image-url.com/basin.png",
    "Boulder (3CM)": "https://your-image-url.com/boulder.png",
    "Volcanic (3CM & 6CM)": "https://your-image-url.com/volcanic.png",
    "Cornice (6CM)": "https://your-image-url.com/cornice.png",
    "Piedmont (3CM)": "https://your-image-url.com/piedmont.png",
    "Summit (3CM)": "https://your-image-url.com/summit.png",
    "Seacliff (3CM & 6CM)": "https://your-image-url.com/seacliff.png",
    "Alpine (3CM)": "https://your-image-url.com/alpine.png",
    "Treeline (3CM)": "https://your-image-url.com/treeline.png",
    "Rimrock (Custom Sizes)": "https://your-image-url.com/rimrock.png",
    "Moraine (3CM & 6CM)": "https://your-image-url.com/moraine.png",
}

# 🎨 **Main UI**
st.title("🛠 Countertop Cost Estimator")
st.markdown("### Select your slab and get an estimate!")

col1, col2 = st.columns(2)
with col1:
    square_feet = st.number_input("📐 Square Feet:", min_value=1, step=1)

with col2:
    thickness_options = ["1.2 cm", "2 cm", "3 cm"]
    st.session_state.selected_thickness = st.selectbox("🔲 Thickness:", thickness_options, index=thickness_options.index(st.session_state.selected_thickness))

# 🔲 **Edge Profile Selection with Image**
st.markdown("### ✨ Select Edge Profile:")
st.session_state.selected_edge_profile = st.selectbox("", list(EDGE_PROFILES.keys()), index=list(EDGE_PROFILES.keys()).index(st.session_state.selected_edge_profile))
st.image(EDGE_PROFILES[st.session_state.selected_edge_profile], width=200)

# 🎨 **Color Selection**
available_colors = st.session_state.df_inventory[st.session_state.df_inventory["Thickness"] == st.session_state.selected_thickness]["Color"].dropna().unique()
if len(available_colors) > 0:
    st.session_state.selected_color = st.selectbox("🎨 Color:", sorted(available_colors), index=list(available_colors).index(st.session_state.selected_color) if st.session_state.selected_color in available_colors else 0)
else:
    st.warning("⚠️ No colors available for this thickness.")
    st.session_state.selected_color = None

if st.button("📊 Estimate Cost"):
    if st.session_state.selected_color is None:
        st.error("❌ Please select a valid color.")
    else:
        selected_slab = st.session_state.df_inventory[(st.session_state.df_inventory["Color"] == st.session_state.selected_color) & (st.session_state.df_inventory["Thickness"] == st.session_state.selected_thickness)]
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

        query = f"{st.session_state.selected_color} {st.session_state.selected_thickness} countertop"
        google_url = f"https://www.google.com/search?tbm=isch&q={query.replace(' ', '+')}"
        st.markdown(f"🔍 [Click here to view {st.session_state.selected_color} images]({google_url})", unsafe_allow_html=True)

        with st.expander("🧐 Show Full Cost Breakdown"):
            st.markdown(f"""
            - **Material Cost:** ${material_cost:.2f}  
            - **Fabrication Cost:** ${fabrication_cost:.2f}  
            - **IB Cost:** ${ib_cost:.2f}  
            - **Installation Cost:** ${install_cost:.2f}  
            - **Total Sale Price:** ${sale_price:.2f}  
            - **Edge Profile Selected:** {st.session_state.selected_edge_profile}  
            """)
