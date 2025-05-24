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
ADDITIONAL_IB_RATE = 0
GST_RATE = 0.05
FINAL_MARKUP_PERCENTAGE = 0.25

# --- Google Sheets API Configuration ---
# UPDATED SPREADSHEET_ID from the URL you just provided
SPREADSHEET_ID = "166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# --- Instrumented Function to load data (modified to use open_by_key) ---
@st.cache_data(show_spinner=False)
def load_data_from_google_sheet(sheet_name_to_load):
    st.info("--- Starting data load process ---")
    st.info(f"Attempting to load data for sheet/tab: '{sheet_name_to_load}'")

    st.info("1. Attempting to load credentials from secrets...")
    creds_dict = None
    try:
        creds_json_str = st.secrets["gcp_service_account"]
        creds_dict = json.loads(creds_json_str)
        st.success("✅ 1. Successfully loaded and parsed credentials from secrets.")
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
    gc = None
    try:
        gc = gspread.service_account_from_dict(creds_dict, scopes=SCOPES)
        st.success(f"✅ 2. gspread client initialized. Type: {type(gc)}")
    except Exception as e:
        st.error(f"❌ 2. Failed to initialize gspread client: {e} (Type: {type(e)})")
        return None

    if gc is None:
        st.error("❌ 2a. 'gc' object is None after initialization. Cannot proceed.")
        return None

    st.info("3. Verifying gspread client and available methods...")
    # --- Debugging: Check available methods ---
    gc_attributes = []
    try:
        gc_attributes = dir(gc)
    except Exception:
        pass # Ignore if dir fails for some reason on a problematic object

    if 'open_by_key' in gc_attributes:
        st.success("✅ 3. 'open_by_key' method IS AVAILABLE on 'gc' object. Proceeding with this method.")
        open_method = gc.open_by_key
    elif 'open_by_id' in gc_attributes: # Fallback to open_by_id if it magically appears
        st.warning("⚠️ 3. 'open_by_key' preferred but not found; 'open_by_id' IS AVAILABLE. Using 'open_by_id'.")
        open_method = gc.open_by_id
    else:
        st.error(f"❌ 3. CRITICAL: Neither 'open_by_key' nor 'open_by_id' found on 'gc' object (type: {type(gc)}).")
        st.subheader("Inspecting the 'gc' object:")
        st.write(f"Is 'gc' None? {gc is None}")
        st.write("Methods and attributes available on 'gc' (from dir(gc)):")
        if gc_attributes:
            st.code('\n'.join(gc_attributes[:50])) # Show first 50
            if len(gc_attributes) > 50: st.write(f"... and {len(gc_attributes) - 50} more.")
        else:
            st.write("Could not retrieve attributes using dir(gc).")
        return None
    # --- End Debugging ---

    st.info(f"4. Attempting to open spreadsheet by ID/Key: '{SPREADSHEET_ID}' using the determined open method.")
    spreadsheet = None
    try:
        spreadsheet = open_method(SPREADSHEET_ID) # Use the determined open_method
        st.success(f"✅ 4. Successfully opened spreadsheet: '{spreadsheet.title}'")
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ 4. Spreadsheet with ID '{SPREADSHEET_ID}' not found. Check SPREADSHEET_ID and sharing permissions with: {creds_dict.get('client_email')}")
        return None
    except gspread.exceptions.APIError as apie:
        st.error(f"❌ 4. Google Sheets API Error opening spreadsheet: {apie}")
        st.error("Ensure SPREADSHEET_ID is correct, service account has 'Viewer' permission, and Sheets API is enabled.")
        return None
    except Exception as e:
        st.error(f"❌ 4. Unexpected error opening spreadsheet: {e} (Type: {type(e)})")
        return None

    if spreadsheet is None:
        st.error("❌ 4a. Spreadsheet object is None. Cannot proceed.")
        return None

    st.info(f"5. Attempting to open worksheet: '{sheet_name_to_load}' from '{spreadsheet.title}'")
    worksheet = None
    try:
        worksheet = spreadsheet.worksheet(sheet_name_to_load)
        st.success(f"✅ 5. Successfully opened worksheet: '{worksheet.title}'")
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"❌ 5. Worksheet '{sheet_name_to_load}' not found in '{spreadsheet.title}'. Check tab name (case-sensitive).")
        return None
    except Exception as e:
        st.error(f"❌ 5. Unexpected error opening worksheet: {e} (Type: {type(e)})")
        return None

    if worksheet is None:
        st.error("❌ 5a. Worksheet object is None. Cannot proceed.")
        return None
        
    st.info(f"6. Attempting to get all records from '{worksheet.title}'...")
    df = None
    try:
        df = pd.DataFrame(worksheet.get_all_records())
        st.success(f"✅ 6. Successfully fetched {len(df)} records.")
    except Exception as e:
        st.error(f"❌ 6. Error getting records/creating DataFrame: {e} (Type: {type(e)})")
        return None

    if df is None or df.empty:
        st.warning("⚠️ 6a. DataFrame is empty or None after fetching records.")
        return pd.DataFrame()

