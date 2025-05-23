import streamlit as st
import pandas as pd
import requests
import io

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
# No need to import json here if st.secimport streamlit as st
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
        # Retrieve credentials from Streamlit secrets
        # st.secrets["gcp_service_account"] is expected to be a string containing the JSON
        creds_json_str = st.secrets["gcp_service_account"]
        creds_dict = json.loads(creds_json_str)

        credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        
        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_id(SPREADSHEET_ID)
        
        # Select the worksheet by its name (e.g., "Vernon", "Edmonton")
        worksheet = spreadsheet.worksheet(sheet_name) 
        
        # Get all records as a list of dictionaries, then convert to DataFrame
        df = pd.DataFrame(worksheet.get_all_records())

        # --- Data Cleaning and Type Conversion ---
        df.columns = df.columns.str.strip() # Strip whitespace from column names

        if "Serialized On Hand Cost" in df.columns:
            # Replace '$', ',', and any leading/trailing spaces, then convert to float
            df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].astype(str).str.replace("[\\$, ]", "", regex=True).astype(float)
        else:
            st.warning(f"Column 'Serialized On Hand Cost' not found in '{sheet_name}'. Please check your sheet.")
            return pd.DataFrame() # Return empty if critical column missing

        if "Available Sq Ft" in df.columns:
            # Convert to numeric, coercing errors to NaN, then fill NaNs (e.g., with 0 or drop)
            df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors="coerce")
        else:
            st.warning(f"Column 'Available Sq Ft' not found in '{sheet_name}'. Please check your sheet.")
            return pd.DataFrame()

        if "Serial Number" in df.columns:
            df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors="coerce").fillna(0).astype(int)
        else:
            st.warning(f"Column 'Serial Number' not found in '{sheet_name}'. Please check your sheet.")
            # This might not be critical enough to stop, depending on usage.

        # Filter out rows where 'Available Sq Ft' is NaN or 0 to avoid division by zero
        df.dropna(subset=['Available Sq Ft'], inplace=True)
        df = df[df['Available Sq Ft'] > 0]
            
        return df

    except gspread.exceptions.WorksheetNotFound:
        st.error(f"❌ Worksheet '{sheet_name}' not found in the Google Sheet. Please check the sheet name and ensure it exists.")
        st.info("Ensure the tab name in your Google Sheet exactly matches the selection in the app.")
        return None
    except KeyError as ke:
        st.error(f"❌ Missing expected secret or configuration: {ke}. Please ensure 'gcp_service_account' is set in Streamlit Cloud secrets.")
        return None
    except json.JSONDecodeError as jde:
        st.error(f"❌ Error decoding service account JSON from secrets: {jde}. Please check the format in Streamlit Cloud secrets.")
        return None
    except Exception as e:
        st.error(f"❌ Failed to load data from '{sheet_name}' sheet: {e}")
        st.warning("Troubleshooting tips:")
        st.warning("- Ensure the `SPREADSHEET_ID` is correct.")
        st.warning("- Confirm the service account email has 'Viewer' access to your Google Sheet.")
        st.warning("- Verify the 'gcp_service_account' secret is correctly configured in Streamlit Cloud.")
        return None

# --- Cost Calculation Function ---
def calculate_aggregated_costs(record, sq_ft_used):
    """Calculates various costs based on a single inventory record and square footage needed."""
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
st.write("Get an accurate estimate for your custom countertop project")

# --- Branch Selector (This drives which Google Sheet tab is loaded) ---
# IMPORTANT: These names MUST exactly match the tab names in your Google Sheet!
branch_locations = ["Vernon", "Victoria", "Vancouver", "Calgary", "Edmonton", "Saskatoon", "Winnipeg", "Abbotsford"]
selected_branch = st.selectbox("Select Your Branch Location", branch_locations)

with st.spinner(f"Loading inventory data for {selected_branch} branch..."):
    df_inventory = load_data_from_google_sheet(selected_branch)
    
if df_inventory is None or df_inventory.empty:
    st.warning(f"Could not load or found no usable inventory data for the '{selected_branch}' branch.")
    st.stop()

st.write(f"**Total slabs loaded for {selected_branch}:** {len(df_inventory)}")

# --- Thickness Selector ---
# Ensure 'Thickness' column exists and is handled gracefully
if "Thickness" in df_inventory.columns:
    df_inventory["Thickness"] = df_inventory["Thickness"].astype(str).str.strip().str.lower()
    thickness_options = ["1.2cm", "2cm", "3cm"]
    selected_thickness = st.selectbox("Select Thickness", options=thickness_options, index=thickness_options.index("3cm")) # Default to 3cm
    df_inventory = df_inventory[df_inventory["Thickness"] == selected_thickness.lower()]
