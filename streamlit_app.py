import streamlit as st
import pandas as pd
import gspread # Used for Google Sheets API interaction
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
# CORRECTED SPREADSHEET_ID based on your provided URL
SPREADSHEET_ID = "166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# Define the names of your Google Sheet tabs
MASTER_INVENTORY_SHEET_TAB_NAME = "InventoryData"
SALESPEOPLE_SHEET_TAB_NAME = "Salespeople" # New constant for the salespeople tab

# --- Function to load data from Google Sheets ---
@st.cache_data(show_spinner=False)
def load_data_from_google_sheet(sheet_name_to_load):
    """
    Loads and processes data from a specified Google Sheet tab.
    Handles authentication, sheet/worksheet opening, and basic data cleaning.
    """
    creds_dict = None
    try:
        creds_json_str = st.secrets["gcp_service_account"]
        creds_dict = json.loads(creds_json_str)
    except KeyError:
        st.error("❌ Critical Error: 'gcp_service_account' secret not found. App cannot access data. Please contact administrator.")
        return pd.DataFrame() # Return empty DataFrame on critical error
    except json.JSONDecodeError as jde:
        st.error(f"❌ Critical Error: Failed to parse Google service account credentials: {jde}. Please contact administrator.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Critical Error: Unexpected issue loading credentials: {e}. Please contact administrator.")
        return pd.DataFrame()

    gc = None
    try:
        gc = gspread.service_account_from_dict(creds_dict, scopes=SCOPES)
    except Exception as e:
        st.error(f"❌ Critical Error: Failed to initialize Google Sheets client: {e}. Please contact administrator.")
        return pd.DataFrame()

    if gc is None:
        st.error("❌ Critical Error: Google Sheets client object is None after initialization. Please contact administrator.")
        return pd.DataFrame()

    open_method = None
    gc_attributes = dir(gc) # Get attributes once
    if 'open_by_key' in gc_attributes:
        open_method = gc.open_by_key
    elif 'open_by_id' in gc_attributes: # Fallback if open_by_key is not found
        open_method = gc.open_by_id
    else:
        st.error(f"❌ Critical Error: Required gspread methods ('open_by_key' or 'open_by_id') not found on client object. App may be misconfigured. Please contact administrator.")
        return pd.DataFrame()

    spreadsheet = None
    try:
        spreadsheet = open_method(SPREADSHEET_ID)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ Error: Spreadsheet not found. Please ensure the data source is correctly set up and shared with: {creds_dict.get('client_email')}")
        return pd.DataFrame()
    except gspread.exceptions.APIError as apie:
        st.error(f"❌ Error: A Google Sheets API error occurred: {apie}. The sheet might be inaccessible or API limits reached.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error: Unexpected issue opening spreadsheet: {e}.")
        return pd.DataFrame()

    if spreadsheet is None: return pd.DataFrame()

    worksheet = None
    try:
        worksheet = spreadsheet.worksheet(sheet_name_to_load)
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"❌ Error: Worksheet tab '{sheet_name_to_load}' not found in the spreadsheet '{spreadsheet.title}'. Please check tab name (it's case-sensitive).")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error: Unexpected issue opening worksheet '{sheet_name_to_load}': {e}.")
        return pd.DataFrame()

    if worksheet is None: return pd.DataFrame()
        
    df = None
    try:
        df = pd.DataFrame(worksheet.get_all_records())
    except Exception as e:
        st.error(f"❌ Error: Could not retrieve records from worksheet '{worksheet.title}': {e}.")
        return pd.DataFrame()

    if df is None or df.empty:
        st.warning(f"⚠️ No data found in worksheet '{worksheet.title}'.")
        return pd.DataFrame()

    try:
        df.columns = df.columns.str.strip()
        
        # --- Conditional column checks and processing based on sheet type ---
        if sheet_name_to_load == MASTER_INVENTORY_SHEET_TAB_NAME:
            required_cols = ["Serialized On Hand Cost", "Available Sq Ft", "Location", "Brand", "Color", "Thickness"]
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                st.error(f"❌ Error: Critical inventory columns missing from '{sheet_name_to_load}': {', '.join(missing_cols)}. Found: {list(df.columns)}")
                return pd.DataFrame()
            
            df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].astype(str).str.replace("[\\$, ]", "", regex=True).str.strip()
            df["Serialized On Hand Cost"] = pd.to_numeric(df["Serialized On Hand Cost"], errors='coerce')
            df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors='coerce')

            if "Serial Number" in df.columns:
                df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors='coerce').fillna(0).astype(int)
            else:
                df["Serial Number"] = 0 

            df.dropna(subset=['Serialized On Hand Cost', 'Available Sq Ft', 'Location', 'Brand', 'Color', 'Thickness'], inplace=True)
            df = df[df['Available Sq Ft'] > 0] 
        
        elif sheet_name_to_load == SALESPEOPLE_SHEET_TAB_NAME:
            required_cols = ["SalespersonName", "Branch", "Email"]
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                st.error(f"❌ Error: Critical salesperson columns missing from '{sheet_name_to_load}': {', '.join(missing_cols)}. Found: {list(df.columns)}")
                return pd.DataFrame()
            
            for col in ["SalespersonName", "Branch", "Email"]:
                df[col] = df[col].astype(str).str.strip()
            df.dropna(subset=["SalespersonName", "Branch", "Email"], inplace=True) # Ensure essential fields are not empty
            
        else: # For any other sheet name not explicitly handled
            st.warning(f"⚠️ Sheet '{sheet_name_to_load}' loaded but no specific processing rules defined for its columns.")
            # You might want to add default dropna for all columns or specific error.

        if df.empty:
            st.warning(f"⚠️ No valid data rows in '{sheet_name_to_load}' after cleaning and filtering.")
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

