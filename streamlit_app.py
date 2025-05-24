import streamlit as st
import pandas as pd
import gspread # Used for Google Sheets API interaction
# from google.oauth2.service_account import Credentials # Not directly used with service_account_from_dict
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
ADDITIONAL_IB_RATE = 0
GST_RATE = 0.05
FINAL_MARKUP_PERCENTAGE = 0.25

# --- Google Sheets API Configuration ---
SPREADSHEET_ID = "166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ" # Corrected ID
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# --- Function to load data from Google Sheets (Debugging messages removed) ---
@st.cache_data(show_spinner=False)
def load_data_from_google_sheet(sheet_name_to_load):
    creds_dict = None
    try:
        creds_json_str = st.secrets["gcp_service_account"]
        creds_dict = json.loads(creds_json_str)
    except KeyError:
        st.error("❌ Critical Error: 'gcp_service_account' secret not found. App cannot access data. Please contact administrator.")
        return None
    except json.JSONDecodeError as jde:
        st.error(f"❌ Critical Error: Failed to parse Google service account credentials: {jde}. Please contact administrator.")
        return None
    except Exception as e:
        st.error(f"❌ Critical Error: Unexpected issue loading credentials: {e}. Please contact administrator.")
        return None

    gc = None
    try:
        gc = gspread.service_account_from_dict(creds_dict, scopes=SCOPES)
    except Exception as e:
        st.error(f"❌ Critical Error: Failed to initialize Google Sheets client: {e}. Please contact administrator.")
        return None

    if gc is None:
        st.error("❌ Critical Error: Google Sheets client object is None after initialization. Please contact administrator.")
        return None

    open_method = None
    gc_attributes = dir(gc) # Check attributes once

    if 'open_by_key' in gc_attributes:
        open_method = gc.open_by_key
    elif 'open_by_id' in gc_attributes: 
        open_method = gc.open_by_id
    else:
        st.error(f"❌ Critical Error: Required gspread methods ('open_by_key' or 'open_by_id') not found on client object. App may be misconfigured. Please contact administrator.")
        return None

    spreadsheet = None
    try:
        spreadsheet = open_method(SPREADSHEET_ID)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ Error: Spreadsheet not found. Please ensure the data source is correctly set up and shared with: {creds_dict.get('client_email')}")
        return None
    except gspread.exceptions.APIError as apie:
        st.error(f"❌ Error: A Google Sheets API error occurred: {apie}. The sheet might be inaccessible or API limits reached.")
        return None
    except Exception as e:
        st.error(f"❌ Error: Unexpected issue opening spreadsheet: {e}.")
        return None

    if spreadsheet is None:
        st.error("❌ Error: Spreadsheet object could not be opened. Cannot proceed.")
        return None

    worksheet = None
    try:
        worksheet = spreadsheet.worksheet(sheet_name_to_load)
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"❌ Error: Worksheet tab '{sheet_name_to_load}' not found in the spreadsheet '{spreadsheet.title}'. Please check tab name (it's case-sensitive).")
        return None
    except Exception as e:
        st.error(f"❌ Error: Unexpected issue opening worksheet '{sheet_name_to_load}': {e}.")
        return None

    if worksheet is None:
        st.error(f"❌ Error: Worksheet object for '{sheet_name_to_load}' could not be opened. Cannot proceed.")
        return None
        
    df = None
    try:
        df = pd.DataFrame(worksheet.get_all_records())
    except Exception as e:
        st.error(f"❌ Error: Could not retrieve records from worksheet '{worksheet.title}': {e}.")
        return None

    if df is None or df.empty:
        st.warning(f"⚠️ No data found in worksheet '{worksheet.title}' or failed to create DataFrame.")
        return pd.DataFrame()

    try:
        df.columns = df.columns.str.strip()
        if "Serialized On Hand Cost" not in df.columns or "Available Sq Ft" not in df.columns:
            st.error(f"❌ Error: Critical data columns ('Serialized On Hand Cost' or 'Available Sq Ft') are missing from the sheet '{sheet_name_to_load}'. Columns found: {list(df.columns)}")
            return pd.DataFrame() 
        
        df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].astype(str).str.replace("[\\$, ]", "", regex=True).str.strip()
        df["Serialized On Hand Cost"] = pd.to_numeric(df["Serialized On Hand Cost"], errors='coerce')

        df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors='coerce')

        if "Serial Number" in df.columns:
            df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors='coerce').fillna(0).astype(int)
        else:
            # This is more of an info, not an error that stops the app
            # st.info(f"ℹ️ Column 'Serial Number' not found in '{sheet_name_to_load}'. Defaulting to 0.")
            df["Serial Number"] = 0 

        df.dropna(subset=['Serialized On Hand Cost', 'Available Sq Ft'], inplace=True) 
        df = df[df['Available Sq Ft'] > 0] 

        if df.empty:
            st.warning(f"⚠️ No valid data rows remaining in '{sheet_name_to_load}' after cleaning and filtering for essential numeric values.")
            return pd.DataFrame()
        return df
    except Exception as e:
        st.error(f"❌ Error: Failed during data processing for sheet '{sheet_name_to_load}': {e}.")
        return pd.DataFrame()