else:
    st.warning("Column 'Thickness' not found in the loaded sheet. Skipping thickness filter.")

if df_inventory.empty:
    st.warning("No slabs match the selected thickness. Please adjust your filter or check data.")
    st.stop()

# --- Create Full Name field ---
if "Brand" in df_inventory.columns and "Color" in df_inventory.columns:
    df_inventory["Full Name"] = df_inventory["Brand"].astype(str) + " - " + df_inventory["Color"].astype(str)
else:
    st.error("Required columns 'Brand' or 'Color' are missing from the loaded sheet. Cannot proceed.")
    st.stop()

# --- Branch to Material Location Access ---
# This dictionary defines which physical inventory locations a sales branch can pull material from.
# The 'Location' column in your Google Sheet should denote the physical warehouse location of the slab.
branch_to_material_sources = {
    "Vernon": ["Vernon", "Abbotsford"],
    "Victoria": ["Vernon", "Abbotsford"],
    "Vancouver": ["Vernon", "Abbotsford"],
    "Calgary": ["Edmonton", "Saskatoon"],
    "Edmonton": ["Edmonton", "Saskatoon"],
    "Saskatoon": ["Edmonton", "Saskatoon"],
    "Winnipeg": ["Edmonton", "Saskatoon"],
    "Abbotsford": ["Abbotsford"] # Assuming Abbotsford can also be a sales branch and draw from itself
}

# Filter `df_inventory` based on `Location` column in the loaded sheet
if "Location" in df_inventory.columns:
    allowed_material_locations = branch_to_material_sources.get(selected_branch, [])
    if allowed_material_locations:
        df_inventory = df_inventory[df_inventory["Location"].isin(allowed_material_locations)]
    else:
        st.info(f"No specific material sources defined for '{selected_branch}'. Showing all materials from this sheet.")
        # If no specific sources are defined, you might decide to stop or just show all data in the selected sheet.
else:
    st.warning("The 'Location' column is missing from your Google Sheet. Cannot filter by material source.")

if df_inventory.empty:
    st.warning("No slabs available after applying location filters. Please check your data or branch settings.")
    st.stop()

# --- Determine Fabrication Plant ---
def get_fabrication_plant(branch):
    """Determines the primary fabrication plant based on the selected branch location."""
    if branch in ["Vernon", "Victoria", "Vancouver", "Abbotsford"]:
        return "Abbotsford"
    elif branch in ["Calgary", "Edmonton", "Saskatoon", "Winnipeg"]:
        return "Saskatoon"
    else:
        return "Unknown" # Should not happen if branch_locations is exhaustive

fabrication_plant = get_fabrication_plant(selected_branch)
st.markdown(f"**Fabrication Plant for {selected_branch} orders:** {fabrication_plant}")

# --- Compute Unit Cost ---
# This should be safe now after initial cleaning in load_data_from_google_sheet
df_inventory["unit_cost"] = df_inventory["Serialized On Hand Cost"] / df_inventory["Available Sq Ft"]

# --- Square Footage Input ---
sq_ft_input = st.number_input("Enter Square Footage Needed", min_value=1, value=40, step=1)
sq_ft_used = max(sq_ft_input, MINIMUM_SQ_FT)

if sq_ft_input < MINIMUM_SQ_FT:
    st.info(f"Minimum square footage is {MINIMUM_SQ_FT} sq ft. Using {MINIMUM_SQ_FT} sq ft for pricing.")

# --- Aggregate Data by Slab ---
# Group by Full Name and Location to get aggregated slab info
df_agg = (
    df_inventory.groupby(["Full Name", "Location"]).agg(
        available_sq_ft=("Available Sq Ft", "sum"),
        unit_cost=("unit_cost", "max"), # Use max unit_cost if multiple entries for same name/location
        slab_count=("Serial Number", "count"),
        serial_numbers=("Serial Number", lambda x: ", ".join(x.astype(str).unique())), # Concatenate unique serial numbers
    ).reset_index()
)

# Apply material buffer requirement
required_material = sq_ft_used * 1.1 # 10% buffer
df_agg = df_agg[df_agg["available_sq_ft"] >= required_material]

if df_agg.empty:
    st.error("No colors have enough total material (including buffer) for the selected square footage.")
    st.stop()

# --- Final Price Calculation ---
df_agg["final_price"] = df_agg.apply(lambda row: calculate_aggregated_costs(row, sq_ft_used)["total_cost"] * (1 + GST_RATE), axis=1)

df_valid = df_agg[df_agg["final_price"] > 0]
if df_valid.empty:
    st.error("No valid slab prices available after calculations (e.g., zero cost).")
    st.stop()

