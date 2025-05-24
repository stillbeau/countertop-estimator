import streamlit as st
import pandas as pd
import gspread # Used for Google Sheets API interaction
from google.oauth2.service_account import Credentials # Though not directly used if service_account_from_dict works
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
# Updated SPREADSHEET_ID from your screenshot
SPREADSHEET_ID = "1i6Gg-39R1YJSGTJIJlJWuGRfE-ReH97_F_EcMiLPa1Q"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly'] # Read-only access to sheets

# --- Fully Instrumented Function to load data from a specific Google Sheet tab ---
@st.cache_data(show_spinner=False)
def load_data_from_google_sheet(sheet_name_to_load): # Renamed parameter for clarity within function
    st.info("--- Starting data load process ---")
    st.info(f"Attempting to load data for sheet/tab: '{sheet_name_to_load}'")

    st.info("1. Attempting to load credentials from secrets...")
    creds_dict = None # Initialize to avoid reference before assignment if first try fails
    try:
        creds_json_str = st.secrets["gcp_service_account"]
        creds_dict = json.loads(creds_json_str)
        st.success("✅ 1. Successfully loaded and parsed credentials from secrets.")
        # st.json(creds_dict) # Optional: display secrets for debugging (ensure private_key is not fully shown in public screenshots)
    except KeyError:
        st.error("❌ 1. Secret 'gcp_service_account' not found in Streamlit Cloud secrets!")
        return None
    except json.JSONDecodeError as jde:
        st.error(f"❌ 1. Failed to parse JSON from 'gcp_service_account' secret: {jde}. Check its format.")
        return None
    except Exception as e:
        st.error(f"❌ 1. Unexpected error loading secrets: {e} (Type: {type(e)})")
        return None

    st.info(f"2. Attempting to authorize gspread using client_email: {creds_dict.get('client_email')}")
    gc = None # Initialize to avoid reference before assignment
    try:
        gc = gspread.service_account_from_dict(creds_dict, scopes=SCOPES)
        st.success(f"✅ 2. gspread client initialized. Type: {type(gc)}")
    except Exception as e:
        st.error(f"❌ 2. Failed to initialize gspread client (gc = gspread.service_account_from_dict(...)): {e} (Type: {type(e)})")
        return None

    if gc is None:
        st.error("❌ 2a. 'gc' object is None after initialization attempt. Cannot proceed.")
        return None

    st.info("3. Checking 'gc' object for 'open_by_id' attribute...")
    # --- Debugging: Check if open_by_id attribute exists ---
    if not hasattr(gc, 'open_by_id'):
        st.error(f"❌ 3. CRITICAL: 'gc' object (type: {type(gc)}) DOES NOT HAVE attribute 'open_by_id'.")
        st.warning("This strongly suggests an issue with the gspread library version/installation in Streamlit Cloud, even if requirements.txt seems correct.")
        st.subheader("Inspecting the 'gc' object:")
        st.write(f"Is 'gc' None? {gc is None}")
        st.write("Methods and attributes available on 'gc':")
        try:
            attributes = dir(gc)
            if len(attributes) < 100:
                st.code('\n'.join(attributes))
            else:
                st.code('\n'.join(attributes[:50]))
                st.write(f"... ({len(attributes) - 100} more) ...")
                st.code('\n'.join(attributes[-50:]))
            if 'open_by_id' in attributes:
                st.success("Further check via dir(): 'open_by_id' IS in the list of attributes! (This contradicts hasattr, which is strange)")
            else:
                st.error("Further check via dir(): 'open_by_id' IS NOT in the list of attributes!")
        except Exception as e_dir:
            st.error(f"Could not get dir(gc): {e_dir}")
        return None
    else:
        st.success("✅ 3. SUCCESS: 'gc' object HAS attribute 'open_by_id'.")
    # --- End Debugging ---

    st.info(f"4. Attempting to open spreadsheet by ID: '{SPREADSHEET_ID}'")
    spreadsheet = None # Initialize
    try:
        spreadsheet = gc.open_by_id(SPREADSHEET_ID)
        st.success(f"✅ 4. Successfully opened spreadsheet: '{spreadsheet.title}'")
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ 4. Spreadsheet with ID '{SPREADSHEET_ID}' not found. Check SPREADSHEET_ID and sharing permissions with service account: {creds_dict.get('client_email')}")
        return None
    except gspread.exceptions.APIError as apie:
        st.error(f"❌ 4. Google Sheets API Error when opening spreadsheet: {apie}")
        st.error("Ensure SPREADSHEET_ID is correct, service account has 'Viewer' permission on the Sheet, and Google Sheets API is enabled in your Google Cloud Project.")
        return None
    except Exception as e:
        st.error(f"❌ 4. Unexpected error opening spreadsheet: {e} (Type: {type(e)})")
        return None

    if spreadsheet is None:
        st.error("❌ 4a. Spreadsheet object is None after attempting to open. Cannot proceed.")
        return None

    st.info(f"5. Attempting to open worksheet: '{sheet_name_to_load}' from spreadsheet '{spreadsheet.title}'")
    worksheet = None # Initialize
    try:
        worksheet = spreadsheet.worksheet(sheet_name_to_load)
        st.success(f"✅ 5. Successfully opened worksheet: '{worksheet.title}'")
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"❌ 5. Worksheet '{sheet_name_to_load}' not found in spreadsheet '{spreadsheet.title}'. Check tab name (it's case-sensitive).")
        return None
    except Exception as e:
        st.error(f"❌ 5. Unexpected error opening worksheet: {e} (Type: {type(e)})")
        return None

    if worksheet is None:
        st.error("❌ 5a. Worksheet object is None after attempting to open. Cannot proceed.")
        return None
        
    st.info(f"6. Attempting to get all records from worksheet '{worksheet.title}'...")
    df = None # Initialize
    try:
        df = pd.DataFrame(worksheet.get_all_records())
        st.success(f"✅ 6. Successfully fetched {len(df)} records.")
    except Exception as e:
        st.error(f"❌ 6. Error getting records from worksheet or creating DataFrame: {e} (Type: {type(e)})")
        return None # Or return pd.DataFrame() depending on how you handle it later

    if df is None or df.empty:
        st.warning("⚠️ 6a. DataFrame is empty or None after fetching records.")
        # Depending on whether an empty sheet is an error or not, you might return df or None/empty df
        # For now, if it's empty, let's return an empty DataFrame to avoid downstream errors if a DF is expected
        return pd.DataFrame()

    st.info("7. Processing DataFrame (cleaning columns, types)...")
    try:
        df.columns = df.columns.str.strip()
        if "Serialized On Hand Cost" not in df.columns or "Available Sq Ft" not in df.columns:
            st.error(f"❌ 7. Critical columns ('Serialized On Hand Cost' or 'Available Sq Ft') missing in sheet '{sheet_name_to_load}' after fetching. Columns found: {list(df.columns)}")
            return pd.DataFrame() 
        df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].astype(str).str.replace("[\\$, ]", "", regex=True).astype(float)
        df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors="coerce")

        if "Serial Number" in df.columns:
            df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors="coerce").fillna(0).astype(int)
        else:
            st.info(f"ℹ️ 7. Column 'Serial Number' not found in '{sheet_name_to_load}'. Defaulting to 0. This may affect slab counting.")
            df["Serial Number"] = 0 

        df.dropna(subset=['Available Sq Ft'], inplace=True) 
        df = df[df['Available Sq Ft'] > 0] 
        st.success("✅ 7. DataFrame processing complete.")
        return df
    except Exception as e:
        st.error(f"❌ 7. Error processing DataFrame: {e} (Type: {type(e)})")
        return pd.DataFrame() # Return empty DF on processing error

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
        "available_sq_ft": record.get("available_sq_ft", 0), # Use .get for safety
        "material_and_fab": material_and_fab,
        "install_cost": install_cost,
        "total_cost": total_cost,
        "ib_cost": ib_total_cost,
    }