# --- Cost Calculation Function ---
def calculate_aggregated_costs(record, sq_ft_used):
    unit_cost = record.get("unit_cost", 0) 
    if unit_cost is None: unit_cost = 0 

    material_cost_with_markup = unit_cost * MARKUP_FACTOR * sq_ft_used
    fabrication_total = FABRICATION_COST_PER_SQFT * sq_ft_used
    material_and_fab = material_cost_with_markup + fabrication_total
    install_cost = INSTALL_COST_PER_SQFT * sq_ft_used
    total_cost = material_and_fab + install_cost
    ib_total_cost = (unit_cost + FABRICATION_COST_PER_SQFT + ADDITIONAL_IB_RATE) * sq_ft_used
    return {
        "available_sq_ft": record.get("available_sq_ft", 0),
        "material_and_fab": material_and_fab,
        "install_cost": install_cost,
        "total_cost": total_cost,
        "ib_cost": ib_total_cost,
    }

# --- Streamlit UI Begins Here ---
st.title("Countertop Cost Estimator")
st.write("Get an accurate estimate for your custom countertop project.")

# This will be modified once you provide the old code for the branch selector
# For now, it uses direct sheet names.
sheet_tab_names_for_selection = ["InventoryData", "Vernon data", "Edmonton", "Saskatoon", "Abbotsford"] 
selected_sheet_name = st.selectbox("Select Data Source (Sheet Tab Name)", sheet_tab_names_for_selection)

with st.spinner(f"Loading inventory data for {selected_sheet_name}..."):
    df_inventory = load_data_from_google_sheet(selected_sheet_name) 

if df_inventory is None or df_inventory.empty:
    st.warning(f"Could not load or found no usable inventory data for '{selected_sheet_name}'. Please check error messages or ensure the sheet has valid data.")
    st.stop()

st.write(f"**Total slabs loaded from {selected_sheet_name}:** {len(df_inventory)}")

if "Thickness" in df_inventory.columns:
    df_inventory["Thickness"] = df_inventory["Thickness"].astype(str).str.strip().str.lower()
    thickness_options = sorted(list(df_inventory["Thickness"].unique())) 
    if not thickness_options: thickness_options = ["1.2cm", "2cm", "3cm"] 
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

# This logic will likely be driven by the new "Branch Selector" you want to add back
branch_to_material_sources = {
    "Vernon data": ["Vernon", "Abbotsford"], "Victoria": ["Vernon", "Abbotsford"],
    "Vancouver": ["Vernon", "Abbotsford"], "Calgary": ["Edmonton", "Saskatoon"],
    "Edmonton": ["Edmonton", "Saskatoon"], "Saskatoon": ["Edmonton", "Saskatoon"],
    "Winnipeg": ["Edmonton", "Saskatoon"], "Abbotsford": ["Abbotsford"],
    "InventoryData": ["Vernon", "Abbotsford", "Edmonton", "Saskatoon"] 
}

if "Location" in df_inventory.columns:
    # This key for branch_to_material_sources will need to align with your new branch selector
    key_for_material_source = selected_sheet_name # Placeholder - will change with branch selector
    if key_for_material_source in branch_to_material_sources:
      allowed_material_locations = branch_to_material_sources.get(key_for_material_source, [])
      if allowed_material_locations:
          df_inventory = df_inventory[df_inventory["Location"].isin(allowed_material_locations)]
