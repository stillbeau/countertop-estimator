import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- Custom CSS ---
st.markdown("""
    <style>
    div[data-baseweb="select"] {
        font-size: 0.8rem;
    }
    .stLabel, label {
        font-size: 0.8rem;
    }
    </style>
""", unsafe_allow_html=True)

# --- Configurations ---
MINIMUM_SQ_FT = 35
MARKUP_FACTOR = 1.15
INSTALL_COST_PER_SQFT = 20
FABRICATION_COST_PER_SQFT = 17
ADDITIONAL_IB_RATE = 0
GST_RATE = 0.05
FINAL_MARKUP_PERCENTAGE = 0.25

# --- Load Google Sheet Data ---
def load_inventory_from_all_tabs(sheet_url, sheet_tabs, creds):
    client = gspread.authorize(creds)
    sheet = client.open_by_url(sheet_url)
    all_data = []
    for tab in sheet_tabs:
        try:
            worksheet = sheet.worksheet(tab)
            df = pd.DataFrame(worksheet.get_all_records())
            df.columns = df.columns.str.strip()
            df["Location"] = tab

            if "Serial Number" in df.columns:
                df["Serial Number"] = df["Serial Number"].astype(str).str.extract(r"(\d+)")
                df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors="coerce")

            if "Serialized On Hand Cost" in df.columns:
                df["Serialized On Hand Cost"] = (
                    df["Serialized On Hand Cost"].replace("[\\$,]", "", regex=True).astype(float)
                )

            if "Available Sq Ft" in df.columns:
                df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors="coerce")

            all_data.append(df)
            st.success(f"✅ Loaded tab: {tab} with {len(df)} rows")
        except Exception as e:
            st.warning(f"⚠️ Failed loading tab '{tab}': {e}")
    return pd.concat(all_data, ignore_index=True)

# --- Main App ---
st.title("Countertop Cost Estimator")
st.write("Get an accurate estimate for your custom countertop project")

with st.spinner("Loading inventory..."):
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"])
    sheet_url = "https://docs.google.com/spreadsheets/d/166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ"
    sheet_tabs = ["Vernon", "Abbotsford", "Edmonton", "Saskatoon"]
    df_inventory = load_inventory_from_all_tabs(sheet_url, sheet_tabs, creds)

# --- Debug Output ---
if df_inventory.empty:
    st.error("❌ No slab data loaded.")
else:
    st.write("✅ Tabs loaded:", sheet_tabs)
    st.write("✅ Total rows loaded:", len(df_inventory))
    st.dataframe(df_inventory.head())
    st.write("📊 Slabs by Location:")
    st.dataframe(df_inventory["Location"].value_counts())
