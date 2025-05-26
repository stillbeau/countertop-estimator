import streamlit as st
import pandas as pd
import gspread
import json
import smtplib
from email.mime.text import MIMEText 
import pytz # Import pytz for timezone handling

# --- Custom CSS ---
st.markdown("""
    <style>
    div[data-baseweb="select"] { font-size: 0.8rem; }
    .stLabel, label { font-size: 0.8rem; }
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
MASTER_INVENTORY_SHEET_TAB_NAME = "InventoryData"
SALESPEOPLE_SHEET_TAB_NAME = "Salespeople"

# --- Function to load data from Google Sheets ---
@st.cache_data(show_spinner=False)
def load_data_from_google_sheet(sheet_name_to_load):
    creds_dict = None
    try:
        creds_json_str = st.secrets["gcp_service_account"]
        creds_dict = json.loads(creds_json_str)
    except KeyError:
        st.error("❌ Config Error: 'gcp_service_account' secret missing. App cannot access data. Please contact administrator.")
        return pd.DataFrame()
    except json.JSONDecodeError as jde:
        st.error(f"❌ Config Error: Failed to parse Google credentials: {jde}. Please contact administrator.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Config Error: Unexpected issue loading credentials: {e}. Please contact administrator.")
        return pd.DataFrame()

    gc = None
    try:
        gc = gspread.service_account_from_dict(creds_dict, scopes=SCOPES)
    except Exception as e:
        st.error(f"❌ Connection Error: Failed to init Google Sheets client: {e}. Please contact administrator.")
        return pd.DataFrame()

    if gc is None:
        st.error("❌ Connection Error: Google Sheets client is None. Contact administrator.")
        return pd.DataFrame()

    open_method = None
    gc_attributes = dir(gc) 
    if 'open_by_key' in gc_attributes: open_method = gc.open_by_key
    elif 'open_by_id' in gc_attributes: open_method = gc.open_by_id
    else:
        st.error(f"❌ Critical Error: Required gspread methods not found on client object. App may be misconfigured. Please contact administrator.")
        return pd.DataFrame()

    spreadsheet = None
    try:
        spreadsheet = open_method(SPREADSHEET_ID)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ Data Error: Spreadsheet not found (ID: ...{SPREADSHEET_ID[-10:]}). Check setup and sharing with: {creds_dict.get('client_email')}")
        return pd.DataFrame()
    except gspread.exceptions.APIError as apie:
        st.error(f"❌ API Error: Google Sheets API issue: {apie}. Check permissions/limits.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error: Unexpected issue opening spreadsheet: {e}.")
        return pd.DataFrame()

    if spreadsheet is None: return pd.DataFrame()

    worksheet = None
    try:
        worksheet = spreadsheet.worksheet(sheet_name_to_load)
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"❌ Data Error: Worksheet tab '{sheet_name_to_load}' not found in '{spreadsheet.title}'.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error: Unexpected issue opening worksheet '{sheet_name_to_load}': {e}.")
        return pd.DataFrame()

    if worksheet is None: return pd.DataFrame()
        
    df = None
    try:
        df = pd.DataFrame(worksheet.get_all_records())
    except Exception as e:
        st.error(f"❌ Error: Could not retrieve records from '{worksheet.title}': {e}.")
        return pd.DataFrame()

    if df is None or df.empty:
        st.warning(f"⚠️ No data found in worksheet '{worksheet.title}'.")
        return pd.DataFrame()

    try:
        df.columns = df.columns.str.strip()
        if sheet_name_to_load == MASTER_INVENTORY_SHEET_TAB_NAME:
            required_cols = ["Serialized On Hand Cost", "Available Sq Ft", "Location", "Brand", "Color", "Thickness"]
        elif sheet_name_to_load == SALESPEOPLE_SHEET_TAB_NAME:
            required_cols = ["SalespersonName", "Branch", "Email"]
        else: required_cols = []

        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            st.error(f"❌ Data Error: Critical data columns missing from '{sheet_name_to_load}': {', '.join(missing_cols)}. Found: {list(df.columns)}")
            return pd.DataFrame()
        
        if sheet_name_to_load == MASTER_INVENTORY_SHEET_TAB_NAME:
            df["Serialized On Hand Cost"] = pd.to_numeric(df["Serialized On Hand Cost"].astype(str).str.replace("[\\$, ]", "", regex=True).str.strip(), errors='coerce')
            df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors='coerce')
            if "Serial Number" in df.columns:
                df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors='coerce').fillna(0).astype(int)
            else: df["Serial Number"] = 0 
            df.dropna(subset=['Serialized On Hand Cost', 'Available Sq Ft', 'Location', 'Brand', 'Color', 'Thickness'], inplace=True)
            df = df[df['Available Sq Ft'] > 0] 
        
        elif sheet_name_to_load == SALESPEOPLE_SHEET_TAB_NAME:
            for col in required_cols: df[col] = df[col].astype(str).str.strip()
            df.dropna(subset=required_cols, inplace=True)
            df = df[df['Email'].str.contains('@', na=False)] 

        if df.empty:
            st.warning(f"⚠️ No valid data in '{sheet_name_to_load}' after cleaning.")
            return pd.DataFrame()
        return df
    except Exception as e:
        st.error(f"❌ Error: Failed processing data for '{sheet_name_to_load}': {e}.")
        return pd.DataFrame()

# --- Cost Calculation Function ---
def calculate_aggregated_costs(record, sq_ft_used):
    unit_cost = record.get("unit_cost", 0); unit_cost = 0 if unit_cost is None else unit_cost
    material_cost_with_markup = unit_cost * MARKUP_FACTOR * sq_ft_used
    fabrication_total = FABRICATION_COST_PER_SQFT * sq_ft_used
    material_and_fab = material_cost_with_markup + fabrication_total
    install_cost = INSTALL_COST_PER_SQFT * sq_ft_used
    total_cost = material_and_fab + install_cost
    ib_total_cost = (unit_cost + FABRICATION_COST_PER_SQFT + ADDITIONAL_IB_RATE) * sq_ft_used
    return {"available_sq_ft": record.get("available_sq_ft", 0),"material_and_fab": material_and_fab,"install_cost": install_cost,"total_cost": total_cost,"ib_cost": ib_total_cost}

# --- Function to Compose Email Body (CLEANER FORMATTING) ---
def compose_breakdown_email_body(selected_branch, selected_record, costs, fabrication_plant, selected_edge_profile, selected_thickness, sq_ft_used, sub_total, gst_amount, final_price_marked_up):
    # Use consistent formatting for currency
    def format_currency(value):
        return f"${value:,.2f}"

    body = f"Subject: Countertop Estimate for {selected_branch} - {selected_record.get('Full Name', 'N/A')}\n\n" # Subject in body as well for clarity
    body += "Dear Valued Customer / Salesperson,\n\n"
    body += "Please find below the detailed estimate for your countertop project:\n\n"

    # --- Project & Material Overview ---
    body += "=================================================\n"
    body += "           PROJECT & MATERIAL OVERVIEW\n"
    body += "=================================================\n"
    body += f"Branch Location:          {selected_branch}\n"
    body += f"Slab Selected:            {selected_record.get('Full Name', 'N/A')}\n"
    body += f"Material Source Location: {selected_record.get('Location', 'N/A')}\n"
    body += f"Fabrication Plant:        {fabrication_plant}\n"
    body += f"Edge Profile Selected:    {selected_edge_profile}\n"
    body += f"Thickness Selected:       {selected_thickness}\n"
    body += f"Square Footage (for pricing): {sq_ft_used} sq.ft\n"
    body += f"Slab Sq Ft (Aggregated):  {selected_record.get('available_sq_ft', 0):.2f} sq.ft\n"
    body += f"Number of Unique Slabs:   {selected_record.get('slab_count', 0)}\n"
    body += f"Contributing Serial Numbers: {selected_record.get('serial_numbers', 'N/A')}\n\n"

    # --- Cost Components ---
    body += "=================================================\n"
    body += "                 COST COMPONENTS\n"
    body += "=================================================\n"
    body += f"Material & Fabrication:   {format_currency(costs.get('material_and_fab', 0))}\n"
    body += f"Installation:             {format_currency(costs.get('install_cost', 0))}\n"
    body += f"IB Cost Component:        {format_currency(costs.get('ib_cost', 0))}\n\n"

    # --- Totals ---
    body += "=================================================\n"
    body += "                     TOTALS\n"
    body += "=================================================\n"
    body += f"Subtotal (before tax & final markup): {format_currency(sub_total)}\n"
    body += f"GST ({GST_RATE*100:.0f}%):                    {format_currency(gst_amount)}\n"
    body += "-------------------------------------------------\n"
    body += f"Total Including GST:      {format_currency(sub_total + gst_amount)}\n"
    body += f"Final Marked-up Price:    {format_currency(final_price_marked_up)}\n"
    body += "=================================================\n\n"
    body += "(Calculation: ((Subtotal + GST) * (1 + Final Markup Percentage)))\n"
    body += f"(Final Markup Percentage: {FINAL_MARKUP_PERCENTAGE*100:.0f}%)\n\n"
    body += "Thank you for using our Countertop Cost Estimator!\n"
    body += "--------------------------------------------------\n"
    
    # Ensure pytz is installed if you use it for timezones. pip install pytz
    vancouver_tz = pytz.timezone('America/Vancouver')
    body += f"Generated on: {pd.Timestamp.now(tz=vancouver_tz).strftime('%Y-%m-%d %H:%M:%S %Z')}"

    return body

# --- Function to Send Email ---
def send_email(subject, body, receiver_email):
    try:
        smtp_user = st.secrets["EMAIL_USER"] # SMTP login username
        smtp_password = st.secrets["EMAIL_PASSWORD"]
        smtp_server = st.secrets["SMTP_SERVER"]
        smtp_port = int(st.secrets["SMTP_PORT"])

        # Use the verified sender email from secrets for the 'From' header
        sender_from_header = st.secrets.get("SENDER_FROM_EMAIL", smtp_user) 
        
        # Recipient email domain validation is removed for testing (re-add for production if needed)
        # if not receiver_email.lower().endswith("@floform.com"):
        #     st.error("Error: Breakdown can only be sent to @floform.com email addresses.")
        #     return False

        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = sender_from_header 
        msg['To'] = receiver_email

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls() 
            server.login(smtp_user, smtp_password) 
            server.sendmail(sender_from_header, receiver_email, msg.as_string()) 
        st.success(f"Breakdown emailed successfully to {receiver_email}!")
        return True
    except KeyError as e:
        st.error(f"SMTP configuration error: Missing secret {e}. Please contact administrator.")
        return False
    except Exception as e:
        st.error(f"Error sending email: {e}")
        return False

# --- Streamlit UI Begins Here ---
st.title("Countertop Cost Estimator")
st.write("Get an accurate estimate for your custom countertop project.")

df_master_inventory = None
df_salespeople = pd.DataFrame() 

with st.spinner(f"Loading all inventory data from '{MASTER_INVENTORY_SHEET_TAB_NAME}'..."):
    df_master_inventory = load_data_from_google_sheet(MASTER_INVENTORY_SHEET_TAB_NAME) 
with st.spinner(f"Loading salespeople data from '{SALESPEOPLE_SHEET_TAB_NAME}'..."):
    df_salespeople = load_data_from_google_sheet(SALESPEOPLE_SHEET_TAB_NAME)

if df_master_inventory.empty: 
    st.error(f"Could not load master inventory data from '{MASTER_INVENTORY_SHEET_TAB_NAME}'. App cannot proceed.")
    st.stop()
if df_salespeople.empty:
    st.warning(f"⚠️ Could not load salespeople data. Emailing functionality will be limited/unavailable.")
    df_salespeople = pd.DataFrame() 

sales_branch_locations = ["Vernon", "Victoria", "Vancouver", "Calgary", "Edmonton", "Saskatoon", "Winnipeg"] 
selected_branch = st.selectbox("Select Your Branch Location", sales_branch_locations)

selected_salesperson_email = None
selected_salesperson_display = "None" 

if not df_salespeople.empty:
    salespeople_in_branch_df = df_salespeople[df_salespeople["Branch"].astype(str).str.lower() == selected_branch.lower()]
    if not salespeople_in_branch_df.empty:
        salesperson_options = salespeople_in_branch_df.apply(lambda x: f"{x['SalespersonName']} ({x['Email']})", axis=1).tolist()
        selected_salesperson_display = st.selectbox(f"Select Salesperson in {selected_branch} (for Email)", options=["None"] + salesperson_options)
        if selected_salesperson_display != "None":
            try:
                start_index = selected_salesperson_display.rfind('(') + 1
                end_index = selected_salesperson_display.rfind(')')
                selected_salesperson_email = selected_salesperson_display[start_index:end_index]
            except Exception: selected_salesperson_email = None 
    else: st.caption(f"No salespeople listed for {selected_branch} branch.")
else: st.caption("Salespeople data not loaded or empty.")

branch_to_material_sources = {
    "Vernon": ["Vernon", "Abbotsford"], "Victoria": ["Vernon", "Abbotsford"], 
    "Vancouver": ["Vernon", "Abbotsford"], "Calgary": ["Edmonton", "Saskatoon"],  
    "Edmonton": ["Edmonton", "Saskatoon"], "Saskatoon": ["Edmonton", "Saskatoon"], "Winnipeg": ["Edmonton", "Saskatoon"], 
}
allowed_locations_for_branch = branch_to_material_sources.get(selected_branch, [])
df_inventory = pd.DataFrame() 
if "Location" in df_master_inventory.columns:
    if allowed_locations_for_branch:
        df_inventory = df_master_inventory[df_master_inventory["Location"].isin(allowed_locations_for_branch)]
    else:
        st.warning(f"No material sources defined for branch '{selected_branch}'. Showing all inventory.")
        df_inventory = df_master_inventory.copy()
else:
    st.error("Master inventory is missing 'Location' column. Cannot filter by branch.")
    df_inventory = df_master_inventory.copy() 

if df_inventory.empty: 
    st.warning(f"No inventory for branch '{selected_branch}' after location filter.")
    st.stop()

def get_fabrication_plant(branch): 
    if branch in ["Vernon", "Victoria", "Vancouver"]: return "Abbotsford"
    if branch in ["Calgary", "Edmonton", "Saskatoon", "Winnipeg"]: return "Saskatoon"
    return "Unknown"
fabrication_plant = get_fabrication_plant(selected_branch)
st.markdown(f"**Orders for {selected_branch} will be fabricated at:** {fabrication_plant}")

if "Thickness" not in df_inventory.columns: 
    st.error("Data Error: 'Thickness' column missing. Cannot proceed."); st.stop()
df_inventory["Thickness"] = df_inventory["Thickness"].astype(str).str.strip().str.lower()
thickness_options = sorted(list(df_inventory["Thickness"].unique())) 
if not thickness_options: st.warning("No thickness options available."); st.stop()
default_thickness_index = thickness_options.index("3cm") if "3cm" in thickness_options else 0
selected_thickness = st.selectbox("Select Thickness", options=thickness_options, index=default_thickness_index)
df_inventory = df_inventory[df_inventory["Thickness"] == selected_thickness.lower()]
if df_inventory.empty: st.warning(f"No slabs match thickness '{selected_thickness}'."); st.stop()

if not ("Brand" in df_inventory.columns and "Color" in df_inventory.columns):
    st.error("Data Error: 'Brand' or 'Color' columns missing. Cannot proceed."); st.stop()
df_inventory["Full Name"] = df_inventory["Brand"].astype(str) + " - " + df_inventory["Color"].astype(str)

if not ("Serialized On Hand Cost" in df_inventory.columns and "Available Sq Ft" in df_inventory.columns):
    st.error("Data Error: Costing columns missing. Cannot proceed."); st.stop()
df_inventory = df_inventory[df_inventory['Available Sq Ft'].notna() & (df_inventory['Available Sq Ft'] > 0)] 
if df_inventory.empty: st.error("No inventory with valid 'Available Sq Ft'."); st.stop()
df_inventory["unit_cost"] = df_inventory["Serialized On Hand Cost"] / df_inventory["Available Sq Ft"]


sq_ft_input = st.number_input("Enter Square Footage Needed", min_value=1, value=40, step=1)
sq_ft_used = max(sq_ft_input, MINIMUM_SQ_FT)
if sq_ft_input < MINIMUM_SQ_FT: st.info(f"Minimum is {MINIMUM_SQ_FT} sq ft. Using {MINIMUM_SQ_FT} for pricing.")

df_agg = (df_inventory.groupby(["Full Name", "Location"]) 
          .agg(available_sq_ft=("Available Sq Ft", "sum"), unit_cost=("unit_cost", "mean"), 
               slab_count=("Serial Number", "nunique"), 
               serial_numbers=("Serial Number", lambda x: ", ".join(sorted(list(x.astype(str).unique()))))) 
          .reset_index())
required_material = sq_ft_used * 1.1
df_agg = df_agg[df_agg["available_sq_ft"] >= required_material]
if df_agg.empty: st.error("No colors have enough material (inc. buffer)."); st.stop()

df_agg["final_price_calculated"] = df_agg.apply(lambda r: calculate_aggregated_costs(r,sq_ft_used)["total_cost"]*(1+GST_RATE),axis=1)
df_valid = df_agg[df_agg["final_price_calculated"] > 0] 
if df_valid.empty: st.error("No valid slab prices after calculations."); st.stop()

min_c, max_c = (int(df_valid["final_price_calculated"].min()), int(df_valid["final_price_calculated"].max())) if not df_valid.empty else (0,10000)
if min_c >= max_c: max_c = min_c + 100
max_job_cost = st.slider("Max Job Cost ($)", min_value=min_c, max_value=max_c, value=max_c, step=100)
df_agg_filtered = df_valid[df_valid["final_price_calculated"] <= max_job_cost] 
if df_agg_filtered.empty: st.error("No colors in selected cost range."); st.stop()

records = df_agg_filtered.to_dict("records")
if not records: st.error("No material records to select."); st.stop()
selected_record = st.selectbox("Select Material/Color", records, format_func=lambda r: f"{r.get('Full Name','N/A')} ({r.get('Location','N/A')}) - (${r.get('final_price_calculated',0)/sq_ft_used:.2f}/sq ft)")

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

    if selected_record.get('slab_count', 0) > 1: st.info("Note: Multiple slabs used; color/pattern may vary.")

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

    # --- Email Button Logic ---
    if selected_salesperson_email: 
        if st.button(f"Email Breakdown to {selected_salesperson_display}"):
            # Domain validation is removed for testing, but ensure it's re-added for production
            # if selected_salesperson_email.lower().endswith("@floform.com"):
            email_subject = f"Countertop Estimate for {selected_branch} - {selected_record.get('Full Name', 'N/A')}"
            email_body = compose_breakdown_email_body(
                selected_branch, selected_record, costs, fabrication_plant, 
                selected_edge_profile, selected_thickness, sq_ft_used, 
                sub_total, gst_amount, final_price_marked_up
            )
            send_email(
                subject=email_subject,
                body=email_body,
                receiver_email=selected_salesperson_email
            )
            # else:
            #     st.error("Error: Selected salesperson email is not a valid @floform.com address.")
    elif selected_salesperson_display != "None": 
        st.warning(f"Could not determine a valid email for {selected_salesperson_display} to send breakdown.")

else: st.info("Please make a material selection to see price details and breakdown.")

st.markdown("---")
st.caption(f"Estimator. Branch: '{selected_branch}'. Data sourced from '{MASTER_INVENTORY_SHEET_TAB_NAME}'. Time: {pd.Timestamp.now(tz='America/Vancouver').strftime('%Y-%m-%d %H:%M:%S %Z')}")
