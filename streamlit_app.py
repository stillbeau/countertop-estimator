import streamlit as st
import pandas as pd
import requests
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Email Configuration using st.secrets ---
SMTP_SERVER = st.secrets["SMTP_SERVER"]
SMTP_PORT = int(st.secrets["SMTP_PORT"])
EMAIL_USER = st.secrets["EMAIL_USER"]
EMAIL_PASSWORD = st.secrets["EMAIL_PASSWORD"]
RECIPIENT_EMAIL = st.secrets.get("RECIPIENT_EMAIL", "sambeaumont@me.com")

# --- Other Configurations ---
MARKUP_FACTOR = 1.15
INSTALL_COST_PER_SQFT = 23
FABRICATION_COST_PER_SQFT = 23
ADDITIONAL_IB_RATE = 0
GST_RATE = 0.05

# --- Google Sheets URL for cost data ---
GOOGLE_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ/export?format=csv"
)

@st.cache_data
def load_data():
    try:
        response = requests.get(GOOGLE_SHEET_URL)
        if response.status_code != 200:
            st.error("❌ Error loading the file. Check the Google Sheets URL.")
            return None
        df = pd.read_csv(io.StringIO(response.text))
        df.columns = df.columns.str.strip()
        df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].replace("[\$,]", "", regex=True).astype(float)
        df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors="coerce")
        df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors="coerce").fillna(0).astype(int)
        return df
    except Exception as e:
        st.error(f"❌ Failed to load data: {e}")
        return None

def calculate_aggregated_costs(record, sq_ft_needed):
    # record["unit_cost"] is the maximum unit cost among slabs for that color
    unit_cost = record["unit_cost"]
    material_cost_with_markup = unit_cost * MARKUP_FACTOR * sq_ft_needed
    fabrication_total = FABRICATION_COST_PER_SQFT * sq_ft_needed
    material_and_fab = material_cost_with_markup + fabrication_total
    install_cost = INSTALL_COST_PER_SQFT * sq_ft_needed
    total_cost = material_and_fab + install_cost
    ib_total_cost = (unit_cost + FABRICATION_COST_PER_SQFT + ADDITIONAL_IB_RATE) * sq_ft_needed
    return {
        "available_sq_ft": record["Available Sq Ft"],
        "material_and_fab": material_and_fab,
        "install_cost": install_cost,
        "total_cost": total_cost,
        "ib_cost": ib_total_cost
    }

def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = "Sc countertops <sam@sccountertops.ca>"
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
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

# --- Basic Filters ---
location = st.selectbox("Select Location", options=["VER", "ABB"], index=0)  # Default to VER
df_filtered = df_inventory[df_inventory["Location"] == location]
if df_filtered.empty:
    st.warning("No slabs found for the selected location.")
    st.stop()

thickness = st.selectbox("Select Thickness", options=["1.2cm", "2cm", "3cm"], index=2)  # Default to 3cm
df_filtered = df_filtered[df_filtered["Thickness"] == thickness]
if df_filtered.empty:
    st.warning("No slabs match the selected thickness. Please adjust your filter.")
    st.stop()

df_filtered = df_filtered.copy()
df_filtered["Full Name"] = df_filtered["Brand"] + " - " + df_filtered["Color"]

# --- Square Footage Input ---
sq_ft_needed = st.number_input(
    "Enter Square Footage Needed", 
    min_value=1, 
    value=20, 
    step=1, 
    format="%d",
    help="Measure front edge and depth in inches, multiply, then divide by 144."
)

# --- Group First, Then Filter by Material ---
# 1) Compute unit_cost for each slab
df_filtered["unit_cost"] = df_filtered["Serialized On Hand Cost"] / df_filtered["Available Sq Ft"]

# 2) Aggregate by color:
#    - Sum Available Sq Ft
#    - Keep the max unit cost
#    - Count slabs
df_agg = df_filtered.groupby("Full Name").agg({
    "Available Sq Ft": "sum",
    "unit_cost": "max",
    "Serial Number": "count"
}).reset_index()
df_agg.rename(columns={"Serial Number": "slab_count"}, inplace=True)

