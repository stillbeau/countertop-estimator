import pandas as pd
import streamlit as st
import requests
from io import BytesIO
import json
import os

# ✅ GitHub RAW File URL (Your Excel Data)
file_url = "https://raw.githubusercontent.com/stillbeau/countertop-estimator/main/deadfeb.xlsx"

# 🔑 Admin Password
ADMIN_PASSWORD = "floform2024"

# 🔄 **Settings File to Persist Admin Rates**
SETTINGS_FILE = "settings.json"

# ✅ **Function to Load Saved Settings Safely**
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            # ✅ Ensure "dark_mode" key exists, else default to False
            data.setdefault("dark_mode", False)
            return data
    return {"fab_cost": 23, "install_cost": 23, "ib_margin": 0.15, "sale_margin": 0.15, "dark_mode": False}

# ✅ **Function to Save Settings**
def save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump({
            "fab_cost": st.session_state.fab_cost,
            "install_cost": st.session_state.install_cost,
            "ib_margin": st.session_state.ib_margin,
            "sale_margin": st.session_state.sale_margin,
            "dark_mode": st.session_state.dark_mode
        }, f)

# ✅ Load saved settings safely
saved_settings = load_settings()

# ✅ **Ensure Session State Variables Exist**
for key, default_value in saved_settings.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# ✅ **Dark Mode CSS**
def apply_dark_mode():
    if st.session_state.dark_mode:
        st.markdown("""
            <style>
            body, .stApp {
                background-color: #121212;
                color: white;
            }
            .stSidebar {
                background-color: #1E1E1E;
            }
            .stButton>button {
                background-color: #444;
                color: white;
                border-radius: 8px;
            }
            .stTextInput>div>div>input {
                background-color: #333;
                color: white;
            }
            </style>
        """, unsafe_allow_html=True)

# ✅ Apply Dark Mode (but don't block UI)
apply_dark_mode()

# 🎛 **Sidebar Settings**
with st.sidebar:
    st.header("🔑 Admin Panel")

    # **Dark Mode Toggle (Now Always Works)**
    dark_mode_toggled = st.toggle("🌓 Dark Mode", value=st.session_state.dark_mode)
    if dark_mode_toggled != st.session_state.dark_mode:
        st.session_state.dark_mode = dark_mode_toggled
        save_settings()
        st.experimental_rerun()  # ✅ Ensures the toggle applies instantly

    if not st.session_state.admin_access:
        password_input = st.text_input("Enter Admin Password:", type="password")
        if st.button("🔓 Login"):
            if password_input == ADMIN_PASSWORD:
                st.session_state.admin_access = True
                st.experimental_rerun()

    if st.session_state.admin_access:
        st.subheader("⚙️ Adjustable Rates")

        st.session_state.fab_cost = st.number_input("🛠 Fabrication Cost per sq ft:", 
                                                    value=float(st.session_state.fab_cost), step=1.0)

        st.session_state.ib_margin = st.number_input("📈 IB Margin (%)", 
                                                     value=float(st.session_state.ib_margin), step=0.01, format="%.2f")

        st.session_state.install_cost = st.number_input("🚚 Install & Template Cost per sq ft:", 
                                                        value=float(st.session_state.install_cost), step=1.0)

        st.session_state.sale_margin = st.number_input("📈 Sale Margin (%)", 
                                                       value=float(st.session_state.sale_margin), step=0.01, format="%.2f")

        # ✅ Save settings when any value is changed
        save_settings()

        if st.button("🔒 Logout"):
            st.session_state.admin_access = False
            st.experimental_rerun()

# 🎨 **Main UI**
st.title("🛠 Countertop Cost Estimator")
st.markdown("### Select your slab and get an estimate!")

col1, col2 = st.columns(2)
with col1:
    square_feet = st.number_input("📐 Square Feet:", min_value=1, step=1)

with col2:
    thickness_options = ["1.2 cm", "2 cm", "3 cm"]
    selected_thickness = st.selectbox("🔲 Thickness:", thickness_options)

# ✅ Ensure Data is Loaded Before Proceeding
if "df_inventory" in st.session_state and not st.session_state.df_inventory.empty:
    df_inventory = st.session_state.df_inventory
    available_colors = df_inventory[df_inventory["Thickness"] == selected_thickness]["Color"].dropna().unique()

    if len(available_colors) > 0:
        selected_color = st.selectbox("🎨 Color:", sorted(available_colors))
    else:
        st.warning("⚠️ No colors available for this thickness.")
        selected_color = None

    if st.button("📊 Estimate Cost"):
        if selected_color is None:
            st.error("❌ Please select a valid color.")
        else:
            selected_slab = df_inventory[(df_inventory["Color"] == selected_color) & (df_inventory["Thickness"] == selected_thickness)]
            if selected_slab.empty:
                st.error("❌ No slab found for the selected color and thickness.")
            else:
                selected_slab = selected_slab.iloc[0]
                available_sqft = selected_slab["Available Qty"]
                sq_ft_price = float(selected_slab["SQ FT PRICE"])  
                required_sqft = square_feet * 1.2  

                material_cost = sq_ft_price * required_sqft
                fabrication_cost = st.session_state.fab_cost * required_sqft
                install_cost = st.session_state.install_cost * required_sqft
                ib_cost = (material_cost + fabrication_cost) * (1 + st.session_state.ib_margin)
                sale_price = (ib_cost + install_cost) * (1 + st.session_state.sale_margin)

                st.success(f"💰 **Estimated Sale Price: ${sale_price:.2f}**")

                # ✅ Generate Google Search URL
                query = f"{selected_color} {selected_thickness} countertop"
                google_url = f"https://www.google.com/search?tbm=isch&q={query.replace(' ', '+')}"
                st.markdown(f"🔍 [Click here to view {selected_color} images]({google_url})", unsafe_allow_html=True)

                with st.expander("🧐 Show Full Cost Breakdown"):
                    st.markdown(f"""
                    - **Material Cost:** ${material_cost:.2f}  
                    - **Fabrication Cost:** ${fabrication_cost:.2f}  
                    - **IB Cost:** ${ib_cost:.2f}  
                    - **Installation Cost:** ${install_cost:.2f}  
                    - **Total Sale Price:** ${sale_price:.2f}  
                    """)

else:
    st.warning("⚠️ Data not loaded. Please refresh the page.")