st.info("7. Processing DataFrame...")
try:
    df.columns = df.columns.str.strip()
    if "Serialized On Hand Cost" not in df.columns or "Available Sq Ft" not in df.columns:
        st.error(f"❌ 7. Critical columns ('Serialized On Hand Cost' or 'Available Sq Ft') missing in sheet '{sheet_name_to_load}' after fetching. Columns found: {list(df.columns)}")
        return pd.DataFrame()

    # Clean and convert "Serialized On Hand Cost"
    # First, remove currency symbols and commas, convert to string to ensure .str accessor works
    df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].astype(str).str.replace("[\\$,]", "", regex=True).str.strip()
    # Now convert to numeric, coercing errors (like empty strings) to NaN
    df["Serialized On Hand Cost"] = pd.to_numeric(df["Serialized On Hand Cost"], errors='coerce')

    # Clean and convert "Available Sq Ft"
    df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors='coerce')

    # Handle NaN values created by 'coerce' if necessary (e.g., fill with 0 or drop rows)
    # For now, let's see if subsequent filters handle NaNs, or if we need to explicitly fill/drop.
    # If unit_cost relies on these, NaNs might propagate.
    # Example: df.fillna({'Serialized On Hand Cost': 0, 'Available Sq Ft': 0}, inplace=True)
    # Or, more likely, you'll want to drop rows where these essential values are missing.

    if "Serial Number" in df.columns:
        df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors='coerce').fillna(0).astype(int)
    else:
        st.info(f"ℹ️ 7. Column 'Serial Number' not found in '{sheet_name_to_load}'. Defaulting to 0.")
        df["Serial Number"] = 0

    # Drop rows where essential numeric columns became NaN, or where Available Sq Ft is 0 (or less)
    df.dropna(subset=['Serialized On Hand Cost', 'Available Sq Ft'], inplace=True)
    df = df[df['Available Sq Ft'] > 0] # Also ensures Available Sq Ft is not zero before division for unit_cost

    if df.empty:
        st.warning("⚠️ 7a. DataFrame is empty after cleaning and dropping rows with missing essential data.")
        return pd.DataFrame()

    st.success("✅ 7. DataFrame processing complete.")
    return df
except Exception as e:
    st.error(f"❌ 7. Error processing DataFrame: {e} (Type: {type(e)})")
    return pd.DataFrame()

# --- Cost Calculation Function (remains the same) ---
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

# --- Streamlit UI Begins Here (remains largely the same) ---
st.title("Countertop Cost Estimator")
st.write("Get an accurate estimate for your custom countertop project.")

branch_locations = ["InventoryData", "Vernon data", "Edmonton", "Saskatoon", "Abbotsford"] 
selected_sheet_name = st.selectbox("Select Data Source (Sheet Tab Name)", branch_locations)

with st.spinner(f"Loading inventory data for {selected_sheet_name}..."):
    df_inventory = load_data_from_google_sheet(selected_sheet_name) 

if df_inventory is None or df_inventory.empty:
    st.warning(f"Could not load or found no usable inventory data for '{selected_sheet_name}'. Review messages above for details.")
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

branch_to_material_sources = {
    "Vernon data": ["Vernon", "Abbotsford"], "Victoria": ["Vernon", "Abbotsford"],
    "Vancouver": ["Vernon", "Abbotsford"], "Calgary": ["Edmonton", "Saskatoon"],
    "Edmonton": ["Edmonton", "Saskatoon"], "Saskatoon": ["Edmonton", "Saskatoon"],
    "Winnipeg": ["Edmonton", "Saskatoon"], "Abbotsford": ["Abbotsford"],
    "InventoryData": ["Vernon", "Abbotsford", "Edmonton", "Saskatoon"] 
}

if "Location" in df_inventory.columns:
    if selected_sheet_name in branch_to_material_sources:
      allowed_material_locations = branch_to_material_sources.get(selected_sheet_name, [])
      if allowed_material_locations:
          df_inventory = df_inventory[df_inventory["Location"].isin(allowed_material_locations)]
else:
    st.info("Column 'Location' missing. Cannot filter by material source.")

if df_inventory.empty: 
    st.warning("No slabs available after applying location filters.")
    st.stop()

def get_fabrication_plant(sheet_or_branch_name): 
    branch_concept = sheet_or_branch_name 
    if sheet_or_branch_name == "Vernon data": branch_concept = "Vernon"
    if branch_concept in ["Vernon", "Victoria", "Vancouver", "Abbotsford"]: return "Abbotsford"
    if branch_concept in ["Calgary", "Edmonton", "Saskatoon", "Winnipeg"]: return "Saskatoon"
    if sheet_or_branch_name == "InventoryData" : return "Multiple (check material location)" 
    return "Unknown"

fabrication_plant = get_fabrication_plant(selected_sheet_name)
st.markdown(f"**Assumed Fabrication Plant for '{selected_sheet_name}' source:** {fabrication_plant}")

if not ("Serialized On Hand Cost" in df_inventory.columns and \
      "Available Sq Ft" in df_inventory.columns and \
      not df_inventory[df_inventory['Available Sq Ft'] == 0].empty):
    
    if df_inventory.empty or \
       'Available Sq Ft' not in df_inventory.columns or \
       df_inventory['Available Sq Ft'].isnull().all() or \
       (df_inventory['Available Sq Ft'] == 0).all():
        st.error("No inventory with valid 'Available Sq Ft' to calculate unit cost. Cannot proceed.")
        st.stop()
df_inventory = df_inventory[df_inventory['Available Sq Ft'] != 0]
if df_inventory.empty:
    st.error("All inventory items have zero 'Available Sq Ft' after filtering. Cannot calculate unit cost.")
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
else:
    st.info("Please make a material selection to see price details.")

st.markdown("---")
st.caption(f"Countertop Estimator. Data for '{selected_sheet_name}'. Current Time (Server): {pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d %H:%M:%S %Z')}")
