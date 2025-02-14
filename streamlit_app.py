import pandas as pd
import streamlit as st
import requests
from io import BytesIO

# ✅ Step 1: Define the correct GitHub RAW File URL
file_url = "https://raw.githubusercontent.com/stillbeau/countertop-estimator/main/deadfeb.xlsx"

# ✅ Step 2: Define `load_data()` BEFORE calling it
@st.cache_data
def load_data():
    """Load and clean the Excel file from GitHub."""
    try:
        st.write("📢 Attempting to fetch file...")
        response = requests.get(file_url, timeout=10)
        
        if response.status_code != 200:
            st.error(f"⚠️ Error loading file: HTTP {response.status_code}")
            return None

        st.write("✅ File downloaded successfully!")

        # ✅ Ensure this function exists before being called
        xls = pd.ExcelFile(BytesIO(response.content), engine="openpyxl")
        
        # ✅ Debugging Step - Check available sheets
        sheet_names = xls.sheet_names
        st.write(f"🔍 Available Sheets: {sheet_names}")

        # ✅ Try loading the first sheet
        df = pd.read_excel(xls, sheet_name=sheet_names[0])

        # ✅ Show first few rows for debugging
        st.write("📊 First 5 rows of data:", df.head())

        return df
    
    except Exception as e:
        st.error(f"❌ Error while loading the file: {e}")
        return None

# ✅ Step 3: Now Call `load_data()` AFTER It Is Defined
df_inventory = load_data()

if df_inventory is None:
    st.warning("⚠️ Data failed to load. Please check your file structure.")
    st.stop()

st.write("✅ Data loaded successfully!")