# --- Price Filtering Slider ---
min_possible_cost = int(df_valid["final_price"].min())
max_possible_cost = int(df_valid["final_price"].max())

max_job_cost = st.slider("Select Maximum Job Cost ($)", min_value=min_possible_cost, max_value=max_possible_cost, value=max_possible_cost, step=100)

df_agg_filtered = df_agg[df_agg["final_price"] <= max_job_cost]
if df_agg_filtered.empty:
    st.error("No colors available within the selected cost range.")
    st.stop()

# --- Selectbox for Color/Material ---
records = df_agg_filtered.to_dict("records")
selected_record = st.selectbox(
    "Select Color",
    options=records,
    format_func=lambda record: f"{record['Full Name']} - (${record['final_price'] / sq_ft_used:.2f}/sq ft)"
)

# --- Display Selected Slab Information ---
st.markdown(f"**Total Available Sq Ft (Selected Color):** {selected_record['available_sq_ft']:.0f} sq.ft")
st.markdown(f"**Number of Slabs (Selected Color):** {selected_record['slab_count']}")

# --- Google Image Search Link ---
search_url = f"https://www.google.com/search?q={selected_record['Full Name'].replace(' ', '+')}+countertop"
st.markdown(f"[🔎 Google Image Search for {selected_record['Full Name']}]({search_url})")

# --- Edge Profile Selection ---
edge_profiles = ["Crescent", "Basin", "Boulder", "Volcanic", "Piedmont", "Summit", "Seacliff", "Alpine", "Treeline"]
selected_edge_profile = st.selectbox("Select Edge Profile", options=edge_profiles, index=edge_profiles.index("Seacliff"))

# --- Final Cost Summary ---
costs = calculate_aggregated_costs(selected_record, sq_ft_used)
sub_total = costs["total_cost"]
gst_amount = sub_total * GST_RATE
final_price = (sub_total + gst_amount) * (1 + FINAL_MARKUP_PERCENTAGE)

with st.expander("View Subtotal & GST"):
    st.markdown(f"**Subtotal (before tax):** ${sub_total:,.2f}")
    st.markdown(f"**GST (5%):** ${gst_amount:,.2f}")

st.markdown(f"### Your Total Price: :green[${final_price:,.2f}]")

if selected_record["slab_count"] > 1:
    st.info("Note: Multiple slabs are being used for this color; colors may vary due to natural variations.")

# --- Detailed Breakdown (Password Protected) ---
# --- THIS ENTIRE SECTION IS COMMENTED OUT FOR DEBUGGING THE SYNTAX ERROR ---
# pwd = st.text_input("Enter password to view detailed breakdown", type="password")
# if pwd == "floform": # This is a simple, hardcoded password. For real apps, use proper auth.
#     with st.expander("View Detailed Breakdown"):
#         st.markdown(f"- **Slab:** {selected_record['Full Name']}")
#         st.markdown(f"- **Material Location:** {selected_record['Location']}")
#         st.markdown(f"- **Fabrication Plant:** {fabrication_plant}")
#         st.markdown(f"- **Edge Profile:** {selected_edge_profile}")
#         st.markdown(f"- **Thickness:** {selected_thickness}")
#         st.markdown(f"- **Square Footage (for pricing):** {sq_ft_used}")
#         st.markdown(f"- **Slab Sq Ft (Aggregated Available):** {selected_record['available_sq_ft']:.2f} sq.ft")
#         st.markdown(f"- **Slab Count:** {selected_record['slab_count']}")
#         st.markdown(f"- **Serial Numbers:** {selected_record['serial_numbers']}")
#         st.markdown(f"- **Material & Fabrication:** ${costs['material_and_fab']:,.2f}")
#         st.markdown(f"- **Installation:** ${costs['install_cost']:,.2f}")
#         st.markdown(f"- **IB (Industry-Specific Base Cost):** ${costs['ib_cost']:,.2f}")
#         st.markdown(f"- **Subtotal (before tax):** ${sub_total:,.2f}")
#         st.markdown(f"- **GST (5%):** ${gst_amount:,.2f}")
#         st.markdown(f"- **Final Price (with markup):** ${final_price:,.2f}")
# else:
#     st.info("Enter password to view detailed breakdown.")
# --- END OF COMMENTED OUT SECTION ---rets handles parsing for you,
# but gspread.service_account_from_dictimport streamlit as st
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
SPREADSHEET_ID = "1vSgq5Sa6y-d9SoWKngBEBwpwlFedFL66P5GqW0S7qq-CdZHiOyevSgNnmzApVxR_2RuwknpiIRxPZ_T" # <<< REPLACE THIS!

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly'] # Read-only access to sheets

