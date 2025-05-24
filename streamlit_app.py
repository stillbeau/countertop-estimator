import streamlit as st
import pandas as pd
import gspread # Used for Google Sheets API interaction
from google.oauth2.service_account import Credentials # Used for authenticating with Google
import json # Used to parse the service account JSON string from Streamlit secrets

# --- Custom CSS for improved mobile readability ---
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
ADDITIONAL_IB_RATE = 0 # If there's an additional cost per sqft for IB (Industry-Specific)
GST_RATE = 0.05
FINAL_MARKUP_PERCENTAGE = 0.25

# --- Google Sheets API Configuration ---
# You MUST replace "YOUR_SPREADSHEET_ID_HERE" with the actual ID from your Google Sheet's URL.
# Example: https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID_HERE/edit
SPREADSHEET_ID = "1vSgq5Sa6y-d9SoWKngBEBwpwlFedFL66P5GqW0S7qq-CdZHiOyevSgNnmzApVxR_2RuwknpiIRxPZ_T" # <<< REPLACE THIS if it's not your actual ID!

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly'] # Read-only access to sheets

# --- Function to load data from a specific Google Sheet tab ---
@st.cache_data(show_spinner=False)
def load_data_from_google_sheet(sheet_name):
    """
    Loads data from a specified tab (worksheet) in a Google Sheet using the Sheets API.
    Assumes gcp_service_account secret is configured in Streamlit Cloud.
    """
    try:
        creds_json_str = st.secrets["gcp_service_account"]
        creds_dict = json.loads(creds_json_str)
        credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_id(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(sheet_name)
        df = pd.DataFrame(worksheet.get_all_records())

        df.columns = df.columns.str.strip()
        if "Serialized On Hand Cost" not in df.columns or "Available Sq Ft" not in df.columns:
            st.error(f"Critical columns ('Serialized On Hand Cost' or 'Available Sq Ft') missing in sheet '{sheet_name}'.")
            return pd.DataFrame()

        df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].astype(str).str.replace("[\\$, ]", "", regex=True).astype(float)
        df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors="coerce")

        if "Serial Number" in df.columns:
            df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors="coerce").fillna(0).astype(int)
        else:
            st.info(f"Column 'Serial Number' not found in '{sheet_name}'. This may affect slab counting if not intended.")
            df["Serial Number"] = 0 # Add a default if missing, to prevent errors later if column is expected

        df.dropna(subset=['Available Sq Ft'], inplace=True)
        df = df[df['Available Sq Ft'] > 0]
        return df

    except gspread.exceptions.WorksheetNotFound:
        st.error(f"❌ Worksheet '{sheet_name}' not found. Check Google Sheet tab names and app's 'branch_locations' list.")
        return None
    except KeyError as ke:
        st.error(f"❌ Missing secret: '{ke}'. Ensure 'gcp_service_account' is set in Streamlit Cloud secrets.")
        return None
    except json.JSONDecodeError as jde:
        st.error(f"❌ Error decoding service account JSON from secrets: {jde}. Check format in Streamlit Cloud secrets.")
        return None
    except Exception as e:
        st.error(f"❌ Error loading data from '{sheet_name}': {e}")
        return None

# --- Cost Calculation Function ---
def calculate_aggregated_costs(record, sq_ft_used):
    unit_cost = record["unit_cost"]
    material_cost_with_markup = unit_cost * MARKUP_FACTOR * sq_ft_used
    fabrication_total = FABRICATION_COST_PER_SQFT * sq_ft_used
    material_and_fab = material_cost_with_markup + fabrication_total
    install_cost = INSTALL_COST_PER_SQFT * sq_ft_used
    total_cost = material_and_fab + install_cost
    ib_total_cost = (unit_cost + FABRICATION_COST_PER_SQFT + ADDITIONAL_IB_RATE) * sq_ft_used
    return {
        "available_sq_ft": record["available_sq_ft"],
        "material_and_fab": material_and_fab,
        "install_cost": install_cost,
        "total_cost": total_cost,
        "ib_cost": ib_total_cost,
    }

