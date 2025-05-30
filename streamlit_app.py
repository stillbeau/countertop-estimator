import streamlit as st
import pandas as pd
import gspread
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz # Import pytz for timezone handling

# --- Custom CSS ---
st.markdown("""
    <style>
    div[data-baseweb="select"] { font-size: 0.8rem; }
    .stLabel, label { font-size: 0.8rem; }
    </style>
""", unsafe_allow_html=True)

# --- Configurations ---
MINIMUM_SQ_FT = 35.0 # Made it float for consistency with number_input step
MARKUP_FACTOR = 1.25
INSTALL_COST_PER_SQFT = 27.0
FABRICATION_COST_PER_SQFT = 17.0
ADDITIONAL_IB_RATE = 0.0
GST_RATE = 0.05

# --- Google Sheets API Configuration ---
SPREADSHEET_ID = "166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
MASTER_INVENTORY_SHEET_TAB_NAME = "InventoryData"
SALESPEOPLE_SHEET_TAB_NAME = "Salespeople"

# --- Function to load data from Google Sheets ---
@st.cache_data(show_spinner=False)
def load_data_from_google_sheet(sheet_name_to_load):
    creds_data_from_secrets = None
    try:
        creds_data_from_secrets = st.secrets["gcp_service_account"]
    except KeyError:
        st.error(f"❌ Config Error: 'gcp_service_account' secret missing in Streamlit secrets. App cannot access {sheet_name_to_load}. Please contact administrator.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Config Error: Unexpected issue retrieving 'gcp_service_account' secret: {e}. Please contact administrator.")
        return pd.DataFrame()

    if creds_data_from_secrets is None:
        st.error(f"❌ Config Error: 'gcp_service_account' secret value is None after retrieval. Cannot access {sheet_name_to_load}. Please contact administrator.")
        return pd.DataFrame()

    creds_dict = None
    try:
        if isinstance(creds_data_from_secrets, str):
            creds_dict = json.loads(creds_data_from_secrets)
        elif isinstance(creds_data_from_secrets, dict) or hasattr(creds_data_from_secrets, 'get'): # Handles AttrDict from TOML table
            creds_dict = dict(creds_data_from_secrets)
        else:
            st.error(f"❌ Config Error: 'gcp_service_account' secret is an unexpected type: {type(creds_data_from_secrets)}. Expected a JSON string or a dictionary-like object. Cannot access {sheet_name_to_load}. Please contact administrator.")
            return pd.DataFrame()
    except json.JSONDecodeError as jde:
        st.error(f"❌ Config Error: Failed to parse Google credentials from JSON string for {sheet_name_to_load}: {jde}. Please contact administrator.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Config Error: Unexpected issue preparing credentials from secret for {sheet_name_to_load}: {e}. Please contact administrator.")
        return pd.DataFrame()

    if creds_dict is None:
        st.error(f"❌ Config Error: Failed to prepare a valid credentials dictionary for {sheet_name_to_load}. Please contact administrator.")
        return pd.DataFrame()

    gc = None
    try:
        gc = gspread.service_account_from_dict(creds_dict, scopes=SCOPES)
    except Exception as e:
        st.error(f"❌ Connection Error: Failed to initialize Google Sheets client for {sheet_name_to_load} with processed credentials: {e}. Please contact administrator.")
        return pd.DataFrame()

    if gc is None:
        st.error(f"❌ Connection Error: Google Sheets client is None after attempting initialization for {sheet_name_to_load}. Contact administrator.")
        return pd.DataFrame()

    open_method = None
    if hasattr(gc, 'open_by_key'): open_method = gc.open_by_key
    elif hasattr(gc, 'open_by_id'): open_method = gc.open_by_id # open_by_id is often an alias
    else:
        st.error(f"❌ Critical Error: Required gspread open methods not found on client object. App may be misconfigured or gspread version issue. Cannot access {sheet_name_to_load}. Please contact administrator.")
        return pd.DataFrame()

    spreadsheet = None
    try:
        spreadsheet = open_method(SPREADSHEET_ID)
    except gspread.exceptions.SpreadsheetNotFound:
        client_email_info = creds_dict.get('client_email', 'UNKNOWN (could not read from credentials)')
        st.error(f"❌ Data Error: Spreadsheet not found (ID: ...{SPREADSHEET_ID[-10:]}). Ensure it's shared with: {client_email_info}. Cannot access {sheet_name_to_load}.")
        return pd.DataFrame()
    except gspread.exceptions.APIError as apie:
        st.error(f"❌ API Error: Google Sheets API issue while opening spreadsheet for {sheet_name_to_load}: {apie}. Check permissions/limits or API enablement in Google Cloud Console.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error: Unexpected issue opening spreadsheet for {sheet_name_to_load}: {e}.")
        return pd.DataFrame()

    if spreadsheet is None: return pd.DataFrame()

    worksheet = None
    try:
        worksheet = spreadsheet.worksheet(sheet_name_to_load)
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"❌ Data Error: Worksheet tab '{sheet_name_to_load}' not found in spreadsheet '{spreadsheet.title}'.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error: Unexpected issue opening worksheet '{sheet_name_to_load}': {e}.")
        return pd.DataFrame()

    if worksheet is None: return pd.DataFrame()

    df_records = None
    try:
        df_records = worksheet.get_all_records()
    except Exception as e:
        st.error(f"❌ Error: Could not retrieve records from worksheet '{worksheet.title}': {e}.")
        return pd.DataFrame()

    if not df_records: # Handles empty list from get_all_records if sheet is empty
        st.warning(f"⚠️ No records found in worksheet '{worksheet.title}'. The sheet might be empty or headers might be missing.")
        return pd.DataFrame()

    df = pd.DataFrame(df_records)

    if df.empty:
        st.warning(f"⚠️ No data loaded into DataFrame from worksheet '{worksheet.title}'.")
        return pd.DataFrame()

    try:
        df.columns = df.columns.str.strip()
        if sheet_name_to_load == MASTER_INVENTORY_SHEET_TAB_NAME:
            required_cols = ["Serialized On Hand Cost", "Available Sq Ft", "Location", "Brand", "Color", "Thickness", "Serial Number"]
        elif sheet_name_to_load == SALESPEOPLE_SHEET_TAB_NAME:
            required_cols = ["SalespersonName", "Branch", "Email"]
        else: required_cols = []

        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            st.error(f"❌ Data Error: Critical data columns missing from '{sheet_name_to_load}': {', '.join(missing_cols)}. Found columns: {list(df.columns)}")
            return pd.DataFrame()

        if sheet_name_to_load == MASTER_INVENTORY_SHEET_TAB_NAME:
            df["Serialized On Hand Cost"] = pd.to_numeric(df["Serialized On Hand Cost"].astype(str).str.replace(r"[$, ]", "", regex=True).str.strip(), errors='coerce')
            df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors='coerce')
            df["Serial Number Str"] = df["Serial Number"].astype(str).str.strip() # For string joining later
            df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors='coerce').fillna(0).astype(int) # For nunique

            df.dropna(subset=['Serialized On Hand Cost', 'Available Sq Ft', 'Location', 'Brand', 'Color', 'Thickness'], inplace=True)
            df = df[df['Available Sq Ft'] > 0]

        elif sheet_name_to_load == SALESPEOPLE_SHEET_TAB_NAME:
            for col in required_cols: df[col] = df[col].astype(str).str.strip()
            df.dropna(subset=required_cols, inplace=True) # Drop if any required field is empty after stripping
            df = df[df['Email'].str.contains('@', na=False)]

        if df.empty:
            st.warning(f"⚠️ No valid data in '{sheet_name_to_load}' after cleaning and validation. Please check data integrity.")
        return df
    except Exception as e:
        st.error(f"❌ Error: Failed processing data for '{sheet_name_to_load}': {e}.")
        return pd.DataFrame()