# --- Streamlit UI Begins Here ---
st.title("Countertop Cost Estimator")
st.write("Get an accurate estimate for your custom countertop project.")

# IMPORTANT: These names MUST exactly match the tab names in your Google Sheet for data loading!
# Based on your screenshot, "Vernon data" is a tab, not "Vernon". Adjust as needed.
branch_locations = ["InventoryData", "Vernon data", "Edmonton", "Saskatoon", "Abbotsford"] # Adjusted "Vernon"
# Or, if you want the UI to show "Vernon" but load "Vernon data":
# branch_display_names = ["Vernon", "Victoria", "Vancouver", "Calgary", "Edmonton", "Saskatoon", "Winnipeg", "Abbotsford", "All Inventory"]
# branch_sheet_map = {
#     "Vernon": "Vernon data",
#     "Victoria": "Victoria", # Assuming a tab named "Victoria"
#     "All Inventory": "InventoryData",
#     # ... map other display names to actual sheet tab names
# }
# selected_branch_display = st.selectbox("Select Your Branch Location", branch_display_names)
# sheet_to_load = branch_sheet_map.get(selected_branch_display, "InventoryData") # Default to InventoryData

selected_sheet_name = st.selectbox("Select Data Source (Sheet Tab Name)", branch_locations)


with st.spinner(f"Loading inventory data for {selected_sheet_name}..."):
    # Pass the exact sheet name to the loading function
    df_inventory = load_data_from_google_sheet(selected_sheet_name) 