else:
    st.info("Column 'Location' missing. Cannot filter by material source.")

if df_inventory.empty: 
    st.warning("No slabs available after applying location filters.")
    st.stop()

# This function will also likely be driven by the new "Branch Selector"
def get_fabrication_plant(key_for_fab_plant): 
    branch_concept = key_for_fab_plant 
    if key_for_fab_plant == "Vernon data": branch_concept = "Vernon" # Example mapping
    # Add other mappings if sheet names differ from conceptual branch names

    if branch_concept in ["Vernon", "Victoria", "Vancouver", "Abbotsford"]: return "Abbotsford"
    if branch_concept in ["Calgary", "Edmonton", "Saskatoon", "Winnipeg"]: return "Saskatoon"
    if key_for_fab_plant == "InventoryData" : return "Multiple (check material location)" 
    return "Unknown"

fabrication_plant = get_fabrication_plant(selected_sheet_name) # Placeholder - will change
st.markdown(f"**Assumed Fabrication Plant for '{selected_sheet_name}' source:** {fabrication_plant}")


if not ("Serialized On Hand Cost" in df_inventory.columns and \
      "Available Sq Ft" in df_inventory.columns):
    st.error("Critical columns 'Serialized On Hand Cost' or 'Available Sq Ft' are missing before unit cost calculation. Cannot proceed.")
    st.stop()

df_inventory = df_inventory[df_inventory['Available Sq Ft'].notna()] 
df_inventory = df_inventory[df_inventory['Available Sq Ft'] > 0] 
if df_inventory.empty:
    st.error("All inventory items have zero or invalid 'Available Sq Ft' after filtering. Cannot calculate unit cost.")
    st.stop()
df_inventory["unit_cost"] = df_inventory["Serialized On Hand Cost"] / df_inventory["Available Sq Ft"]


sq_ft_input = st.number_input("Enter Square Footage Needed", min_value=1, value=40, step=1)
sq_ft_used = max(sq_ft_input, MINIMUM_SQ_FT)
if sq_ft_input < MINIMUM_SQ_FT:
    st.info(f"Minimum is {MINIMUM_SQ_FT} sq ft. Using {MINIMUM_SQ_FT} sq ft for pricing.")

df_agg = (df_inventory.groupby(["Full Name", "Location"]) 
          .agg(available_sq_ft=("Available Sq Ft", "sum"),
               unit_cost=("unit_cost", "mean"), 
               slab_count=("Serial Number", "nunique"), 
               serial_numbers=("Serial Number", lambda x: ", ".join(sorted(list(x.astype(str).unique()))))) 
          .reset_index())

required_material = sq_ft_used * 1.1
df_agg = df_agg[df_agg["available_sq_ft"] >= required_material]
if df_agg.empty:
    st.error("No colors have enough material (including 10% buffer).")
    st.stop()

df_agg["final_price"] = df_agg.apply(lambda row: calculate_aggregated_costs(row, sq_ft_used)["total_cost"] * (1 + GST_RATE), axis=1)
df_valid = df_agg[df_agg["final_price"] > 0]

if df_valid.empty:
    st.error("No valid slab prices available after calculations.")
    st.stop()

min_possible_cost = int(df_valid["final_price"].min()) if not df_valid.empty else 0
max_possible_cost = int(df_valid["final_price"].max()) if not df_valid.empty else 10000 
if min_possible_cost >= max_possible_cost : max_possible_cost = min_possible_cost + 100 

max_job_cost = st.slider("Select Maximum Job Cost ($)", min_value=min_possible_cost, max_value=max_possible_cost, value=max_possible_cost, step=100)
df_agg_filtered = df_agg[df_agg["final_price"] <= max_job_cost]

if df_agg_filtered.empty:
    st.error("No colors available within the selected cost range.")
    st.stop()

records = df_agg_filtered.to_dict("records")
if not records: 
    st.error("No material records available to select after all filters.")
    st.stop()

selected_record = st.selectbox("Select Material/Color", options=records,
                               format_func=lambda rec: f"{rec.get('Full Name', 'N/A')} ({rec.get('Location', 'N/A')}) - (${rec.get('final_price', 0) / sq_ft_used:.2f}/sq ft)")

