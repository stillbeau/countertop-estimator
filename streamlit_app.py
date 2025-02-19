import streamlit as st
import pandas as pd
import requests
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re  # For email validation
from typing import Optional

# --- Configurations --- (Consider moving these to st.secrets or a config file)
MINIMUM_SQ_FT = 25
MARKUP_FACTOR = 1.25
INSTALL_COST_PER_SQFT = 23
FABRICATION_COST_PER_SQFT = 23
ADDITIONAL_IB_RATE = 0
GST_RATE = 0.05
# Email config is fine in st.secrets

# --- Google Sheets URL ---
GOOGLE_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ/export?format=csv"
)


def is_valid_email(email: str) -> bool:
    """Simple email validation using regex."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}<span class="math-inline">"
return bool\(re\.match\(pattern, email\)\)
@st\.cache\_data
def load\_data\(\) \-\> Optional\[pd\.DataFrame\]\:
try\:
response \= requests\.get\(GOOGLE\_SHEET\_URL\)
response\.raise\_for\_status\(\)  \# Raises HTTPError for bad requests \(4xx or 5xx\)
df \= pd\.read\_csv\(io\.StringIO\(response\.text\)\)
df\.columns \= df\.columns\.str\.strip\(\)
df\["Serialized On Hand Cost"\] \= \(
df\["Serialized On Hand Cost"\]\.replace\("\[\\</span>,]", "", regex=True).astype(float)
        )
        df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors="coerce")
        df["Serial Number"] = (
            pd.to_numeric(df["Serial Number"], errors="coerce").fillna(0).astype(int)
        )
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Failed to load data: Network error: {e}")
        return None
    except Exception as e:
        st.error(f"❌ Failed to load data: An unexpected error occurred: {e}")
        return None


def calculate_aggregated_costs(record, sq_ft_used: float) -> dict:
    # ... (rest of the function remains the same) ...
    unit_cost = record["unit_cost"]
    material_cost_with_markup = unit_cost * MARKUP_FACTOR * sq_ft_used
    fabrication_total = FABRICATION_COST_PER_SQFT * sq_ft_used
    material_and_fab = material_cost_with_markup + fabrication_total
    install_cost = INSTALL_COST_PER_SQFT * sq_ft_used
    total_cost = material_and_fab + install_cost
    ib_total_cost = (
        (unit_cost + FABRICATION_COST_PER_SQFT + ADDITIONAL_IB_RATE) * sq_ft_used
    )
    return {
        "available_sq_ft": record["available_sq_ft"],
        "material_and_fab": material_and_fab,
        "install_cost": install_cost,
        "total_cost": total_cost,
        "ib_cost": ib_total_cost,
    }


def send_email(subject: str, body: str) -> bool:
    # ... (rest of the function remains the same) ...
    msg = MIMEMultipart()
    msg["From"] = "Sc countertops <sam@sccountertops.ca>"
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False


# --- UI and rest of your application logic ---
st.title("Countertop Cost Estimator")
st.write("Get an accurate estimate for your custom countertop project")

# --- Load Data ---
with st.spinner("Loading data..."):
    df_inventory = load_data()
if df_inventory is None:
    st.error("Data could not be loaded.")
    st.stop()

# --- Thickness Selector (Location selector removed) ---
thickness = st.selectbox(
    "Select Thickness", options=["1.2cm", "2cm", "3cm"], index=2
)  # Default to 3cm
df_inventory = df_inventory[df_inventory["Thickness"] == thickness]
if df_inventory.empty:
    st.warning("No slabs match the selected thickness. Please adjust your filter.")
    st.stop()

# --- Map Supplier (from Location) and Create Combined Identifier ---
supplier_mapping = {"VER": "Vernon", "ABB": "Abbotsford"}
df_inventory["Supplier"] = df_inventory["Location"].map(supplier_mapping)
df_inventory["Full Name"] = df_inventory["Brand"] + " - " + df_inventory["Color"]

# *** Compute Unit Cost ***
df_inventory["unit_cost"] = (
    df_inventory["Serialized On Hand Cost"] / df_inventory["Available Sq Ft"]
)

# --- Square Footage Input ---
sq_ft_input = st.number_input(
    "Enter Square Footage Needed",
    min_value=1,
    value=20,
    step=1,
    format="%d",
    help="Measure the front edge and depth (in inches), multiply them, and divide by 144.",
)
# Enforce the minimum square footage for quoting
if sq_ft_input < MINIMUM_SQ_FT:
    sq_ft_used = MINIMUM_SQ_FT
    st.info(
        f"Minimum square footage is {MINIMUM_SQ_FT} sq ft. Using {MINIMUM_SQ_FT} sq ft for pricing."
    )
else:
    sq_ft_used = sq_ft_input

# --- Aggregate Data by Slab (Full Name) and Supplier ---
# Using named aggregation to sum available sq ft, get max unit_cost, count slabs, and join serial numbers.
df_agg = df_inventory.groupby(["Full Name", "Supplier"]).agg(
    available_sq_ft=("Available Sq Ft", "sum"),
    unit_cost=("unit_cost", "max"),
    slab_count=("Serial Number", "count"),
    serial_numbers=("Serial Number", lambda x: ", ".join(x.astype(str))),
).reset_index()

# --- Filter Out Options Without Enough Material ---
required_material = sq_ft_used *
