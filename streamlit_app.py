import pandas as pd
import streamlit as st
import requests
from io import BytesIO

# ✅ Correct GitHub RAW File URL
file_url = "https://raw.githubusercontent.com/stillbeau/countertop-estimator/main/deadfeb.xlsx"

# ✅ Define `load_data()` BEFORE calling it
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

        # ✅ Load the Excel file
        xls = pd.ExcelFile(BytesIO(response.content), engine="openpyxl")

        # ✅ Debugging Step - Check available sheets
        sheet_names = xls.sheet_names
        st.write(f"🔍 Available Sheets: {sheet_names}")

        # ✅ Load the first sheet
        df = pd.read_excel(xls, sheet_name=sheet_names[0])

        # ✅ Clean column names (remove hidden spaces)
        df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=True)

        # ✅ Force "Serial Number" column to be text
        for col in df.columns:
            if "serial" in col.lower():  # Handle variations like "Serial Number"
                df[col] = df[col].astype(str)
                st.write(f"🔧 Converted column '{col}' to string.")

        # ✅ Show first few rows for debugging
        st.write("📊 First 5 rows of cleaned data:", df.head())

        return df
    
    except Exception as e:
        st.error(f"❌ Error while loading the file: {e}")
        return None

# ✅ Call `load_data()` AFTER it is defined
df_inventory = load_data()

if df_inventory is None:
    st.warning("⚠️ Data failed to load. Please check your file structure.")
    st.stop()

st.write("✅ Data loaded successfully!")
