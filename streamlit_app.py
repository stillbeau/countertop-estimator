import streamlit as st
import pandas as pd
import gspread
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz

# --- MUST BE FIRST STREAMLIT COMMAND ---
st.set_page_config(page_title="CounterPro Estimator", layout="centered")

# --- Custom CSS ---
st.markdown("""
    <style>
    div[data-baseweb="select"] { font-size: 0.8rem; }
    .stLabel, label { font-size: 0.8rem; }
    </style>
""", unsafe_allow_html=True)

# --- Configurations ---
MINIMUM_SQ_FT = 35
MARKUP_FACTOR = 1.25
INSTALL_COST_PER_SQFT = 27
FABRICATION_COST_PER_SQFT = 17
ADDITIONAL_IB_RATE = 0
GST_RATE = 0.05
SPREADSHEET_ID = "166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
MASTER_INVENTORY_SHEET_TAB_NAME = "InventoryData"
SALESPEOPLE_SHEET_TAB_NAME = "Salespeople"

@st.cache_data(show_spinner=False)
def load_data_from_google_sheet(sheet_name_to_load):
    try:
        creds_dict = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds_dict, scopes=SCOPES)
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(sheet_name_to_load)
        df = pd.DataFrame(worksheet.get_all_records())
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Failed to load sheet '{sheet_name_to_load}': {e}")
        return pd.DataFrame()

def calculate_aggregated_costs(record, sq_ft_used):
    unit_cost = record.get("unit_cost", 0) or 0
    material_cost_with_markup = unit_cost * MARKUP_FACTOR * sq_ft_used
    fabrication_total = FABRICATION_COST_PER_SQFT * sq_ft_used
    install_cost = INSTALL_COST_PER_SQFT * sq_ft_used
    ib_cost_component = (unit_cost + FABRICATION_COST_PER_SQFT + ADDITIONAL_IB_RATE) * sq_ft_used
    total_customer_facing_base_cost = material_cost_with_markup + fabrication_total + install_cost
    return {
        "base_material_and_fab_component": material_cost_with_markup + fabrication_total,
        "base_install_cost_component": install_cost,
        "ib_cost_component": ib_cost_component,
        "total_customer_facing_base_cost": total_customer_facing_base_cost
    }

st.title("CounterPro")
st.write("Get an accurate estimate for your custom countertop project.")

df_inventory = load_data_from_google_sheet(MASTER_INVENTORY_SHEET_TAB_NAME)
if df_inventory.empty:
    st.stop()

# --- Validate and clean Full Name fields ---
if "Brand" not in df_inventory.columns or "Color" not in df_inventory.columns:
    st.error("Missing 'Brand' or 'Color' column."); st.stop()
df_inventory["Brand"] = df_inventory["Brand"].astype(str).str.strip()
df_inventory["Color"] = df_inventory["Color"].astype(str).str.strip()
df_inventory["Full Name"] = df_inventory["Brand"] + " - " + df_inventory["Color"]

# --- Cost Calculations ---
if "Serialized On Hand Cost" not in df_inventory.columns or "Available Sq Ft" not in df_inventory.columns:
    st.error("Missing costing columns."); st.stop()
df_inventory = df_inventory[df_inventory['Available Sq Ft'].notna() & (df_inventory['Available Sq Ft'] > 0)]
df_inventory["unit_cost"] = df_inventory["Serialized On Hand Cost"] / df_inventory["Available Sq Ft"]

sq_ft_input = st.number_input("Enter Square Footage Needed", min_value=1, value=40, step=1)
sq_ft_used = max(sq_ft_input, MINIMUM_SQ_FT)

df_inventory["price"] = df_inventory.apply(lambda r: calculate_aggregated_costs(r, sq_ft_used)["total_customer_facing_base_cost"], axis=1)
options = df_inventory.to_dict("records")
selected = st.selectbox("Choose a material", options, format_func=lambda r: f"{r['Full Name']} - ${r['price']:.2f}")

if selected:
    costs = calculate_aggregated_costs(selected, sq_ft_used)
    st.markdown(f"**Material:** {selected['Full Name']}")
    st.markdown(f"**Total Cost Estimate:** ${costs['total_customer_facing_base_cost']:,.2f}")