# --- Load Master Inventory Data AND Salespeople Data---
df_master_inventory = None
df_salespeople = None

with st.spinner(f"Loading all inventory data from '{MASTER_INVENTORY_SHEET_TAB_NAME}'..."):
    df_master_inventory = load_data_from_google_sheet(MASTER_INVENTORY_SHEET_TAB_NAME) 

with st.spinner(f"Loading salespeople data from '{SALESPEOPLE_SHEET_TAB_NAME}'..."):
    df_salespeople = load_data_from_google_sheet(SALESPEOPLE_SHEET_TAB_NAME)

if df_master_inventory is None or df_master_inventory.empty:
    st.error(f"Could not load master inventory data from '{MASTER_INVENTORY_SHEET_TAB_NAME}'. Cannot proceed.")
    st.stop()
# Warning if salespeople data isn't loaded, but don't stop the app
if df_salespeople is None or df_salespeople.empty:
    st.warning(f"⚠️ Could not load salespeople data from '{SALESPEOPLE_SHEET_TAB_NAME}'. Emailing functionality will be unavailable.")
    # Ensure df_salespeople is an empty DataFrame if loading failed, to prevent downstream errors
    df_salespeople = pd.DataFrame() 

st.success(f"Successfully loaded {len(df_master_inventory)} total inventory records.")
if not df_salespeople.empty: # Only show success if data was actually loaded
    st.success(f"Successfully loaded {len(df_salespeople)} salespeople records.")


# --- Branch Selector ---
sales_branch_locations = ["Vernon", "Victoria", "Vancouver", "Calgary", "Edmonton", "Saskatoon", "Winnipeg"] 
selected_branch = st.selectbox("Select Your Branch Location", sales_branch_locations)

# --- Salesperson Selector ---
selected_salesperson_email = None # Initialize to None
selected_salesperson_display = "None" # Initialize display name