if df_inventory is None or df_inventory.empty:
    st.warning(f"Could not load or found no usable inventory data for '{selected_sheet_name}'. Review messages above.")
    st.stop()

st.write(f"**Total slabs loaded from {selected_sheet_name}:** {len(df_inventory)}")

if "Thickness" in df_inventory.columns:
    df_inventory["Thickness"] = df_inventory["Thickness"].astype(str).str.strip().str.lower()
    thickness_options = sorted(df_inventory["Thickness"].unique().tolist())
    if not thickness_options: thickness_options = ["1.2cm", "2cm", "3cm"] # Fallback
    # Try to find '3cm' or default to first available
    default_thickness_index = thickness_options.index("3cm") if "3cm" in thickness_options else 0
    selected_thickness = st.selectbox("Select Thickness", options=thickness_options, index=default_thickness_index)
    df_inventory = df_inventory[df_inventory["Thickness"] == selected_thickness.lower()]
else:
    st.info("Column 'Thickness' not found. Skipping thickness filter.")

if df_inventory.empty: # Check after thickness filter
    st.warning("No slabs match selected thickness after filtering.")
    st.stop()

if "Brand" in df_inventory.columns and "Color" in df_inventory.columns:
    df_inventory["Full Name"] = df_inventory["Brand"].astype(str) + " - " + df_inventory["Color"].astype(str)
else:
    st.error("Required 'Brand' or 'Color' columns missing from loaded data. Cannot proceed.")
    st.stop()

# Note: The branch_to_material_sources and get_fabrication_plant logic
# used 'selected_branch' which was tied to a display name.
# Now we are directly using 'selected_sheet_name'. You might need to adjust
# how 'fabrication_plant' or 'material_sources' are determined if 'selected_sheet_name'
# doesn't directly map to a sales branch concept (e.g. if it's "InventoryData").
# For simplicity, I'll assume selected_sheet_name can be used for this logic.

branch_to_material_sources = {
    "Vernon data": ["Vernon", "Abbotsford"], "Victoria": ["Vernon", "Abbotsford"], # Assuming "Vernon data" is the Vernon branch
    "Vancouver": ["Vernon", "Abbotsford"], "Calgary": ["Edmonton", "Saskatoon"],
    "Edmonton": ["Edmonton", "Saskatoon"], "Saskatoon": ["Edmonton", "Saskatoon"],
    "Winnipeg": ["Edmonton", "Saskatoon"], "Abbotsford": ["Abbotsford"],
    "InventoryData": ["Vernon", "Abbotsford", "Edmonton", "Saskatoon"] # Example: InventoryData can source from all
}

if "Location" in df_inventory.columns:
    # Use selected_sheet_name (or a mapped branch name if you implement that)
    # For now, let's assume selected_sheet_name can be a key in branch_to_material_sources
    # or you have a default.
    # This logic might need refinement based on how 'selected_sheet_name' relates to your branches.
    
    # Simple approach: if selected_sheet_name is a branch, use it. Otherwise, don't filter by source.
    if selected_sheet_name in branch_to_material_sources:
      allowed_material_locations = branch_to_material_sources.get(selected_sheet_name, [])
      if allowed_material_locations:
          df_inventory = df_inventory[df_inventory["Location"].isin(allowed_material_locations)]
      # else:
          # st.info(f"No specific material sources defined for '{selected_sheet_name}'. Showing all materials from this sheet.")
    # else if selected_sheet_name == "InventoryData":
        # Potentially no location filtering if it's the master sheet, or apply broad rules.
        # For now, this means if "InventoryData" is not in branch_to_material_sources, it won't be filtered.
        # You might want to add "InventoryData": ["Vernon", "Abbotsford", "Edmonton", "Saskatoon"] to the dict.

else:
    st.info("Column 'Location' missing. Cannot filter by material source.")

if df_inventory.empty: # Check after location filter
    st.warning("No slabs available after applying location filters.")
    st.stop()

