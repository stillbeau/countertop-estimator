import pandas as pd
import streamlit as st
import requests
from io import BytesIO

# ✅ Correct GitHub RAW File URL
file_url = "https://raw.githubusercontent.com/stillbeau/countertop-estimator/main/Dead%20Stock%20Jan%209%202025%20revised.xlsx"

@st.cache_data
def load_data():
    """Load and clean the Excel file from GitHub."""
    try:
        response = requests.get(file_url, timeout=10)
        if response.status_code != 200:
            st.error(f"⚠️ Error loading file: HTTP {response.status_code}")
            return None

        # ✅ Ensure this function exists before being called
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

# ✅ Call the function AFTER it's defined
df_inventory = load_data()

if df_inventory is None:
    st.warning("⚠️ Data failed to load. Please check your file permissions and format.")
    st.stop()

st.write("✅ Data loaded successfully!")
