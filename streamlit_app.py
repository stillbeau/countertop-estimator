import streamlit as st
import pandas as pd
import requests
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Configurations ---
MINIMUM_SQ_FT = 25
MARKUP_FACTOR = 1.25
INSTALL_COST_PER_SQFT = 23
FABRICATION_COST_PER_SQFT = 23
ADDITIONAL_IB_RATE = 0
GST_RATE = 0.05

# --- Email Configuration using st.secrets ---
SMTP_SERVER = st.secrets["SMTP_SERVER"]
SMTP_PORT = int(st.secrets["SMTP_PORT"])
EMAIL_USER = st.secrets["EMAIL_USER"]
EMAIL_PASSWORD = st.secrets["EMAIL_PASSWORD"]
RECIPIENT_EMAIL = st.secrets.get("RECIPIENT_EMAIL", "sambeaumont@me.com")

# --- Google Sheets URL for cost data ---
GOOGLE_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ/export?format=csv"
)

@st.cache_data
def load_data():
    try:
        response = requests.get(GOOGLE_SHEET_URL)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        df = pd.read_csv(io.StringIO(response.text))
        df.columns = df.columns.str.strip()
        # Using raw string for regex pattern
        df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].replace(r"[\$,]", "", regex=True).astype(float)
        df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors="coerce")
        df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors="coerce").fillna(0).astype(int)
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error loading data: {e}")
        return None
    except Exception as e:
        st.error(f"❌ An unexpected error occurred: {e}")
        return None

# --- Cost Calculation Functions ---
def calculate_material_cost(unit_cost, sq_ft_used):
    return unit_cost * MARKUP_FACTOR * sq_ft_used

def calculate_fabrication_cost(sq_ft_used):
    return FABRICATION_COST_PER_SQFT * sq_ft_used

def calculate_installation_cost(sq_ft_used):
    return INSTALL_COST_PER_SQFT * sq_ft_used

def calculate_installation_base_cost(unit_cost, sq_ft_used):
    return (unit_cost + FABRICATION_COST_PER_SQFT + ADDITIONAL_IB_RATE) * sq_ft_used

def calculate_aggregated_costs(record, sq_ft_used):
    material_cost = calculate_material_cost(record["unit_cost"], sq_ft_used)
    fabrication_cost = calculate_fabrication_cost(sq_ft_used)
    installation_cost = calculate_installation_cost(sq_ft_used)
    installation_base_cost = calculate_installation_base_cost(record["unit_cost"], sq_ft_used)
    total_cost = material_cost + fabrication_cost + installation_cost
    return {
        "available_sq_ft": record["available_sq_ft"],
        "material_and_fab": material_cost + fabrication_cost,
        "install_cost": installation_cost,
        "total_cost": total_cost,
        "ib_cost": installation_base_cost,
    }

def send_email(subject, body):
    #... (email sending logic remains the same)...

# --- UI ---
st.title("Countertop Cost Estimator")
st.write("Get an accurate estimate for your custom countertop project")

# --- Sidebar Filters ---
with st.sidebar:
    thickness = st.selectbox("Select Thickness", options=["1.2cm", "2cm", "3cm"], index=2)
    sq_ft_input = st.number_input(
        "Enter Square Footage Needed",
        min_value=1,
        value=20,
        step=1,
        format="%d",
        help="Measure the front edge and depth (in inches), multiply them, and divide by 144."
    )
    #... (rest of the sidebar filters)...

# --- Data Processing ---
df_inventory = df_inventory[df_inventory["Thickness"] == thickness]
if df_inventory.empty:
    st.error("No slabs match the selected thickness. Please adjust your filter.")
    st.stop()

#... (rest of the data processing logic)...

# --- Tabs ---
tabs = ["Slab Selection", "Cost Breakdown", "Request a Quote"]
selected_tab = st.tabs(tabs)

if selected_tab == "Slab Selection":
    st.subheader("Select a Slab")
    # Implement grid layout for slab selection (using st.columns or a grid library)
    #...

elif selected_tab == "Cost Breakdown":
    st.subheader("Cost Breakdown")
    # Display cost breakdown details
    #...

elif selected_tab == "Request a Quote":
    st.subheader("Request a Quote")
    # Display the quote request form
    #...