# --- Function to load data from a specific Google Sheet tab ---
@st.cache_data(show_spinner=False)
def load_data_from_google_sheet(sheet_name):
    """
    Loads data from a specified tab (worksheet) in a Google Sheet using the Sheets API.
    Assumes gcp_service_account secret is configured in Streamlit Cloud.
    """
    try:
        # Retrieve credentials from Streamlit secrets
        # st.secrets["gcp_service_account"] is expected to be a string containing the JSON
        creds_json_str = st.secrets["gcp_service_account"]
        creds_dict = json.loads(creds_json_str)

        credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        
        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_id(SPREADSHEET_ID)
        
        # Select the worksheet by its name (e.g., "Vernon", "Edmonton")
        worksheet = spreadsheet.worksheet(sheet_name) 
        
        # Get all records as a list of dictionaries, then convert to DataFrame
        df = pd.DataFrame(worksheet.get_all_records())

        # --- Data Cleaning and Type Conversion ---
        df.columns = df.columns.str.strip() # Strip whitespace from column names

        if "Serialized On Hand Cost" in df.columns:
            # Replace '$', ',', and any leading/trailing spaces, then convert to float
            df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].astype(str).str.replace("[\\$, ]", "", regex=True).astype(float)
        else:
            st.warning(f"Column 'Serialized On Hand Cost' not found in '{sheet_name}'. Please check your sheet.")
            return pd.DataFrame() # Return empty if critical column missing

        if "Available Sq Ft" in df.columns:
            # Convert to numeric, coercing errors to NaN, then fill NaNs (e.g., with 0 or drop)
            df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors="coerce")
        else:
            st.warning(f"Column 'Available Sq Ft' not found in '{sheet_name}'. Please check your sheet.")
            return pd.DataFrame()

        if "Serial Number" in df.columns:
            df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors="coerce").fillna(0).astype(int)
        else:
            st.warning(f"Column 'Serial Number' not found in '{sheet_name}'. Please check your sheet.")
            # This might not be critical enough to stop, depending on usage.

        # Filter out rows where 'Available Sq Ft' is NaN or 0 to avoid division by zero
        df.dropna(subset=['Available Sq Ft'], inplace=True)
        df = df[df['Available Sq Ft'] > 0]
            
        return df

    except gspread.exceptions.WorksheetNotFound:
        st.error(f"❌ Worksheet '{sheet_name}' not found in the Google Sheet. Please check the sheet name and ensure it exists.")
        st.info("Ensure the tab name in your Google Sheet exactly matches the selection in the app.")
        return None
    except KeyError as ke:
        st.error(f"❌ Missing expected secret or configuration: {ke}. Please ensure 'gcp_service_account' is set in Streamlit Cloud secrets.")
        return None
    except Exception as e:
        st.error(f"❌ Failed to load data from '{sheet_name}' sheet: {e}")
        st.warning("Troubleshooting tips:")
        st.warning("- Ensure the `SPREADSHEET_ID` is correct.")
        st.warning("- Confirm the service account email has 'Viewer' access to your Google Sheet.")
        st.warning("- Verify the 'gcp_service_account' secret is correctly configured in Streamlit Cloud.")
        return None

# --- Cost Calculation Function ---
def calculate_aggregated_costs(record, sq_ft_used):
    """Calculates various costs based on a single inventory record and square footage needed."""
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
st.write("Get an accurate estimate for your custom countertop project")

# --- Branch Selector (This drives which Google Sheet tab is loaded) ---
# IMPORTANT: These names MUST exactly match the tab names in your Google Sheet!
branch_locations = ["Vernon", "Victoria", "Vancouver", "Calgary", "Edmonton", "Saskatoon", "Winnipeg", "Abbotsford"]
selected_branch = st.selectbox("Select Your Branch Location", branch_locations)

with st.spinner(f"Loading inventory data for {selected_branch} branch..."):
    df_inventory = load_data_from_google_sheet(selected_branch)
    
if df_inventory is None or df_inventory.empty:
    st.warning(f"Could not load or found no usable inventory data for the '{selected_branch}' branch.")
    st.stop()

st.write(f"**Total slabs loaded for {selected_branch}:** {len(df_inventory)}")

# --- Thickness Selector ---
# Ensure 'Thickness' column exists and is handled gracefully
if "Thickness" in df_inventory.columns:
    df_inventory["Thickness"] = df_inventory["Thickness"].astype(str).str.strip().str.lower()
    thickness_options = ["1.2cm", "2cm", "3cm"]
    selected_thickness = st.selectbox("Select Thickness", options=thickness_options, index=thickness_options.index("3cm")) # Default to 3cm
    df_inventory = df_inventory[df_inventory["Thickness"] == selected_thickness.lower()]
else:
    st.warning("Column 'Thickness' not found in the loaded sheet. Skipping thickness filter.")