# --- Streamlit UI Begins Here ---
st.title("Countertop Cost Estimator")
st.write("Get an accurate estimate for your custom countertop project.")

branch_locations = ["Vernon", "Victoria", "Vancouver", "Calgary", "Edmonton", "Saskatoon", "Winnipeg", "Abbotsford"]
selected_branch = st.selectbox("Select Your Branch Location", branch_locations)

with st.spinner(f"Loading inventory data for {selected_branch} branch..."):
    df_inventory = load_data_from_google_sheet(selected_branch)

if df_inventory is None or df_inventory.empty:
    st.warning(f"Could not load or found no usable inventory data for '{selected_branch}'.")
    st.stop()

st.write(f"**Total slabs loaded for {selected_branch}:** {len(df_inventory)}")

if "Thickness" in df_inventory.columns:
    df_inventory["Thickness"] = df_inventory["Thickness"].astype(str).str.strip().str.lower()
    thickness_options = ["1.2cm", "2cm", "3cm"]
    # Check if default '3cm' exists, otherwise use first option or handle gracefully
    default_thickness_index = thickness_options.index("3cm") if "3cm" in thickness_options else 0
    selected_thickness = st.selectbox("Select Thickness", options=thickness_options, index=default_thickness_index)
    df_inventory = df_inventory[df_inventory["Thickness"] == selected_thickness.lower()]
else:
    st.info("Column 'Thickness' not found. Skipping thickness filter.")

if df_inventory.empty:
    st.warning("No slabs match selected thickness after filtering.")
    st.stop()

if "Brand" in df_inventory.columns and "Color" in df_inventory.columns:
    df_inventory["Full Name"] = df_inventory["Brand"].astype(str) + " - " + df_inventory["Color"].astype(str)
else:
    st.error("Required 'Brand' or 'Color' columns missing. Cannot proceed.")
    st.stop()

branch_to_material_sources = {
    "Vernon": ["Vernon", "Abbotsford"], "Victoria": ["Vernon", "Abbotsford"],
    "Vancouver": ["Vernon", "Abbotsford"], "Calgary": ["Edmonton", "Saskatoon"],
    "Edmonton": ["Edmonton", "Saskatoon"], "Saskatoon": ["Edmonton", "Saskatoon"],
    "Winnipeg": ["Edmonton", "Saskatoon"], "Abbotsford": ["Abbotsford"]
}

if "Location" in df_inventory.columns:
    allowed_material_locations = branch_to_material_sources.get(selected_branch, [])
    if allowed_material_locations:
        df_inventory = df_inventory[df_inventory["Location"].isin(allowed_material_locations)]
    else:
        st.info(f"No specific material sources for '{selected_branch}'. Showing all.")
else:
    st.info("Column 'Location' missing. Cannot filter by material source.")

if df_inventory.empty:
    st.warning("No slabs available after location filtering.")
    st.stop()

def get_fabrication_plant(branch):
    if branch in ["Vernon", "Victoria", "Vancouver", "Abbotsford"]: return "Abbotsford"
    if branch in ["Calgary", "Edmonton", "Saskatoon", "Winnipeg"]: return "Saskatoon"
    return "Unknown"

fabrication_plant = get_fabrication_plant(selected_branch)
st.markdown(f"**Fabrication Plant for {selected_branch} orders:** {fabrication_plant}")

df_inventory["unit_cost"] = df_inventory["Serialized On Hand Cost"] / df_inventory["Available Sq Ft"]

sq_ft_input = st.number_input("Enter Square Footage Needed", min_value=1, value=40, step=1)
sq_ft_used = max(sq_ft_input, MINIMUM_SQ_FT)
if sq_ft_input < MINIMUM_SQ_FT:
    st.info(f"Minimum is {MINIMUM_SQ_FT} sq ft. Using {MINIMUM_SQ_FT} sq ft for pricing.")

