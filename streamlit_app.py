import pandas as pd
import streamlit as st
import requests
from io import BytesIO

# ✅ Correct GitHub RAW File URL for Excel file
file_url = "https://raw.githubusercontent.com/stillbeau/countertop-estimator/main/Dead%20Stock%20Jan%209%202025%20revised.xlsx"

st.write("📢 Attempting to load data...")

# Test if the file URL is accessible
response = requests.get(file_url)

if response.status_code == 200:
    st.write("✅ File URL is accessible!")
else:
    st.error(f"❌ Failed to fetch the file. HTTP Status Code: {response.status_code}")
    st.stop()

# Load the Excel file
df_inventory = load_data()

if df_inventory is None:
    st.error("❌ Data loading failed. Check the file format and URL.")
    st.stop()
else:
    st.write("✅ Data loaded successfully!")


@st.cache_data
def load_data():
    """Load and clean the Excel file from GitHub."""
    try:
        response = requests.get(file_url, timeout=10)  # 10-second timeout
        if response.status_code != 200:
            st.error(f"⚠️ Error loading file: HTTP {response.status_code}")
            return None

        # ✅ This replaces the old 'file_path' reference
        xls = pd.ExcelFile(BytesIO(response.content), engine="openpyxl")
        df = pd.read_excel(xls, sheet_name='Sheet1')

        df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=True)
        df_cleaned = df[['Product Variant', 'Available Qty', 'SQ FT PRICE', 'FAB', 'TEMP/Install', 'IB SQ FT Price', 'Sale price']].copy()
        df_cleaned.columns = ['Product_Variant', 'Available_Qty_sqft', 'Sq_ft_price', 'Fab', 'Temp_Install', 'IB_sq_ft_price', 'Sale_price']
        df_cleaned[['Material', 'Color_Thickness']] = df_cleaned['Product_Variant'].str.split(' - ', n=1, expand=True)
        df_cleaned[['Color', 'Thickness']] = df_cleaned['Color_Thickness'].str.rsplit(' ', n=1, expand=True)
        df_cleaned['Available_Qty_sqft'] = pd.to_numeric(df_cleaned['Available_Qty_sqft'], errors='coerce')
        df_cleaned['Sq_ft_price'] = pd.to_numeric(df_cleaned['Sq_ft_price'], errors='coerce')
        df_cleaned['Fab'] = pd.to_numeric(df_cleaned['Fab'], errors='coerce')
        df_cleaned['Temp_Install'] = pd.to_numeric(df_cleaned['Temp_Install'], errors='coerce')
        df_cleaned['IB_sq_ft_price'] = pd.to_numeric(df_cleaned['IB_sq_ft_price'], errors='coerce')
        df_cleaned['Sale_price'] = pd.to_numeric(df_cleaned['Sale_price'], errors='coerce')

        return df_cleaned[['Material', 'Color', 'Thickness', 'Available_Qty_sqft', 'Sq_ft_price', 'Fab', 'Temp_Install', 'IB_sq_ft_price', 'Sale_price']]
    
    except Exception as e:
        st.error(f"❌ An error occurred while loading the file: {e}")
        return None

df_inventory = load_data()

if df_inventory is None:
    st.warning("⚠️ Data failed to load. Please check your GitHub URL and file permissions.")
    st.stop()
