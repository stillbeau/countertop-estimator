import streamlit as st
import pandas as pd
import requests
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Custom CSS for improved mobile readability ---
st.markdown(
    """
    <style>
    /* Reduce font size in select boxes and labels */
    div[data-baseweb="select"] {
        font-size: 0.8rem;
    }
    .stLabel, label {
        font-size: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Configurations ---
MINIMUM_SQ_FT = 25            # Minimum square footage for quoting
MARKUP_FACTOR = 1.15          # 15% markup on material cost (used in material cost calculation)
INSTALL_COST_PER_SQFT = 20    # Installation cost per square foot
FABRICATION_COST_PER_SQFT = 17  # Fabrication cost per square foot
ADDITIONAL_IB_RATE = 0        # Extra rate added to material in IB calculation (per sq.ft)
GST_RATE = 0.05               # 5% GST
FINAL_MARKUP_PERCENTAGE = 0.20  # 10% markup applied to final price (this does not affect IB)

# --- Email Configuration using st.secrets ---
SMTP_SERVER = st.secrets["SMTP_SERVER"]          # e.g., "smtp-relay.brevo.com"
SMTP_PORT = int(st.secrets["SMTP_PORT"])           # e.g., 587
EMAIL_USER = st.secrets["EMAIL_USER"]              # e.g., "85e00d001@smtp-brevo.com"
EMAIL_PASSWORD = st.secrets["EMAIL_PASSWORD"]
RECIPIENT_EMAILS = st.secrets.get("RECIPIENT_EMAILS", "sambeaumont@me.com")

# --- Google Sheets URL for cost data ---
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
        # Convert numeric columns
        if "Serialized On Hand Cost" in df.columns:
            df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].replace("[\$,]", "", regex=True).astype(float)
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
        "ib_cost": ib_total_cost
    }

def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    if isinstance(RECIPIENT_EMAILS, str):
        recipient_emails = [email.strip() for email in RECIPIENT_EMAILS.split(",")]
    else:
        recipient_emails = RECIPIENT_EMAILS
    msg["To"] = ", ".join(recipient_emails)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

# --- UI: Title & Subtitle ---
st.title("Countertop Cost Estimator")
st.write("Get an accurate estimate for your custom countertop project")

# --- Load Data ---
with st.spinner("Loading data..."):
    df_inventory = load_data()
if df_inventory is None:
    st.error("Data could not be loaded.")
    st.stop()

# Debug: Show total slabs loaded
st.write(f"**Total slabs loaded:** {len(df_inventory)}")

# --- Thickness Selector ---
df_inventory["Thickness"] = df_inventory["Thickness"].astype(str).str.strip().str.lower()
thickness_options = ["1.2cm", "2cm", "3cm"]
selected_thickness = st.selectbox("Select Thickness", options=thickness_options, index=2)
df_inventory = df_inventory[df_inventory["Thickness"] == selected_thickness.lower()]

st.write(f"**Slabs after thickness filter ({selected_thickness}):** {len(df_inventory)}")
if df_inventory.empty:
    st.warning("No slabs match the selected thickness. Please adjust your filter.")
    st.stop()

# --- Map Supplier and Create Combined Identifier ---
supplier_mapping = {"VER": "Vernon", "ABB": "Abbotsford"}
df_inventory["Supplier"] = df_inventory["Location"].map(supplier_mapping).fillna(df_inventory["Location"])
if "Brand" in df_inventory.columns and "Color" in df_inventory.columns:
    df_inventory["Full Name"] = df_inventory["Brand"].astype(str) + " - " + df_inventory["Color"].astype(str)
else:
    st.error("Required columns 'Brand' or 'Color' are missing.")
    st.stop()

# --- Compute Unit Cost ---
df_inventory["unit_cost"] = df_inventory["Serialized On Hand Cost"] / df_inventory["Available Sq Ft"]

# --- Square Footage Input ---
sq_ft_input = st.number_input(
    "Enter Square Footage Needed", 
    min_value=1, 
    value=40, 
    step=1, 
    format="%d",
    help="Measure the front edge and depth (in inches), multiply them, and divide by 144."
)
if sq_ft_input < MINIMUM_SQ_FT:
    sq_ft_used = MINIMUM_SQ_FT
    st.info(f"Minimum square footage is {MINIMUM_SQ_FT} sq ft. Using {MINIMUM_SQ_FT} sq ft for pricing.")
else:
    sq_ft_used = sq_ft_input

# --- Aggregate Data by Slab (Full Name) and Supplier ---
df_agg = df_inventory.groupby(["Full Name", "Supplier"]).agg(
    available_sq_ft=("Available Sq Ft", "sum"),
    unit_cost=("unit_cost", "max"),
    slab_count=("Serial Number", "count"),
    serial_numbers=("Serial Number", lambda x: ", ".join(x.astype(str)))
).reset_index()

st.write(f"**Number of aggregated slab groups:** {len(df_agg)}")

required_material = sq_ft_used * 1.1
df_agg = df_agg[df_agg["available_sq_ft"] >= required_material]
st.write(f"**Aggregated groups after filtering by required material ({required_material} sq.ft):** {len(df_agg)}")
if df_agg.empty:
    st.error("No colors have enough total material for the selected square footage.")
    st.stop()

def compute_final_price(row):
    cost_info = calculate_aggregated_costs(row, sq_ft_used)
    total = cost_info["total_cost"]
    base_final = total + (total * GST_RATE)
    return base_final

df_agg["final_price"] = df_agg.apply(compute_final_price, axis=1)

df_valid = df_agg[df_agg["final_price"] > 0]
if df_valid.empty:
    st.error("No valid slab prices available.")
    st.stop()

min_possible_cost = int(df_valid["final_price"].min())
max_possible_cost = int(df_valid["final_price"].max())

max_job_cost = st.slider(
    "Select Maximum Job Cost ($)",
    min_value=min_possible_cost,
    max_value=max_possible_cost,
    value=max_possible_cost,
    step=100
)
st.write("Selected Maximum Job Cost: $", max_job_cost)

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

google_search_query = f"{selected_record['Full Name']} countertop"
search_url = f"https://www.google.com/search?q={google_search_query.replace(' ', '+')}"
st.markdown(f"[🔎 Google Image Search]({search_url})")

edge_profiles = ["Crescent", "Basin", "Boulder", "Volcanic", "Piedmont", "Summit", "Seacliff", "Alpine", "Treeline"]
default_index = edge_profiles.index("Seacliff") if "Seacliff" in edge_profiles else 0
selected_edge_profile = st.selectbox("Select Edge Profile", options=edge_profiles, index=default_index)

costs = calculate_aggregated_costs(selected_record, sq_ft_used)
sub_total = costs["total_cost"]
gst_amount = sub_total * GST_RATE
base_final_price = sub_total + gst_amount
final_price = base_final_price * (1 + FINAL_MARKUP_PERCENTAGE)

with st.expander("View Subtotal & GST"):
    st.markdown(f"**Subtotal (before tax):** ${sub_total:,.2f}")
    st.markdown(f"**GST (5%):** ${gst_amount:,.2f}")

st.markdown(f"### Your Total Price: :green[${final_price:,.2f}]")

if selected_record["slab_count"] > 1:
    st.info("Note: Multiple slabs are being used for this color; available square footage has been aggregated, and colors may vary.")

# --- Password Protected Breakdown ---
pwd = st.text_input("Enter password to view detailed breakdown", type="password")
if pwd == "sam":
    with st.expander("View Detailed Breakdown"):
        st.markdown(f"- **Slab:** {selected_record['Full Name']}")
        st.markdown(f"- **Supplier:** {selected_record['Supplier']}")
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

# --- Request a Quote Form ---
st.markdown("## Request a Quote")
st.write("Fill in your contact information below and we'll get in touch with you.")
with st.form("customer_form"):
    name = st.text_input("Name *")
    email = st.text_input("Email *")
    phone = st.text_input("Phone *")
    address = st.text_input("Address")
    city = st.text_input("City *")
    postal_code = st.text_input("Postal Code")
    sales_person = st.text_input("Sales Person")
    submit_request = st.form_submit_button("Submit Request")

if submit_request:
    if not name.strip() or not email.strip() or not phone.strip() or not city.strip():
        st.error("Name, Email, Phone, and City are required fields.")
    else:
        breakdown_info = f"""
Countertop Cost Estimator Details:
--------------------------------------------------
Slab: {selected_record['Full Name']}
Supplied by: {selected_record['Supplier']}
Edge Profile: {selected_edge_profile}
Thickness: {selected_thickness}
Square Footage (used): {sq_ft_used}
Slab Sq Ft (Aggregated): {selected_record['available_sq_ft']:.2f} sq.ft
Slab Count: {selected_record['slab_count']}
Serial Numbers: {selected_record['serial_numbers']}
Material & Fabrication: ${costs['material_and_fab']:,.2f}
Installation: ${costs['install_cost']:,.2f}
IB: ${costs['ib_cost']:,.2f}
Subtotal (before tax): ${sub_total:,.2f}
GST (5%): ${gst_amount:,.2f}
Final Price: ${final_price:,.2f}
--------------------------------------------------
"""
        customer_info = f"""
Customer Information:
--------------------------------------------------
Name: {name}
Email: {email}
Phone: {phone}
Address: {address}
City: {city}
Postal Code: {postal_code}
Sales Person: {sales_person}
--------------------------------------------------
"""
        email_body = f"New Countertop Request:\n\n{customer_info}\n\n{breakdown_info}"
        subject = f"New Countertop Request from {name}"
        if send_email(subject, email_body):
            st.success("Your request has been submitted successfully! We will contact you soon.")
        else:
            st.error("Failed to send email. Please try again later.")
