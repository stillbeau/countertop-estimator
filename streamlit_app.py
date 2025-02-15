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
            if "dark_mode" not in data:
                data["dark_mode"] = False
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
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = saved_settings["dark_mode"]  # ✅ No more KeyError!

# ✅ **Dark Mode CSS**
def apply_dark_mode():
    dark_css = """
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
    """
    if st.session_state.dark_mode:
        st.markdown(dark_css, unsafe_allow_html=True)

# ✅ Apply Dark Mode if Enabled
apply_dark_mode()

# 🎛 **Sidebar Settings**
with st.sidebar:
    st.header("🔑 Admin Panel")

    # **Dark Mode Toggle (Now Always Works)**
    st.session_state.dark_mode = st.toggle("🌓 Dark Mode", value=st.session_state.dark_mode)
    save_settings()  # ✅ Save toggle change safely

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