if selected_record: 
    st.markdown(f"**Material:** {selected_record.get('Full Name', 'N/A')}")
    st.markdown(f"**Source Location:** {selected_record.get('Location', 'N/A')}")
    st.markdown(f"**Total Available Sq Ft (This Color/Location):** {selected_record.get('available_sq_ft', 0):.0f} sq.ft")
    st.markdown(f"**Number of Unique Slabs (This Color/Location):** {selected_record.get('slab_count', 0)}")
    
    search_term = selected_record.get('Full Name', '')
    if search_term:
        search_url = f"https://www.google.com/search?q={search_term.replace(' ', '+')}+countertop"
        st.markdown(f"[🔎 Google Image Search for {search_term}]({search_url})")

    edge_profiles = ["Crescent", "Basin", "Boulder", "Volcanic", "Piedmont", "Summit", "Seacliff", "Alpine", "Treeline"]
    default_edge_index = edge_profiles.index("Seacliff") if "Seacliff" in edge_profiles else 0
    selected_edge_profile = st.selectbox("Select Edge Profile", options=edge_profiles, index=default_edge_index)

    costs = calculate_aggregated_costs(selected_record, sq_ft_used)
    sub_total = costs["total_cost"]
    gst_amount = sub_total * GST_RATE
    final_price_marked_up = (sub_total + gst_amount) * (1 + FINAL_MARKUP_PERCENTAGE)

    with st.expander("View Subtotal & GST"):
        st.markdown(f"**Subtotal (before tax & final markup):** ${sub_total:,.2f}")
        st.markdown(f"**GST ({GST_RATE*100:.0f}%):** ${gst_amount:,.2f}")

    st.markdown(f"### Your Total Estimated Price: :green[${final_price_marked_up:,.2f}]")

    if selected_record.get('slab_count', 0) > 1:
        st.info("Note: Multiple slabs contribute to this material option; color/pattern consistency may vary for natural stone.")

    # --- RE-ADD DETAILED BREAKDOWN EXPANDER (NO PASSWORD FOR NOW) ---
    with st.expander("View Detailed Breakdown"):
        st.markdown(f"- **Slab Selected:** {selected_record.get('Full Name', 'N/A')}")
        st.markdown(f"- **Material Source Location:** {selected_record.get('Location', 'N/A')}")
        st.markdown(f"- **Fabrication Plant (for this source):** {fabrication_plant}") # This will update with branch logic
        st.markdown(f"- **Edge Profile Selected:** {selected_edge_profile}")
        st.markdown(f"- **Thickness Selected:** {selected_thickness}") 
        st.markdown(f"- **Square Footage (for pricing):** {sq_ft_used}")
        st.markdown(f"- **Slab Sq Ft (Aggregated for this Color/Location):** {selected_record.get('available_sq_ft', 0):.2f} sq.ft")
        st.markdown(f"- **Number of Unique Slabs (This Color/Location):** {selected_record.get('slab_count', 0)}")
        st.markdown(f"- **Contributing Serial Numbers:** {selected_record.get('serial_numbers', 'N/A')}")
        st.markdown("--- Cost Components (before final markup & GST) ---")
        st.markdown(f"- **Material & Fabrication Cost Component:** ${costs.get('material_and_fab', 0):,.2f}")
        st.markdown(f"- **Installation Cost Component:** ${costs.get('install_cost', 0):,.2f}")
        st.markdown(f"- **IB Cost Component (Industry Base):** ${costs.get('ib_cost', 0):,.2f}") 
        st.markdown("--- Totals ---")
        st.markdown(f"- **Subtotal (Material, Fab, Install - before tax & final markup):** ${sub_total:,.2f}")
        st.markdown(f"- **GST ({GST_RATE*100:.0f}% on subtotal):** ${gst_amount:,.2f}")
        st.markdown(f"- **Total Including GST (before final markup):** ${(sub_total + gst_amount):,.2f}")
        st.markdown(f"- **Final Marked-up Price (including GST):** ${final_price_marked_up:,.2f}")
        st.markdown(f"Calculation: ((Subtotal + GST) * (1 + {FINAL_MARKUP_PERCENTAGE*100:.0f}% Markup))")

else:
    st.info("Please make a material selection to see price details and breakdown.")

st.markdown("---")
st.caption(f"Countertop Estimator. Data for '{selected_sheet_name}'. Current Time (Server): {pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d %H:%M:%S %Z')}")
