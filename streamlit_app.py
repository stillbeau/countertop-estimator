import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Google Sheets URL
google_sheets_url = "https://docs.google.com/spreadsheets/d/166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ/edit?usp=sharing"

@st.cache_data
def load_google_sheets():
    sheet_id = google_sheets_url.split("/d/")[1].split("/")[0]  # Extract ID from URL
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"

    try:
        df = pd.read_csv(csv_url)
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

# Load data
df_inventory = load_google_sheets()

if df_inventory is not None:
    st.write("✅ **Data Loaded Successfully!**")
    st.dataframe(df_inventory)  # Display the Google Sheet Data
else:
    st.error("❌ Failed to Load Data. Check Google Sheet Link & Permissions.")

