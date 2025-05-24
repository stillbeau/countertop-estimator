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
# !!! IMPORTANT !!!
# 1. REPLACE "YOUR_SPREADSHEET_ID_HERE" with the actual ID from your Google Sheet's URL.
#    Example: https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID_HERE/edit
# 2. FOR THIS TEST: Ensure your Google Sheet has ONE TAB named exactly "InventoryData" (case-sensitive).
SPREADSHEET_ID = "1vSgq5Sa6y-d9SoWKngBEBwpwlFedFL66P5GqW0S7qq-CdZHiOyevSgNnmzApVxR_2RuwknpiIRxPZ_T" # <<< REPLACE THIS if it's not your actual ID!
SINGLE_TEST_SHEET_NAME = "InventoryData" # Fixed sheet name for this test

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly'] # Read-only access to sheets

# --- Function to load data from a specific Google Sheet tab ---
@st.cache_data(show_spinner=False)
def load_data_from_google_sheet(sheet_name_to_load): # Renamed argument for clarity
    """
    Loads data from a specified tab (worksheet) in a Google Sheet using the Sheets API.
    Assumes gcp_service_account secret is configured in Streamlit Cloud.
    """
    st.write(f"Attempting to load sheet: '{sheet_name_to_load}' from SPREADSHEET_ID: '{SPREADSHEET_ID[:10]}...'")
    try:
        creds_json_str = st.secrets["gcp_service_account"]
        creds_dict = json.loads(creds_json_str)
        credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        gc = gspread.authorize(credentials)

     # ... (lines for loading secrets and initializing creds_dict) ...

        st.info(f"Attempting to authorize gspread with service_account_from_dict using client_email: {creds_dict.get('client_email')}")
        try:
            gc = gspread.service_account_from_dict(creds_dict, scopes=SCOPES)
            st.success(f"gspread client initialized. Type: {type(gc)}") # Good to confirm the type
        except Exception as e:
            st.error(f"❌ Failed to initialize gspread client (gc = gspread.service_account_from_dict(...)): {e}")
            return None

        # --- Debugging: Check if open_by_id attribute exists ---
        if not hasattr(gc, 'open_by_id'):
            st.error(f"❌ CRITICAL: 'gc' object (type: {type(gc)}) DOES NOT HAVE attribute 'open_by_id'.")
            st.warning("This strongly suggests an issue with the gspread library version or installation in the Streamlit Cloud environment, even if requirements.txt seems correct.")
            # You could add this to see all available attributes if it fails:
            # st.write(f"Available attributes/methods for 'gc' object: {dir(gc)}")
            return None # Stop execution if this critical method is missing
        else:
            st.success("✅ SUCCESS: 'gc' object HAS attribute 'open_by_id'. Proceeding to open sheet.")
        # --- End Debugging ---

        st.info(f"Attempting to open spreadsheet by ID: {SPREADSHEET_ID}")
        try:
            spreadsheet = gc.open_by_id(SPREADSHEET_ID) # This line will now only be reached if open_by_id exists
            st.success(f"Successfully opened spreadsheet: '{spreadsheet.title}'")
        except gspread.exceptions.SpreadsheetNotFound:
            st.error(f"❌ Spreadsheet with ID '{SPREADSHEET_ID}' not found. Check SPREADSHEET_ID and sharing permissions with service account: {creds_dict.get('client_email')}")
            return None
        # ... (rest of the try-except blocks for opening worksheet and getting records) ...

        spreadsheet = gc.open_by_id(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(sheet_name_to_load)
        df = pd.DataFrame(worksheet.get_all_records())

        df.columns = df.columns.str.strip()
        if "Serialized On Hand Cost" not in df.columns or "Available Sq Ft" not in df.columns:
            st.error(f"Critical columns ('Serialized On Hand Cost' or 'Available Sq Ft') missing in sheet '{sheet_name_to_load}'.")
            return pd.DataFrame() # Return empty DataFrame

        # Data cleaning and type conversion
        df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].astype(str).str.replace("[\\$, ]", "", regex=True).astype(float)
        df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors="coerce")

        if "Serial Number" in df.columns:
            df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors="coerce").fillna(0).astype(int)
        else:
            st.info(f"Column 'Serial Number' not found in '{sheet_name_to_load}'. This may affect slab counting if not intended.")
            df["Serial Number"] = 0 # Add a default if missing

        df.dropna(subset=['Available Sq Ft'], inplace=True)
        df = df[df['Available Sq Ft'] > 0]
        return df

    except gspread.exceptions.WorksheetNotFound:
        st.error(f"❌ Worksheet '{sheet_name_to_load}' not found in the Google Sheet. Please verify the tab name is exactly '{sheet_name_to_load}' (case-sensitive).")
        return None
    except gspread.exceptions.APIError as apie:
        st.error(f"❌ Google Sheets API Error: {apie}. This could be due to incorrect SPREADSHEET_ID, or the service account not having access to the sheet.")
        return None
    except KeyError as ke:
        st.error(f"❌ Missing secret: '{ke}'. Ensure 'gcp_service_account' is set in Streamlit Cloud secrets.")
        return None
    except json.JSONDecodeError as jde:
        st.error(f"❌ Error decoding service account JSON from secrets: {jde}. Check format in Streamlit Cloud secrets.")
        return None
    except Exception as e:
        st.error(f"❌ An unexpected error occurred while loading data from '{sheet_name_to_load}': {e}")
        return None