if not df_salespeople.empty: # Only show salesperson selector if data was loaded
    # Filter salespeople for the selected branch
    salespeople_in_branch_df = df_salespeople[df_salespeople["Branch"].astype(str).str.lower() == selected_branch.lower()]
    
    if not salespeople_in_branch_df.empty:
        # Create a list of display names for the dropdown
        salesperson_options = salespeople_in_branch_df.apply(lambda x: f"{x['SalespersonName']} ({x['Email']})", axis=1).tolist()
        
        selected_salesperson_display = st.selectbox(
            f"Select Salesperson for {selected_branch} (Optional)", 
            options=["None"] + salesperson_options # Add "None" option at the top
        )
        
        if selected_salesperson_display != "None":
            # Extract the email from the selected display string
            # This assumes the format "Name (email@domain.com)"
            try:
                start_index = selected_salesperson_display.rfind('(') + 1
                end_index = selected_salesperson_display.rfind(')')
                selected_salesperson_email = selected_salesperson_display[start_index:end_index]
            except Exception:
                st.error("Could not parse salesperson email from selection.")
                selected_salesperson_email = None
            
            if selected_salesperson_email:
                st.info(f"Selected salesperson for email: {selected_salesperson_email}") # For testing/confirmation
    else:
        st.caption(f"No salespeople listed for the {selected_branch} branch in the 'Salespeople' sheet.")
else:
    st.caption("Salespeople data not loaded. Emailing functionality unavailable.")


# --- Filter inventory based on selected branch's material sources ---
branch_to_material_sources = {
    "Vernon": ["Vernon", "Abbotsford"], "Victoria": ["Vernon", "Abbotsford"], 
    "Vancouver": ["Vernon", "Abbotsford"], "Calgary": ["Edmonton", "Saskatoon"],  
    "Edmonton": ["Edmonton", "Saskatoon"], "Saskatoon": ["Edmonton", "Saskatoon"],
    "Winnipeg": ["Edmonton", "Saskatoon"], 
}
allowed_locations_for_branch = branch_to_material_sources.get(selected_branch, [])
if not allowed_locations_for_branch:
    st.warning(f"No material source locations defined for branch '{selected_branch}'. Showing all available inventory.")
    df_inventory = df_master_inventory.copy() 
else:
    if "Location" in df_master_inventory.columns:
        df_inventory = df_master_inventory[df_master_inventory["Location"].isin(allowed_locations_for_branch)]
    else:
        st.error("Master inventory sheet is missing the 'Location' column. Cannot filter by branch.")
        df_inventory = pd.DataFrame() 

if df_inventory.empty: 
    st.warning(f"No inventory available from allowed material locations for branch '{selected_branch}'. Please adjust branch or filters.")
    st.stop()
st.write(f"**Inventory records available for {selected_branch} (after location filter):** {len(df_inventory)}")

# --- Determine Fabrication Plant ---
def get_fabrication_plant(branch): 
    if branch in ["Vernon", "Victoria", "Vancouver"]: 
        return "Abbotsford"
    elif branch in ["Calgary", "Edmonton", "Saskatoon", "Winnipeg"]:
        return "Saskatoon"
    else:
        return "Unknown"
fabrication_plant = get_fabrication_plant(selected_branch)
st.markdown(f"**Orders for {selected_branch} will be fabricated at:** {fabrication_plant}")

# --- Thickness Selector (Applied to filtered df_inventory) ---
if "Thickness" in df_inventory.columns:
    df_inventory["Thickness"] = df_inventory["Thickness"].astype(str).str.strip().str.lower()
    thickness_options = sorted(list(df_inventory["Thickness"].unique())) 
    if not thickness_options: thickness_options = ["1.2cm", "2cm", "3cm"] 
    default_thickness_index = thickness_options.index("3cm") if "3cm" in thickness_options else 0
    if not thickness_options: 
        st.warning("No thickness options available for the selected branch and material locations.")
        st.stop()
    selected_thickness = st.selectbox("Select Thickness", options=thickness_options, index=default_thickness_index)
    df_inventory = df_inventory[df_inventory["Thickness"] == selected_thickness.lower()]
else:
    st.error("Critical column 'Thickness' not found in the data. Cannot proceed.") 
    st.stop()

if df_inventory.empty: 
    st.warning(f"No slabs match selected thickness '{selected_thickness}' for branch '{selected_branch}'. Please adjust filters.")
    st.stop()

# --- Create Full Name field (Applied to further filtered df_inventory) ---
if "Brand" in df_inventory.columns and "Color" in df_inventory.columns:
    df_inventory["Full Name"] = df_inventory["Brand"].astype(str) + " - " + df_inventory["Color"].astype(str)
else:
    st.error("Required 'Brand' or 'Color' columns missing after filtering. Cannot proceed.")
    st.stop()