# --- Cost Calculation Function ---
def calculate_aggregated_costs(record, sq_ft_used):
    unit_cost = record.get("unit_cost", 0.0)
    unit_cost = 0.0 if pd.isna(unit_cost) else float(unit_cost)

    material_cost_with_markup = unit_cost * MARKUP_FACTOR * sq_ft_used
    fabrication_total = FABRICATION_COST_PER_SQFT * sq_ft_used
    install_cost = INSTALL_COST_PER_SQFT * sq_ft_used

    ib_cost_component = (unit_cost + FABRICATION_COST_PER_SQFT + ADDITIONAL_IB_RATE) * sq_ft_used

    base_material_and_fab_component = material_cost_with_markup + fabrication_total
    base_install_cost_component = install_cost
    total_customer_facing_base_cost = base_material_and_fab_component + base_install_cost_component

    return {
        "available_sq_ft": record.get("available_sq_ft", 0.0),
        "base_material_and_fab_component": base_material_and_fab_component,
        "base_install_cost_component": base_install_cost_component,
        "ib_cost_component": ib_cost_component,
        "total_customer_facing_base_cost": total_customer_facing_base_cost
    }

# --- Function to Compose HTML Email Body ---
def compose_breakdown_email_body(job_name, selected_branch, selected_record, costs, fabrication_plant, selected_thickness, sq_ft_used, additional_costs_input, base_sub_total_after_additions, gst_amount, final_price_with_all_costs):
    def format_currency_html(value): return f"${float(value):,.2f}"
    vancouver_tz = pytz.timezone('America/Vancouver')
    generated_time = pd.Timestamp.now(tz=vancouver_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
    job_name_display = job_name if job_name else "Unnamed Job"
    html_body = f"""
    <html><head><style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ width: 100%; max-width: 600px; margin: 0 auto; background-color: #f9f9f9; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        h1, h2 {{ color: #0056b3; }} h2 {{border-bottom: 1px solid #eee; padding-bottom: 5px; margin-top: 20px;}}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }} th {{ background-color: #e9e9e9; }}
        .total-row td {{ font-weight: bold; background-color: #e0e0e0; }} .grand-total-row td {{ font-weight: bold; background-color: #c9e0ff; font-size: 1.1em; }}
        .note {{ font-size: 0.9em; color: #666; margin-top: 15px; }} .footer {{ font-size: 0.8em; color: #999; text-align: center; margin-top: 30px; padding-top: 10px; border-top: 1px solid #eee; }}
    </style></head><body><div class="container">
        <h1>CounterPro Estimate</h1><p>Dear Valued Customer / Salesperson,</p><p>Please find below the detailed estimate for your countertop project:</p>
        <h2>Project & Material Overview</h2><table>
            <tr><th>Detail</th><th>Value</th></tr>
            <tr><td>Job Name:</td><td>{job_name_display}</td></tr>
            <tr><td>Branch Location:</td><td>{selected_branch}</td></tr>
            <tr><td>Slab Selected:</td><td>{selected_record.get('Full Name', 'N/A')}</td></tr>
            <tr><td>Material Source Location:</td><td>{selected_record.get('Location', 'N/A')}</td></tr>
            <tr><td>Fabrication Plant:</td><td>{fabrication_plant}</td></tr>
            <tr><td>Thickness Selected:</td><td>{selected_thickness}</td></tr>
            <tr><td>Square Footage (for pricing):</td><td>{sq_ft_used:.2f} sq.ft</td></tr>
            <tr><td>Slab Sq Ft (Aggregated):</td><td>{selected_record.get('available_sq_ft', 0.0):.2f} sq.ft</td></tr>
            <tr><td>Number of Unique Slabs:</td><td>{selected_record.get('slab_count', 0)}</td></tr>
            <tr><td>Contributing Serial Numbers:</td><td>{selected_record.get('serial_numbers_str', 'N/A')}</td></tr>
        </table>
        <h2>Cost Components</h2><table>
            <tr><th>Component</th><th>Amount</th></tr>
            <tr><td>Material & Fabrication:</td><td>{format_currency_html(costs.get('base_material_and_fab_component', 0))}</td></tr>
            <tr><td>Installation:</td><td>{format_currency_html(costs.get('base_install_cost_component', 0))}</td></tr>
            <tr><td>Internal Billing (IB) Cost Component:</td><td>{format_currency_html(costs.get('ib_cost_component', 0))}</td></tr>
        </table>
        <h2>Totals</h2><table>
            <tr><th>Description</th><th>Amount</th></tr>
            <tr><td>Base Estimate (Material/Fab/Install):</td><td>{format_currency_html(costs.get('total_customer_facing_base_cost', 0))}</td></tr>
            <tr><td>Additional Costs (Plumbing, Tile, etc.):</td><td>{format_currency_html(additional_costs_input)}</td></tr>
            <tr class="total-row"><td>Subtotal (Before GST):</td><td>{format_currency_html(base_sub_total_after_additions)}</td></tr>
            <tr><td>GST ({GST_RATE*100:.0f}%):</td><td>{format_currency_html(gst_amount)}</td></tr>
            <tr class="grand-total-row"><td>Final Estimated Price:</td><td>{format_currency_html(final_price_with_all_costs)}</td></tr>
        </table>
        <div class="note"><p><strong>Please Note:</strong> This is an estimate and is subject to change based on final template measurements, material availability, and any unforeseen project complexities. Prices are valid for 30 days unless otherwise stated.</p></div>
        <p>Thank you for using our Countertop Cost Estimator!</p><div class="footer">Generated by CounterPro on: {generated_time}</div>
    </div></body></html>
    """
    return html_body

# --- Function to Send Email ---
def send_email(subject, body, receiver_email):
    try:
        smtp_user = st.secrets["EMAIL_USER"]
        smtp_password = st.secrets["EMAIL_PASSWORD"]
        smtp_server = st.secrets["SMTP_SERVER"]
        smtp_port = int(st.secrets["SMTP_PORT"]) # Ensure port is integer
        sender_from_header = st.secrets.get("SENDER_FROM_EMAIL", smtp_user) # Use SENDER_FROM_EMAIL if present, else EMAIL_USER
        tracking_cc_email = st.secrets.get("QUOTE_TRACKING_CC_EMAIL", "").strip() # Get and strip, empty if not present

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_from_header
        msg['To'] = receiver_email

        all_recipients = [receiver_email]
        if tracking_cc_email:
            msg['Cc'] = tracking_cc_email
            all_recipients.append(tracking_cc_email)

        msg.attach(MIMEText(body, 'html'))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(sender_from_header, all_recipients, msg.as_string())

        st.success(f"Breakdown emailed successfully to {receiver_email}" + (f" and CC'd to {tracking_cc_email}." if tracking_cc_email else "."))
        return True
    except KeyError as e:
        st.error(f"❌ SMTP Configuration Error: Missing secret {e}. Email not sent. Please contact administrator.")
        return False
    except smtplib.SMTPAuthenticationError:
        st.error("❌ SMTP Authentication Error: Check EMAIL_USER and EMAIL_PASSWORD. Email not sent.")
        return False
    except Exception as e:
        st.error(f"❌ Error Sending Email: {e}. Email not sent.")
        return False

# --- Streamlit UI Begins Here ---
st.set_page_config(page_title="CounterPro Estimator", layout="centered")
st.title("CounterPro Estimator")
st.write("Get an accurate estimate for your custom countertop project.")

# Load data with spinners
with st.spinner(f"Loading inventory data from '{MASTER_INVENTORY_SHEET_TAB_NAME}'..."):
    df_master_inventory = load_data_from_google_sheet(MASTER_INVENTORY_SHEET_TAB_NAME)
with st.spinner(f"Loading salespeople data from '{SALESPEOPLE_SHEET_TAB_NAME}'..."):
    df_salespeople = load_data_from_google_sheet(SALESPEOPLE_SHEET_TAB_NAME)

# Critical check for master inventory
if df_master_inventory.empty:
    st.error(f"Could not load master inventory data from '{MASTER_INVENTORY_SHEET_TAB_NAME}'. App cannot proceed.")
    st.stop()

# Handle salespeople data (non-critical for app to run, but limits email)
if df_salespeople.empty:
    st.warning(f"⚠️ Salespeople data not loaded or empty from '{SALESPEOPLE_SHEET_TAB_NAME}'. Emailing functionality to salespeople will be unavailable.")
    df_salespeople = pd.DataFrame(columns=["SalespersonName", "Branch", "Email"]) # Ensure it's an empty DF with expected columns

# --- UI Inputs ---
sales_branch_locations = ["Vernon", "Victoria", "Vancouver", "Calgary", "Edmonton", "Saskatoon", "Winnipeg"]
selected_branch = st.selectbox("Select Your Branch Location:", sales_branch_locations)

selected_salesperson_email = None
selected_salesperson_display = "None"
if "Branch" in df_salespeople.columns and "SalespersonName" in df_salespeople.columns and "Email" in df_salespeople.columns:
    salespeople_in_branch_df = df_salespeople[df_salespeople["Branch"].astype(str).str.lower() == selected_branch.lower()]
    if not salespeople_in_branch_df.empty:
        salesperson_options = ["None"] + sorted(salespeople_in_branch_df['SalespersonName'].unique().tolist())
        selected_salesperson_display = st.selectbox(f"Select Salesperson in {selected_branch} (for Email):", options=salesperson_options)
        if selected_salesperson_display != "None":
            selected_salesperson_row = salespeople_in_branch_df[salespeople_in_branch_df['SalespersonName'] == selected_salesperson_display]
            if not selected_salesperson_row.empty:
                selected_salesperson_email = selected_salesperson_row['Email'].iloc[0]
    else:
        st.caption(f"No salespeople listed for {selected_branch} branch in the loaded data.")
else:
    st.caption("Salespeople data is incomplete (missing Branch, Name, or Email columns). Salesperson selection unavailable.")


branch_to_material_sources = {
    "Vernon": ["Vernon", "Abbotsford"], "Victoria": ["Vernon", "Abbotsford"],
    "Vancouver": ["Vernon", "Abbotsford"], "Calgary": ["Edmonton", "Saskatoon"],
    "Edmonton": ["Edmonton", "Saskatoon"], "Saskatoon": ["Edmonton", "Saskatoon"], "Winnipeg": ["Edmonton", "Saskatoon"],
}
allowed_locations_for_branch = branch_to_material_sources.get(selected_branch, [])

df_inventory_filtered_by_loc = pd.DataFrame()
if "Location" in df_master_inventory.columns:
    if allowed_locations_for_branch:
        df_inventory_filtered_by_loc = df_master_inventory[df_master_inventory["Location"].isin(allowed_locations_for_branch)]
    else:
        st.warning(f"No material source locations configured for branch '{selected_branch}'. Showing all inventory (if available).")
        df_inventory_filtered_by_loc = df_master_inventory.copy()
else:
    st.error("Master inventory is missing the 'Location' column. Cannot filter by branch.")
    st.stop()

if df_inventory_filtered_by_loc.empty:
    st.warning(f"No inventory found for branch '{selected_branch}' after applying location filters (Allowed: {', '.join(allowed_locations_for_branch) if allowed_locations_for_branch else 'None'}). Check inventory data or branch configuration.")
    st.stop()

def get_fabrication_plant(branch_location):
    if branch_location in ["Vernon", "Victoria", "Vancouver"]: return "Abbotsford"
    if branch_location in ["Calgary", "Edmonton", "Saskatoon", "Winnipeg"]: return "Saskatoon"
    return "Unknown"
fabrication_plant = get_fabrication_plant(selected_branch)
st.markdown(f"**Orders for {selected_branch} will be fabricated at:** `{fabrication_plant}`")

if "Thickness" not in df_inventory_filtered_by_loc.columns:
    st.error("Data Error: 'Thickness' column missing from filtered inventory. Cannot proceed."); st.stop()

df_inventory_filtered_by_loc["Thickness"] = df_inventory_filtered_by_loc["Thickness"].astype(str).str.strip().str.lower()
thickness_options = sorted(list(df_inventory_filtered_by_loc["Thickness"].unique()))
if not thickness_options: st.warning("No thickness options available in the filtered inventory for this branch."); st.stop()

default_thickness = "3cm"
if default_thickness not in thickness_options and thickness_options:
    default_thickness = thickness_options[0] # Fallback to first available if "3cm" is not an option
elif not thickness_options: # Should be caught by previous st.stop() but as a safeguard
    st.error("No thickness options found."); st.stop()

selected_thickness = st.selectbox("Select Thickness:", options=thickness_options, index=thickness_options.index(default_thickness))
df_inventory_for_thickness = df_inventory_filtered_by_loc[df_inventory_filtered_by_loc["Thickness"] == selected_thickness.lower()]

if df_inventory_for_thickness.empty:
    st.warning(f"No slabs match selected thickness '{selected_thickness}' in the current inventory selection for {selected_branch}."); st.stop()

# --- Prepare for Aggregation and Costing ---
if not ("Brand" in df_inventory_for_thickness.columns and "Color" in df_inventory_for_thickness.columns):
    st.error("Data Error: 'Brand' or 'Color' columns missing in inventory. Cannot create 'Full Name'."); st.stop()
df_inventory_for_thickness["Full Name"] = df_inventory_for_thickness["Brand"].astype(str).str.strip() + " - " + df_inventory_for_thickness["Color"].astype(str).str.strip()

if not ("Serialized On Hand Cost" in df_inventory_for_thickness.columns and "Available Sq Ft" in df_inventory_for_thickness.columns):
    st.error("Data Error: Essential costing columns ('Serialized On Hand Cost', 'Available Sq Ft') missing."); st.stop()

# Ensure Available Sq Ft is numeric and positive before calculating unit_cost
df_inventory_for_thickness["Available Sq Ft"] = pd.to_numeric(df_inventory_for_thickness["Available Sq Ft"], errors='coerce')
df_inventory_for_thickness.dropna(subset=["Available Sq Ft"], inplace=True) # Drop if not numeric
df_inventory_for_thickness = df_inventory_for_thickness[df_inventory_for_thickness['Available Sq Ft'] > 0]

if df_inventory_for_thickness.empty: st.error("No inventory with valid 'Available Sq Ft' (>0) after thickness selection."); st.stop()

df_inventory_for_thickness["unit_cost"] = df_inventory_for_thickness["Serialized On Hand Cost"] / df_inventory_for_thickness["Available Sq Ft"]
df_inventory_for_thickness.dropna(subset=["unit_cost"], inplace=True) # Drop if unit_cost calculation failed (e.g., non-numeric cost)
df_inventory_for_thickness = df_inventory_for_thickness[df_inventory_for_thickness['unit_cost'] >= 0] # Ensure unit cost is not negative

if df_inventory_for_thickness.empty: st.error("No inventory with valid 'unit_cost' after calculation."); st.stop()

sq_ft_input = st.number_input("Enter Square Footage Needed for Project:", min_value=1.0, value=40.0, step=0.5, format="%.2f")
sq_ft_used_for_pricing = max(sq_ft_input, MINIMUM_SQ_FT)
if sq_ft_input < MINIMUM_SQ_FT:
    st.info(f"Minimum square footage for pricing is {MINIMUM_SQ_FT:.0f} sq ft. Using {MINIMUM_SQ_FT:.0f} sq ft for calculations.")

# --- Aggregate Slabs and Filter by Availability ---
required_material_buffer_factor = 1.10 # 10% buffer for waste/cuts
required_material_with_buffer = sq_ft_used_for_pricing * required_material_buffer_factor

# Group by Full Name and Location to aggregate slabs of the same material/location
df_aggregated_slabs = (df_inventory_for_thickness.groupby(["Full Name", "Location"])
    .agg(
        available_sq_ft=("Available Sq Ft", "sum"),
        unit_cost=("unit_cost", "mean"), # Use mean of unit costs if multiple slabs of same color/loc have slightly different costs
        slab_count=("Serial Number", "nunique"),
        serial_numbers_str=("Serial Number Str", lambda x: ", ".join(sorted(list(x.unique())))) # Use unique string serial numbers
    )
    .reset_index()
)

df_available_options = df_aggregated_slabs[df_aggregated_slabs["available_sq_ft"] >= required_material_with_buffer]
if df_available_options.empty:
    st.error(f"No material options have enough stock ({required_material_with_buffer:.2f} sq ft required, including buffer) for the selected criteria and thickness. Try a different thickness or reduce square footage."); st.stop()

# --- Calculate Prices and Filter by Max Job Cost ---
df_available_options["price_for_initial_filter"] = df_available_options.apply(
    lambda r: calculate_aggregated_costs(r, sq_ft_used_for_pricing)["total_customer_facing_base_cost"], axis=1
)
df_priced_options = df_available_options[df_available_options["price_for_initial_filter"].notna() & (df_available_options["price_for_initial_filter"] > 0)]

if df_priced_options.empty:
    st.error("No valid slab prices after initial calculations. Check cost data and markup factors."); st.stop()

min_cost_slider = int(df_priced_options["price_for_initial_filter"].min())
max_cost_slider = int(df_priced_options["price_for_initial_filter"].max())
if min_cost_slider >= max_cost_slider: max_cost_slider = min_cost_slider + 100 # Ensure range for slider

selected_max_job_cost = st.slider(
    "Filter by Max Estimated Job Cost ($) (Base Price for Material/Fab/Install):",
    min_value=min_cost_slider,
    max_value=max_cost_slider,
    value=max_cost_slider, # Default to max
    step=50
)
df_final_selection_options = df_priced_options[df_priced_options["price_for_initial_filter"] <= selected_max_job_cost]

if df_final_selection_options.empty:
    st.error("No material colors fall within the selected maximum job cost range. Adjust the slider or other criteria."); st.stop()

# --- Material Selection and Final Display ---
material_records_for_selection = df_final_selection_options.to_dict("records")
selected_material_record = st.selectbox(
    "Select Material/Color:",
    options=material_records_for_selection,
    format_func=lambda r: f"{r.get('Full Name','N/A')} ({r.get('Location','N/A')}) - Est. ${r.get('price_for_initial_filter',0)/sq_ft_used_for_pricing:.2f}/sq ft"
)

if selected_material_record:
    st.subheader(f"Details for: {selected_material_record.get('Full Name', 'N/A')}")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Source Location:** {selected_material_record.get('Location', 'N/A')}")
        st.markdown(f"**Total Available (Aggregated):** {selected_material_record.get('available_sq_ft', 0.0):.2f} sq.ft")
    with col2:
        st.markdown(f"**Unique Slabs (Aggregated):** {selected_material_record.get('slab_count', 0)}")
        st.markdown(f"**Contributing Serials:** {selected_material_record.get('serial_numbers_str', 'N/A')}")

    search_term_for_image = selected_material_record.get('Full Name', '')
    if search_term_for_image:
        google_image_search_url = f"https://www.google.com/search?q={search_term_for_image.replace(' ', '+')}+countertop&tbm=isch"
        st.markdown(f"[🔎 Google Image Search for **{search_term_for_image}**]({google_image_search_url})", unsafe_allow_html=True)

    calculated_costs = calculate_aggregated_costs(selected_material_record, sq_ft_used_for_pricing)
    additional_costs_input = st.number_input("Enter Additional Costs (e.g., Plumbing, Electrical, Sinks, Edging Upgrades):", min_value=0.0, value=0.0, step=10.0, format="%.2f")

    base_estimate_cost_val = calculated_costs.get('total_customer_facing_base_cost', 0.0)
    sub_total_before_gst_val = base_estimate_cost_val + additional_costs_input
    gst_amount_val = sub_total_before_gst_val * GST_RATE
    final_price_for_customer_val = sub_total_before_gst_val + gst_amount_val

    with st.expander("View Detailed Cost Breakdown", expanded=True):
        st.markdown(f"**Base Estimate (Material/Fabrication/Installation):** `${base_estimate_cost_val:,.2f}`")
        st.markdown(f"**Internal Billing (IB) Cost Component (Internal Use):** `${calculated_costs.get('ib_cost_component', 0.0):,.2f}`")
        st.markdown(f"**Additional Costs Entered:** `${additional_costs_input:,.2f}`")
        st.markdown(f"**Subtotal (After Additions, Before GST):** `${sub_total_before_gst_val:,.2f}`")
        st.markdown(f"**GST ({GST_RATE*100:.0f}%):** `${gst_amount_val:,.2f}`")
    st.markdown(f"### Total Estimated Price: <span style='color:green; font-size:1.5em;'>${final_price_for_customer_val:,.2f}</span> (CAD)", unsafe_allow_html=True)

    if selected_material_record.get('slab_count', 0) > 1:
        st.info("ℹ️ Note: This estimate may utilize material from multiple slabs. Variations in color, pattern, or veining between slabs are possible and considered normal for natural and engineered stone products. It is advisable to view slabs if consistency is critical.")

    st.subheader("Email Estimate")
    job_name_input = st.text_input("Job Name / Customer Name (Optional, for Email Subject):", "")

    if selected_salesperson_email:
        if st.button(f"Email Breakdown to {selected_salesperson_display} ({selected_salesperson_email})"):
            email_subject = f"CounterPro Estimate: {job_name_input if job_name_input else 'Unnamed Job'} - {selected_material_record.get('Full Name', 'N/A')} ({selected_branch})"
            email_body_html = compose_breakdown_email_body(
                job_name_input, selected_branch, selected_material_record, calculated_costs, fabrication_plant,
                selected_thickness, sq_ft_used_for_pricing,
                additional_costs_input, sub_total_before_gst_val,
                gst_amount_val, final_price_for_customer_val
            )
            send_email(subject=email_subject, body=email_body_html, receiver_email=selected_salesperson_email)
    elif selected_salesperson_display != "None":
        st.warning(f"Could not determine a valid email address for salesperson '{selected_salesperson_display}'. Email cannot be sent to salesperson.")
    else:
        st.caption("No salesperson selected, or salesperson data is unavailable for emailing.")

else:
    st.info("Please make a material selection from the dropdown above to see price details and further options.")

# --- Footer ---
st.markdown("---")
current_time_vancouver = pd.Timestamp.now(tz='America/Vancouver').strftime('%Y-%m-%d %H:%M:%S %Z')
st.caption(f"CounterPro Estimator | Branch: {selected_branch} | Data from: '{MASTER_INVENTORY_SHEET_TAB_NAME}' | Generated: {current_time_vancouver}")