if df_inventory.empty:
    st.warning("No slabs match the selected thickness. Please adjust your filter or check data.")
    st.stop()

# --- Create Full Name field ---
if "Brand" in df_inventory.columns and "Color" in df_inventory.columns:
    df_inventory["Full Name"] = df_inventory["Brand"].astype(str) + " - " + df_inventory["Color"].astype(str)
else:
    st.error("Required columns 'Brand' or 'Color' are missing from the loaded sheet. Cannot proceed.")
    st.stop()

# --- Branch to Material Location Access ---
# This dictionary defines which physical inventory locations a sales branch can pull material from.
# The 'Location' column in your Google Sheet should denote the physical warehouse location of the slab.
branch_to_material_sources = {
    "Vernon": ["Vernon", "Abbotsford"],
    "Victoria": ["Vernon", "Abbotsford"],
    "Vancouver": ["Vernon", "Abbotsford"],
    "Calgary": ["Edmonton", "Saskatoon"],
    "Edmonton": ["Edmonton", "Saskatoon"],
    "Saskatoon": ["Edmonton", "Saskatoon"],
    "Winnipeg": ["Edmonton", "Saskatoon"],
    "Abbotsford": ["Abbotsford"] # Assuming Abbotsford can also be a sales branch and draw from itself
}

# Filter `df_inventory` based on `Location` column in the loaded sheet
if "Location" in df_inventory.columns:
    allowed_material_locations = branch_to_material_sources.get(selected_branch, [])
    if allowed_material_locations:
        df_inventory = df_inventory[df_inventory["Location"].isin(allowed_material_locations)]
    else:
        st.info(f"No specific material sources defined for '{selected_branch}'. Showing all materials from this sheet.")
        # If no specific sources are defined, you might decide to stop or just show all data in the selected sheet.
else:
    st.warning("The 'Location' column is missing from your Google Sheet. Cannot filter by material source.")

if df_inventory.empty:
    st.warning("No slabs available after applying location filters. Please check your data or branch settings.")
    st.stop()

# --- Determine Fabrication Plant ---
def get_fabrication_plant(branch):
    """Determines the primary fabrication plant based on the selected branch location."""
    if branch in ["Vernon", "Victoria", "Vancouver", "Abbotsford"]:
        return "Abbotsford"
    elif branch in ["Calgary", "Edmonton", "Saskatoon", "Winnipeg"]:
        return "Saskatoon"
    else:
        return "Unknown" # Should not happen if branch_locations is exhaustive

fabrication_plant = get_fabrication_plant(selected_branch)
st.markdown(f"**Fabrication Plant for {selected_branch} orders:** {fabrication_plant}")

# --- Compute Unit Cost ---
# This should be safe now after initial cleaning in load_data_from_google_sheet
df_inventory["unit_cost"] = df_inventory["Serialized On Hand Cost"] / df_inventory["Available Sq Ft"]

# --- Square Footage Input ---
sq_ft_input = st.number_input("Enter Square Footage Needed", min_value=1, value=40, step=1)
sq_ft_used = max(sq_ft_input, MINIMUM_SQ_FT)

if sq_ft_input < MINIMUM_SQ_FT:
    st.info(f"Minimum square footage is {MINIMUM_SQ_FT} sq ft. Using {MINIMUM_SQ_FT} sq ft for pricing.")

# --- Aggregate Data by Slab ---
# Group by Full Name and Location to get aggregated slab info
df_agg = (
    df_inventory.groupby(["Full Name", "Location"]).agg(
        available_sq_ft=("Available Sq Ft", "sum"),
        unit_cost=("unit_cost", "max"), # Use max unit_cost if multiple entries for same name/location
        slab_count=("Serial Number", "count"),
        serial_numbers=("Serial Number", lambda x: ", ".join(x.astype(str).unique())), # Concatenate unique serial numbers
    ).reset_index()
)

# Apply material buffer requirement
required_material = sq_ft_used * 1.1 # 10% buffer
df_agg = df_agg[df_agg["available_sq_ft"] >= required_material]

if df_agg.empty:
    st.error("No colors have enough total material (including buffer) for the selected square footage.")
    st.stop()

# --- Final Price Calculation ---
df_agg["final_price"] = df_agg.apply(lambda row: calculate_aggregated_costs(row, sq_ft_used)["total_cost"] * (1 + GST_RATE), axis=1)

df_valid = df_agg[df_agg["final_price"] > 0]
if df_valid.empty:
    st.error("No valid slab prices available after calculations (e.g., zero cost).")
    st.stop()

# --- Price Filtering Slider ---
min_possible_cost = int(df_valid["final_price"].min())
max_possible_cost = int(df_valid["final_price"].max())