# --- Compute Unit Cost (Applied to final filtered df_inventory) ---
if df_inventory.empty or not ("Serialized On Hand Cost" in df_inventory.columns and "Available Sq Ft" in df_inventory.columns):
    st.error("Cannot calculate unit costs due to missing data or empty inventory after filters.")
    st.stop()
df_inventory = df_inventory[df_inventory['Available Sq Ft'].notna()] 
df_inventory = df_inventory[df_inventory['Available Sq Ft'] > 0] 
if df_inventory.empty:
    st.error("All inventory items have zero or invalid 'Available Sq Ft' after filtering. Cannot calculate unit cost.")
    st.stop()
df_inventory["unit_cost"] = df_inventory["Serialized On Hand Cost"] / df_inventory["Available Sq Ft"]


# --- UI from here down uses the filtered df_inventory ---
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
    st.error("No colors have enough material (including 10% buffer) for the selected branch and filters.")
    st.stop()

df_agg["final_price_calculated"] = df_agg.apply(lambda row: calculate_aggregated_costs(row, sq_ft_used)["total_cost"] * (1 + GST_RATE), axis=1)
df_valid = df_agg[df_agg["final_price_calculated"] > 0] 

if df_valid.empty:
    st.error("No valid slab prices available after calculations.")
    st.stop()

min_possible_cost = int(df_valid["final_price_calculated"].min()) if not df_valid.empty else 0
max_possible_cost = int(df_valid["final_price_calculated"].max()) if not df_valid.empty else 10000 
if min_possible_cost >= max_possible_cost : max_possible_cost = min_possible_cost + 100 

max_job_cost = st.slider("Select Maximum Job Cost ($)", min_value=min_possible_cost, max_value=max_possible_cost, value=max_possible_cost, step=100)
df_agg_filtered = df_valid[df_valid["final_price_calculated"] <= max_job_cost] 

if df_agg_filtered.empty:
    st.error("No colors available within the selected cost range.")
    st.stop()

records = df_agg_filtered.to_dict("records")
if not records: 
    st.error("No material records available to select after all filters.")
    st.stop()

selected_record = st.selectbox("Select Material/Color", options=records,
                               format_func=lambda rec: f"{rec.get('Full Name', 'N/A')} ({rec.get('Location', 'N/A')}) - (${rec.get('final_price_calculated', 0) / sq_ft_used:.2f}/sq ft)")

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

    # --- DETAILED BREAKDOWN EXPANDER ---
    with st.expander("View Detailed Breakdown"):
        st.markdown(f"- **Slab Selected:** {selected_record.get('Full Name', 'N/A')}")
        st.markdown(f"- **Material Source Location:** {selected_record.get('Location', 'N/A')}")
        st.markdown(f"- **Fabrication Plant (for selected branch '{selected_branch}'):** {fabrication_plant}") 
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
        st.markdown(f"- **GST ({GST_RATE*100:.0f}%):** ${gst_amount:,.2f}")
        st.markdown(f"- **Total Including GST (before final markup):** ${(sub_total + gst_amount):,.2f}")
        st.markdown(f"- **Final Marked-up Price (including GST):** ${final_price_marked_up:,.2f}")
        st.markdown(f"Calculation: ((Subtotal + GST) * (1 + {FINAL_MARKUP_PERCENTAGE*100:.0f}% Markup))")

    # --- Placeholder for Email Button ---
    if selected_salesperson_email: # Only show if a salesperson is selected
        if st.button(f"Email Breakdown to {selected_salesperson_display}"):
            st.info("Email sending functionality to be implemented.")
            # Here you would:
            # 1. Compose the email body with breakdown details.
            # 2. Call your send_email function.
            # send_email_function(subject, email_body, "your_sender_email@example.com", selected_salesperson_email, st.secrets["SMTP_SERVER"], ...)
            pass # Replace with actual email sending call

else:
    st.info("Please make a material selection to see price details and breakdown.")

st.markdown("---")
st.caption(f"Countertop Estimator. For Branch: '{selected_branch}'. Data sourced from '{MASTER_INVENTORY_SHEET_TAB_NAME}'. Time: {pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d %H:%M:%S %Z')}")