df_agg = (df_inventory.groupby(["Full Name", "Location"])
          .agg(available_sq_ft=("Available Sq Ft", "sum"),
               unit_cost=("unit_cost", "max"),
               slab_count=("Serial Number", "nunique"), # Count unique serial numbers for slab count
               serial_numbers=("Serial Number", lambda x: ", ".join(x.astype(str).unique())))
          .reset_index())

required_material = sq_ft_used * 1.1
df_agg = df_agg[df_agg["available_sq_ft"] >= required_material]
if df_agg.empty:
    st.error("No colors have enough material (including buffer).")
    st.stop()

df_agg["final_price"] = df_agg.apply(lambda row: calculate_aggregated_costs(row, sq_ft_used)["total_cost"] * (1 + GST_RATE), axis=1)
df_valid = df_agg[df_agg["final_price"] > 0]
if df_valid.empty:
    st.error("No valid slab prices available after calculations.")
    st.stop()

min_possible_cost = int(df_valid["final_price"].min()) if not df_valid.empty else 0
max_possible_cost = int(df_valid["final_price"].max()) if not df_valid.empty else 10000 # Default max if empty
if min_possible_cost >= max_possible_cost : max_possible_cost = min_possible_cost + 100 # Ensure max > min

max_job_cost = st.slider("Select Maximum Job Cost ($)", min_value=min_possible_cost, max_value=max_possible_cost, value=max_possible_cost, step=100)
df_agg_filtered = df_agg[df_agg["final_price"] <= max_job_cost]

if df_agg_filtered.empty:
    st.error("No colors available within the selected cost range.")
    st.stop()

records = df_agg_filtered.to_dict("records")
if not records: # Should be caught by df_agg_filtered.empty, but as a safeguard
    st.error("No records available to select.")
    st.stop()

selected_record = st.selectbox("Select Color", options=records,
                               format_func=lambda rec: f"{rec['Full Name']} - (${rec['final_price'] / sq_ft_used:.2f}/sq ft)")

if selected_record: # Check if a record is selected
    st.markdown(f"**Total Available Sq Ft (Selected Color):** {selected_record.get('available_sq_ft', 0):.0f} sq.ft")
    st.markdown(f"**Number of Slabs (Selected Color):** {selected_record.get('slab_count', 0)}")
    search_url = f"https://www.google.com/search?q={selected_record.get('Full Name', '').replace(' ', '+')}+countertop"
    st.markdown(f"[🔎 Google Image Search for {selected_record.get('Full Name', '')}]({search_url})")

    edge_profiles = ["Crescent", "Basin", "Boulder", "Volcanic", "Piedmont", "Summit", "Seacliff", "Alpine", "Treeline"]
    selected_edge_profile = st.selectbox("Select Edge Profile", options=edge_profiles, index=edge_profiles.index("Seacliff"))

    costs = calculate_aggregated_costs(selected_record, sq_ft_used)
    sub_total = costs["total_cost"]
    gst_amount = sub_total * GST_RATE
    final_price = (sub_total + gst_amount) * (1 + FINAL_MARKUP_PERCENTAGE)

    with st.expander("View Subtotal & GST"):
        st.markdown(f"**Subtotal (before tax):** ${sub_total:,.2f}")
        st.markdown(f"**GST (5%):** ${gst_amount:,.2f}")

    st.markdown(f"### Your Total Price: :green[${final_price:,.2f}]")

    if selected_record.get('slab_count', 0) > 1:
        st.info("Note: Multiple slabs are being used; colors may vary.")
else:
    st.info("Please make a selection to see price details.")


# --- DETAILED BREAKDOWN (PASSWORD PROTECTED) SECTION HAS BEEN COMPLETELY REMOVED ---
# (If you plan to email the breakdown, the logic to gather data for it
#  and trigger the email would go here or be called from here,
#  perhaps after a button click like "Email me this breakdown")

st.markdown("---")
st.caption("Estimator vX.Y.Z") # Optional: version number or footer