max_job_cost = st.slider("Select Maximum Job Cost ($)", min_value=min_possible_cost, max_value=max_possible_cost, value=max_possible_cost, step=100)

df_agg_filtered = df_agg[df_agg["final_price"] <= max_job_cost]
if df_agg_filtered.empty:
    st.error("No colors available within the selected cost range.")
    st.stop()

# --- Selectbox for Color/Material ---
records = df_agg_filtered.to_dict("records")
selected_record = st.selectbox(
    "Select Color",
    options=records,
    format_func=lambda record: f"{record['Full Name']} - (${record['final_price'] / sq_ft_used:.2f}/sq ft)"
)

# --- Display Selected Slab Information ---
st.markdown(f"**Total Available Sq Ft (Selected Color):** {selected_record['available_sq_ft']:.0f} sq.ft")
st.markdown(f"**Number of Slabs (Selected Color):** {selected_record['slab_count']}")

# --- Google Image Search Link ---
search_url = f"https://www.google.com/search?q={selected_record['Full Name'].replace(' ', '+')}+countertop"
st.markdown(f"[🔎 Google Image Search for {selected_record['Full Name']}]({search_url})")

# --- Edge Profile Selection ---
edge_profiles = ["Crescent", "Basin", "Boulder", "Volcanic", "Piedmont", "Summit", "Seacliff", "Alpine", "Treeline"]
selected_edge_profile = st.selectbox("Select Edge Profile", options=edge_profiles, index=edge_profiles.index("Seacliff"))

# --- Final Cost Summary ---
costs = calculate_aggregated_costs(selected_record, sq_ft_used)
sub_total = costs["total_cost"]
gst_amount = sub_total * GST_RATE
final_price = (sub_total + gst_amount) * (1 + FINAL_MARKUP_PERCENTAGE)

with st.expander("View Subtotal & GST"):
    st.markdown(f"**Subtotal (before tax):** ${sub_total:,.2f}")
    st.markdown(f"**GST (5%):** ${gst_amount:,.2f}")

st.markdown(f"### Your Total Price: :green[${final_price:,.2f}]")

if selected_record["slab_count"] > 1:
    st.info("Note: Multiple slabs are being used for this color; colors may vary due to natural variations.")

# --- Detailed Breakdown (Password Protected) ---
pwd = st.text_input("Enter password to view detailed breakdown", type="password")
if pwd == "floform": # This is a simple, hardcoded password. For real apps, use proper auth.
    with st.expander("View Detailed Breakdown"):
        st.markdown(f"- **Slab:** {selected_record['Full Name']}")
        st.markdown(f"- **Material Location:** {selected_record['Location']}")
        st.markdown(f"- **Fabrication Plant:** {fabrication_plant}")
        st.markdown(f"- **Edge Profile:** {selected_edge_profile}")
        st.markdown(f"- **Thickness:** {selected_thickness}")
        st.markdown(f"- **Square Footage (for pricing):** {sq_ft_used}")
        st.markdown(f"- **Slab Sq Ft (Aggregated Available):** {selected_record['available_sq_ft']:.2f} sq.ft")
        st.markdown(f"- **Slab Count:** {selected_record['slab_count']}")
        st.markdown(f"- **Serial Numbers:** {selected_record['serial_numbers']}")
        st.markdown(f"- **Material & Fabrication:** ${costs['material_and_fab']:,.2f}")
        st.markdown(f"- **Installation:** ${costs['install_cost']:,.2f}")
        st.markdown(f"- **IB (Industry-Specific Base Cost):** ${costs['ib_cost']:,.2f}")
        st.markdown(f"- **Subtotal (before tax):** ${sub_total:,.2f}")
        st.markdown(f"- **GST (5%):** ${gst_amount:,.2f}")
        st.markdown(f"- **Final Price (with markup):** ${final_price:,.2f}")
else:
    st.info("Enter password to view detailed breakdown.") expects a dict.
# st.secrets['gcp_service_account'] should already be a dict if formatted correctly as a string in secrets.

# --- Configurations (keep as is) ---
MINIMUM_SQ_FT = 35
# ... other constants ...
GST_RATE = 0.05
FINAL_MARKUP_PERCENTAGE = 0.25

# --- Google Sheets API Configuration ---
# SPREADSHEET_ID should still be defined here or fetched from secrets if you prefer
SPREADSHEET_ID = "1vSgq5Sa6y-d9SoWKngBEBwpwlFedFL66P5GqW0S7qq-CdZHiOyevSgNnmzApVxR_2RuwknpiIRxPZ_T" # <<< YOUR SPREADSHEET ID
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