# 3) Filter aggregated data by required material (≥ sq_ft_needed * 1.2)
required_material = sq_ft_needed * 1.2
df_agg = df_agg[df_agg["Available Sq Ft"] >= required_material]
if df_agg.empty:
    st.error("No colors have enough total material for the selected square footage.")
    st.stop()

# 4) Compute final price for each color to filter by cost
def compute_final_price(row):
    cost_info = calculate_aggregated_costs(row, sq_ft_needed)
    total = cost_info["total_cost"]
    final = total + total * GST_RATE
    return final

df_agg["final_price"] = df_agg.apply(lambda row: compute_final_price(row), axis=1)

# --- Maximum Job Cost Slider ---
max_possible_cost = int(df_agg["final_price"].max())
max_job_cost = st.slider("Select Maximum Job Cost ($)", min_value=0, max_value=max_possible_cost, value=max_possible_cost//2)
st.write("Selected Maximum Job Cost: $", max_job_cost)

df_agg_filtered = df_agg[df_agg["final_price"] <= max_job_cost]
if df_agg_filtered.empty:
    st.error("No colors available within the selected cost range.")
    st.stop()

# --- Color Selection from Aggregated Options ---
selected_full_name = st.selectbox("Select Color", options=df_agg_filtered["Full Name"].unique())

# --- Edge Profile and Links ---
col1, col2 = st.columns([2,1])
with col1:
    selected_edge_profile = st.selectbox("Select Edge Profile", ["Bullnose", "Eased", "Beveled", "Ogee", "Waterfall"])
with col2:
    google_search_query = f"{selected_full_name} countertop"
    search_url = f"https://www.google.com/search?q={google_search_query.replace(' ', '+')}"
    st.markdown(f"[🔎 Google Image Search]({search_url})")

st.markdown("[Floform Edge Profiles](https://floform.com/countertops/edge-profiles/)")

# Retrieve the aggregated record for the selected color
selected_record = df_agg_filtered[df_agg_filtered["Full Name"] == selected_full_name]
if selected_record.empty:
    st.error("Selected color not found. Please choose a different option.")
    st.stop()
selected_record = selected_record.iloc[0]

# Calculate costs for the aggregated record
costs = calculate_aggregated_costs(selected_record, sq_ft_needed)
sub_total = costs["total_cost"]
gst_amount = sub_total * GST_RATE
final_price = sub_total + gst_amount

st.markdown(f"### Your Total Price: :green[${final_price:,.2f}]")
with st.expander("View Subtotal & GST"):
    st.markdown(f"**Subtotal (before tax):** ${sub_total:,.2f}")
    st.markdown(f"**GST (5%):** ${gst_amount:,.2f}")

# Disclaimer if multiple slabs used
if selected_record["slab_count"] > 1:
    st.info("Note: Multiple slabs are being used for this color; available square footage has been aggregated, and colors may vary.")

# --- Request a Quote Form ---
st.markdown("## Request a Quote")
st.write("Fill in your contact information below and we'll get in touch with you.")
with st.form("customer_form"):
    name = st.text_input("Name *")
    email = st.text_input("Email *")
    phone = st.text_input("Phone *")
    address = st.text_area("Address")
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
Edge Profile: {selected_edge_profile}
Square Footage: {sq_ft_needed}
Slab Sq Ft: {selected_record['Available Sq Ft']:.2f} sq.ft
Slab Count: {selected_record['slab_count']}
Material & Fab: ${costs['material_and_fab']:,.2f}
Installation: ${costs['install_cost']:,.2f}
IB: ${costs['ib_cost']:,.2f}
Subtotal (before tax): ${sub_total:,.2f}
GST (5%): ${gst_amount:,.2f}
Final Price: ${final_price:,.2f}
--------------------------------------------------
"""
        disclaimer = ""
        if selected_record["slab_count"] > 1:
            disclaimer = "Multiple slabs are being used for this color; color may vary.\n"

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

        email_body = f"New Countertop Request:\n\n{customer_info}\n\n{breakdown_info}\n{disclaimer}"
        subject = f"New Countertop Request from {name}"
        if send_email(subject, email_body):
            st.success("Your request has been submitted successfully! We will contact you soon.")
        else:
            st.error("Failed to send email. Please try again later.")