# --- Cost Calculation Function ---
def calculate_aggregated_costs(record, sq_ft_used):
    unit_cost = record["unit_cost"]
    material_cost_with_markup = unit_cost * MARKUP_FACTOR * sq_ft_used
    fabrication_total = FABRICATION_COST_PER_SQFT * sq_ft_used
    material_and_fab = material_cost_with_markup + fabrication_total
    install_cost = INSTALL_COST_PER_SQFT * sq_ft_used
    total_cost = material_and_fab + install_cost
    # ib_total_cost = (unit_cost + FABRICATION_COST_PER_SQFT + ADDITIONAL_IB_RATE) * sq_ft_used # Not currently used in final display
    return {
        "available_sq_ft": record["available_sq_ft"],
        "material_and_fab": material_and_fab,
        "install_cost": install_cost,
        "total_cost": total_cost,
        # "ib_cost": ib_total_cost, # Not currently used in final display
    }

# --- Streamlit UI Begins Here ---
st.title("Countertop Cost Estimator")
st.write("Get an accurate estimate for your custom countertop project.")

# Branch selection UI (still used for Fabrication Plant logic)
branch_locations = ["Vernon", "Victoria", "Vancouver", "Calgary", "Edmonton", "Saskatoon", "Winnipeg", "Abbotsford"]
selected_branch = st.selectbox("Select Your Branch Location (used for fabrication plant)", branch_locations)

st.info(f"For this test, all inventory data will be loaded from a single sheet tab named: '{SINGLE_TEST_SHEET_NAME}'.")

with st.spinner(f"Loading inventory data from '{SINGLE_TEST_SHEET_NAME}'..."):
    df_inventory = load_data_from_google_sheet(SINGLE_TEST_SHEET_NAME)

if df_inventory is None or df_inventory.empty:
    st.error(f"Failed to load inventory data from '{SINGLE_TEST_SHEET_NAME}'. Please check the error messages above and ensure the sheet is correctly set up and accessible.")
    st.stop()

st.write(f"**Total slabs loaded from '{SINGLE_TEST_SHEET_NAME}':** {len(df_inventory)}")

if "Thickness" in df_inventory.columns:
    df_inventory["Thickness"] = df_inventory["Thickness"].astype(str).str.strip().str.lower()
    thickness_options = sorted(df_inventory["Thickness"].unique())
    if not thickness_options: thickness_options = ["1.2cm", "2cm", "3cm"] # Fallback
    default_thickness = "3cm" if "3cm" in thickness_options else thickness_options[0] if thickness_options else None
    if default_thickness:
        selected_thickness = st.selectbox("Select Thickness", options=thickness_options, index=thickness_options.index(default_thickness))
        df_inventory = df_inventory[df_inventory["Thickness"] == selected_thickness.lower()]
    else:
        st.warning("No thickness options available. Proceeding without thickness filter.")
else:
    st.info("Column 'Thickness' not found. Skipping thickness filter.")

if df_inventory.empty:
    st.warning("No slabs match selected thickness after filtering (or no data loaded).")
    st.stop()

if "Brand" in df_inventory.columns and "Color" in df_inventory.columns:
    df_inventory["Full Name"] = df_inventory["Brand"].astype(str) + " - " + df_inventory["Color"].astype(str)
else:
    st.error("Required 'Brand' or 'Color' columns missing in the loaded data. Cannot proceed.")
    st.stop()

# --- Temporarily commenting out branch-specific material source filtering for single sheet test ---
# This logic might need to be re-evaluated if using a single sheet with mixed location data.
# branch_to_material_sources = {
#     "Vernon": ["Vernon", "Abbotsford"], "Victoria": ["Vernon", "Abbotsford"],
#     "Vancouver": ["Vernon", "Abbotsford"], "Calgary": ["Edmonton", "Saskatoon"],
#     "Edmonton": ["Edmonton", "Saskatoon"], "Saskatoon": ["Edmonton", "Saskatoon"],
#     "Winnipeg": ["Edmonton", "Saskatoon"], "Abbotsford": ["Abbotsford"]
# }
# if "Location" in df_