@st.cache_data(show_spinner=False)
def load_data_from_google_sheet(sheet_name):
    try:
        # Use Streamlit Secrets for credentials
        # st.secrets["gcp_service_account"] should directly give you the dictionary
        # if the TOML string was parsed correctly by Streamlit.
        # If it's still a string, you might need json.loads()
        creds_json_str = st.secrets["gcp_service_account"]
        # It's good practice to ensure it's a dictionary
        if isinstance(creds_json_str, str):
             # This import might be needed if creds_json_str is a string
            import json
            creds_dict = json.loads(creds_json_str)
        else:
            # If Streamlit already parsed it to a dict (common for complex TOML values)
            creds_dict = creds_json_str

        credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_id(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(sheet_name)
        df = pd.DataFrame(worksheet.get_all_records())

        # ... (rest of your data cleaning logic)
        df.columns = df.columns.str.strip()
        if "Serialized On Hand Cost" in df.columns:
            df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].astype(str).str.replace("[\\$, ]", "", regex=True).astype(float)
        if "Available Sq Ft" in df.columns:
            df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors="coerce")
        if "Serial Number" in df.columns:
            df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors="coerce").fillna(0).astype(int)

        return df
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"❌ Worksheet '{sheet_name}' not found in the Google Sheet. Please check the sheet name and ensure it exists.")
        return None
    except Exception as e:
        st.error(f"❌ Failed to load data from '{sheet_name}' sheet: {e}")
        st.error("Make sure the 'gcp_service_account' secret is correctly configured in Streamlit Cloud and your Google Sheet is shared with the service account email.")
        return None

# ... (rest of your Streamlit app code from the previous response) ...

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
ADDITIONAL_IB_RATE = 0
GST_RATE = 0.05
FINAL_MARKUP_PERCENTAGE = 0.25

GOOGLE_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vSgq5Sa6y-d9SoWKngBEBwpwlFedFL66P5GqW0S7qq-CdZHiOyevSgNnmzApVxR_2RuwknpiIRxPZ_T/pub?output=csv"
)

@st.cache_data(show_spinner=False)
def load_data():
    try:
        response = requests.get(GOOGLE_SHEET_URL)
        if response.status_code != 200:
            st.error("❌ Error loading the file. Check the Google Sheets URL.")
            return None
        df = pd.read_csv(io.StringIO(response.text))
        df.columns = df.columns.str.strip()
        if "Serialized On Hand Cost" in df.columns:
            df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].replace("[\\$,]", "", regex=True).astype(float)
        if "Available Sq Ft" in df.columns:
            df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors="coerce")
        if "Serial Number" in df.columns:
            df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors="coerce").fillna(0).astype(int)
        return df
    except Exception as e:
        st.error(f"❌ Failed to load data: {e}")
        return None

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

st.title("Countertop Cost Estimator")
st.write("Get an accurate estimate for your custom countertop project")

with st.spinner("Loading data..."):
    df_inventory = load_data()
if df_inventory is None:
    st.stop()

st.write(f"**Total slabs loaded:** {len(df_inventory)}")

# --- Thickness Selector ---
df_inventory["Thickness"] = df_inventory["Thickness"].astype(str).str.strip().str.lower()
thickness_options = ["1.2cm", "2cm", "3cm"]
selected_thickness = st.selectbox("Select Thickness", options=thickness_options, index=2)
df_inventory = df_inventory[df_inventory["Thickness"] == selected_thickness.lower()]

if df_inventory.empty:
    st.warning("No slabs match the selected thickness. Please adjust your filter.")
    st.stop()

# --- Create Full Name field ---
if "Brand" in df_inventory.columns and "Color" in df_inventory.columns:
    df_inventory["Full Name"] = df_inventory["Brand"].astype(str) + " - " + df_inventory["Color"].astype(str)
else:
    st.error("Required columns 'Brand' or 'Color' are missing.")
    st.stop()

# --- Branch Selector ---
branch_locations = ["Vernon", "Victoria", "Vancouver", "Calgary", "Edmonton", "Saskatoon", "Winnipeg"]
selected_branch = st.selectbox("Select Your Branch Location", branch_locations)

# --- Branch to Material Location Access ---
branch_to_material_sources = {
    "Vernon": ["Vernon", "Abbotsford"],
    "Victoria": ["Vernon", "Abbotsford"],
    "Vancouver": ["Vernon", "Abbotsford"],
    "Calgary": ["Edmonton", "Saskatoon"],
    "Edmonton": ["Edmonton", "Saskatoon"],
    "Saskatoon": ["Edmonton", "Saskatoon"],
    "Winnipeg": ["Edmonton", "Saskatoon"],
}

df_inventory = df_inventory[df_inventory["Location"].isin(branch_to_material_sources.get(selected_branch, []))]