def get_fabrication_plant(sheet_or_branch_name): # Parameter changed
    # This logic needs to map from the sheet name to a branch concept if they differ
    # Example: if sheet_or_branch_name is "Vernon data", it maps to "Vernon" branch concept
    branch_concept = sheet_or_branch_name 
    if sheet_or_branch_name == "Vernon data": branch_concept = "Vernon"
    # Add other mappings if sheet names differ from conceptual branch names

    if branch_concept in ["Vernon", "Victoria", "Vancouver", "Abbotsford"]: return "Abbotsford"
    if branch_concept in ["Calgary", "Edmonton", "Saskatoon", "Winnipeg"]: return "Saskatoon"
    if sheet_or_branch_name == "InventoryData" : return "Multiple (check material location)" # Or a default
    return "Unknown"

fabrication_plant = get_fabrication_plant(selected_sheet_name)
st.markdown(f"**Assumed Fabrication Plant for '{selected_sheet_name}' source:** {fabrication_plant}")

if not ("Serialized On Hand Cost" in df_inventory.columns and "Available Sq Ft" in df_inventory.columns and not df_inventory[df_inventory['Available Sq Ft'] == 0].empty):
    if df_inventory.empty or 'Available Sq Ft' not in df_inventory.columns or df_inventory['Available Sq Ft'].isnull().all() or (df_inventory['Available Sq Ft'] == 0).all():
        st.error("No inventory with available square footage to calculate unit cost after filters. Cannot proceed.")
        st.stop()
df_inventory["unit_cost"] = df_inventory["Serialized On Hand Cost"] / df_inventory["Available Sq Ft"]


sq_ft_input = st.number_input("Enter Square Footage Needed", min_value=1, value=40, step=1)
sq_ft_used = max(sq_ft_input, MINIMUM_SQ_FT)
if sq_ft_input < MINIMUM_SQ_FT:
    st.info(f"Minimum is {MINIMUM_SQ_FT} sq ft. Using {MINIMUM_SQ_FT} sq ft for pricing.")

df_agg = (df_inventory.groupby(["Full Name", "Location"]) # Location here is material's physical location
          .agg(available_sq_ft=("Available Sq Ft", "sum"),
               unit_cost=("unit_cost", "mean"), # Using mean, max could also be an option
               slab_count=("Serial Number", "nunique"), 
               serial_numbers=("Serial Number", lambda x: ", ".join(sorted(x.astype(str).unique()))))
          .reset_index())

required_material = sq_ft_used * 1.1
df_agg = df_agg[df_agg["available_sq_ft"] >= required_material]
if df_agg.empty:
    st.error("No colors have enough material (including 10% buffer).")
    st.stop()

df_agg["final_price"] = df_agg.apply(lambda row: calculate_aggregated_costs(row, sq_ft_used)["total_cost"] * (1 + GST_RATE), axis=1)
df_valid = df_agg[df_agg["final_price"] > 0]

if df_valid.empty:
    st.error("No valid slab prices available after calculations (e.g., zero cost or no inventory passed filters).")
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
selected_record = st.selectbox("Select Material/Color", options=records,
                               format_func=lambda rec: f"{rec.get('Full Name', 'N/A')} ({rec.get('Location', 'N/A')}) - (${rec.get('final_price', 0) / sq_ft_used:.2f}/sq ft)")

if selected_record: # Check if a record is selected
    st.markdown(f"**Material:** {selected_record.get('Full Name', 'N/A')}")
    st.markdown(f"**Source Location:** {selected_record.get('Location', 'N/A')}")
    st.markdown(f"**Total Available Sq Ft (This Color/Location):** {selected_record.get('available_sq_ft', 0):.0f} sq.ft")
    st.markdown(f"**Number of Unique Slabs (This Color/Location):** {selected_record.get('slab_count', 0)}")
    
    search_term = selected_record.get('Full Name', '')
    if search_term:
        search_url = f"https://www.google.com/search?q={search_term.replace(' ', '+')}+countertop"
        st.markdown(f"[🔎 Google Image Search for {search_term}]({search_url})")

    edge_profiles = ["Crescent", "Basin", "Boulder", "Volcanic", "Piedmont", "Summit", "Seacliff", "Alpine", "Treeline"]
    # Ensure Seacliff is in list or handle gracefully
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
else:
    st.info("Please make a material selection to see price details.")

st.markdown("---")
st.caption(f"Countertop Estimator. Data for '{selected_sheet_name}'. Current Time (Server): {pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d %H:%M:%S %Z')}")