# --- Determine Fabrication Plant ---
def get_fabrication_plant(branch):
    if branch in ["Vernon", "Victoria", "Vancouver"]:
        return "Abbotsford"
    elif branch in ["Calgary", "Edmonton", "Saskatoon", "Winnipeg"]:
        return "Saskatoon"
    else:
        return "Unknown"

fabrication_plant = get_fabrication_plant(selected_branch)
st.markdown(f"**Fabrication Plant:** {fabrication_plant}")

# --- Compute Unit Cost ---
df_inventory["unit_cost"] = df_inventory["Serialized On Hand Cost"] / df_inventory["Available Sq Ft"]

# --- Square Footage Input ---
sq_ft_input = st.number_input("Enter Square Footage Needed", min_value=1, value=40, step=1)
sq_ft_used = max(sq_ft_input, MINIMUM_SQ_FT)

if sq_ft_input < MINIMUM_SQ_FT:
    st.info(f"Minimum square footage is {MINIMUM_SQ_FT} sq ft. Using {MINIMUM_SQ_FT} sq ft for pricing.")

# --- Aggregate Data by Slab ---
df_agg = (
    df_inventory.groupby(["Full Name", "Location"]).agg(
        available_sq_ft=("Available Sq Ft", "sum"),
        unit_cost=("unit_cost", "max"),
        slab_count=("Serial Number", "count"),
        serial_numbers=("Serial Number", lambda x: ", ".join(x.astype(str))),
    ).reset_index()
)

required_material = sq_ft_used * 1.1
df_agg = df_agg[df_agg["available_sq_ft"] >= required_material]

if df_agg.empty:
    st.error("No colors have enough total material for the selected square footage.")
    st.stop()

# --- Final Price Calculation ---
df_agg["final_price"] = df_agg.apply(lambda row: calculate_aggregated_costs(row, sq_ft_used)["total_cost"] * (1 + GST_RATE), axis=1)

df_valid = df_agg[df_agg["final_price"] > 0]
if df_valid.empty:
    st.error("No valid slab prices available.")
    st.stop()

min_possible_cost = int(df_valid["final_price"].min())
max_possible_cost = int(df_valid["final_price"].max())

max_job_cost = st.slider("Select Maximum Job Cost ($)", min_value=min_possible_cost, max_value=max_possible_cost, value=max_possible_cost, step=100)

df_agg_filtered = df_agg[df_agg["final_price"] <= max_job_cost]
if df_agg_filtered.empty:
    st.error("No colors available within the selected cost range.")
    st.stop()

records = df_agg_filtered.to_dict("records")
selected_record = st.selectbox(
    "Select Color",
    options=records,
    format_func=lambda record: f"{record['Full Name']} - (${record['final_price'] / sq_ft_used:.2f}/sq ft)"
)

st.markdown(f"**Total Available Sq Ft:** {selected_record['available_sq_ft']:.0f} sq.ft")
st.markdown(f"**Number of Slabs:** {selected_record['slab_count']}")

search_url = f"https://www.google.com/search?q={selected_record['Full Name'].replace(' ', '+')}+countertop"
st.markdown(f"[🔎 Google Image Search]({search_url})")

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

if selected_record["slab_count"] > 1:
    st.info("Note: Multiple slabs are being used for this color; colors may vary.")

pwd = st.text_input("Enter password to view detailed breakdown", type="password")
if pwd == "floform":
    with st.expander("View Detailed Breakdown"):
        st.markdown(f"- **Slab:** {selected_record['Full Name']}")
        st.markdown(f"- **Material Location:** {selected_record['Location']}")
        st.markdown(f"- **Fabrication Plant:** {fabrication_plant}")
        st.markdown(f"- **Edge Profile:** {selected_edge_profile}")
        st.markdown(f"- **Thickness:** {selected_thickness}")
        st.markdown(f"- **Square Footage (used):** {sq_ft_used}")
        st.markdown(f"- **Slab Sq Ft (Aggregated):** {selected_record['available_sq_ft']:.2f} sq.ft")
        st.markdown(f"- **Slab Count:** {selected_record['slab_count']}")
        st.markdown(f"- **Serial Numbers:** {selected_record['serial_numbers']}")
        st.markdown(f"- **Material & Fabrication:** ${costs['material_and_fab']:,.2f}")
        st.markdown(f"- **Installation:** ${costs['install_cost']:,.2f}")
        st.markdown(f"- **IB:** ${costs['ib_cost']:,.2f}")
        st.markdown(f"- **Subtotal (before tax):** ${sub_total:,.2f}")
        st.markdown(f"- **GST (5%):** ${gst_amount:,.2f}")
        st.markdown(f"- **Final Price (with markup):** ${final_price:,.2f}")
else:
    st.info("Enter password to view detailed breakdown.")
