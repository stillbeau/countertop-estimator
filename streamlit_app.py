# Import necessary libraries
import streamlit as st
import pandas as pd
import requests
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Configurations ---
MINIMUM_SQ_FT = 25
MARKUP_FACTOR = 1.25
INSTALL_COST_PER_SQFT = 23
FABRICATION_COST_PER_SQFT = 23
ADDITIONAL_IB_RATE = 0
GST_RATE = 0.05
FINAL_MARKUP_PERCENTAGE = 0.10

# --- Email Configuration ---
SMTP_SERVER = st.secrets["SMTP_SERVER"]
SMTP_PORT = int(st.secrets["SMTP_PORT"])
EMAIL_USER = st.secrets["EMAIL_USER"]
EMAIL_PASSWORD = st.secrets["EMAIL_PASSWORD"]
RECIPIENT_EMAILS = st.secrets.get("RECIPIENT_EMAILS", "sbeaumont@floform.com, athomas@floform.com")

# --- Google Sheets URL for cost data ---
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ/export?format=csv"

# --- Caching the Data Loading Process ---
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

# --- Processing the Inventory Data ---
@st.cache_data
def process_inventory(df):
    supplier_mapping = {"VER": "Vernon", "ABB": "Abbotsford"}
    df["Supplier"] = df["Location"].map(supplier_mapping)
    df["Full Name"] = df["Brand"] + " - " + df["Color"]
    df["unit_cost"] = df["Serialized On Hand Cost"] / df["Available Sq Ft"]
    return df

# --- Cost Calculation Function ---
def calculate_aggregated_costs(record, sq_ft_used):
    unit_cost = record["unit_cost"]
    material_cost_with_markup = unit_cost * MARKUP_FACTOR * sq_ft_used
    fabrication_total = FABRICATION_COST_PER_SQFT * sq_ft_used
    install_cost = INSTALL_COST_PER_SQFT * sq_ft_used
    total_cost = material_cost_with_markup + fabrication_total + install_cost
    ib_total_cost = (unit_cost + FABRICATION_COST_PER_SQFT + ADDITIONAL_IB_RATE) * sq_ft_used
    return {
        "available_sq_ft": record["available_sq_ft"],
        "material_and_fab": material_cost_with_markup + fabrication_total,
        "install_cost": install_cost,
        "total_cost": total_cost,
        "ib_cost": ib_total_cost
    }

# --- Function to Send Email with HTML Formatting ---
def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = f"SC Countertops <{EMAIL_USER}>"
    recipient_emails = [email.strip() for email in RECIPIENT_EMAILS.split(",")]
    msg["To"] = ", ".join(recipient_emails)
    msg["Subject"] = subject

    html_body = f"""
    <html>
    <body>
        <h2>New Countertop Quote Request</h2>
        <pre>{body}</pre>
    </body>
    </html>
    """
    msg.attach(MIMEText(html_body, "html"))

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

# --- Streamlit UI ---
st.title("Countertop Cost Estimator")
st.write("Get an accurate estimate for your custom countertop project")

# --- Load Data ---
with st.spinner("Loading data..."):
    df_inventory = load_data()
if df_inventory is None:
    st.stop()
df_inventory = process_inventory(df_inventory)

# --- Thickness Selector ---
thickness = st.selectbox("Select Thickness", options=["1.2cm", "2cm", "3cm"], index=2)
df_inventory = df_inventory[df_inventory["Thickness"] == thickness]
if df_inventory.empty:
    st.warning("No slabs match the selected thickness. Please adjust your filter.")
    st.stop()

# --- Square Footage Input ---
sq_ft_input = st.number_input(
    "Enter Square Footage Needed", min_value=1, value=40, step=1, format="%d"
)
sq_ft_used = max(sq_ft_input, MINIMUM_SQ_FT)

# --- Aggregate Data ---
df_agg = df_inventory.groupby(["Full Name", "Supplier"]).agg(
    available_sq_ft=("Available Sq Ft", "sum"),
    unit_cost=("unit_cost", "max"),
    slab_count=("Serial Number", "count"),
    serial_numbers=("Serial Number", lambda x: ", ".join(x.astype(str)))
).reset_index()

# --- Filter by Availability ---
required_material = sq_ft_used * 1.2
df_agg = df_agg[df_agg["available_sq_ft"] >= required_material]

if df_agg.empty:
    st.error("No colors have enough total material for the selected square footage.")
    st.stop()

df_agg["final_price"] = df_agg.apply(lambda row: calculate_aggregated_costs(row, sq_ft_used)["total_cost"] * (1 + GST_RATE), axis=1)

# --- Cost Filtering ---
min_cost, max_cost = int(df_agg["final_price"].min()), int(df_agg["final_price"].max())
max_job_cost = st.slider("Select Maximum Job Cost ($)", min_cost, max_cost, max_cost, step=100)
df_agg_filtered = df_agg[df_agg["final_price"] <= max_job_cost]

if df_agg_filtered.empty:
    st.error("No colors available within the selected cost range.")
    st.stop()

# --- Display Options in Table ---
st.write("Available Countertop Options:")
st.dataframe(df_agg_filtered[["Full Name", "Supplier", "available_sq_ft", "final_price"]])

# --- Selection ---
records = df_agg_filtered.to_dict("records")
selected_record = st.selectbox(
    "Select Color",
    options=records,
    format_func=lambda record: f"{record['Full Name']} - (${record['final_price'] / sq_ft_used:.2f}/sq ft)"
)

# --- Price Breakdown ---
costs = calculate_aggregated_costs(selected_record, sq_ft_used)
final_price = costs["total_cost"] * (1 + FINAL_MARKUP_PERCENTAGE)
col1, col2 = st.columns(2)
col1.metric("Subtotal", f"${costs['total_cost']:,.2f}")
col2.metric("GST (5%)", f"${costs['total_cost'] * GST_RATE:,.2f}")
st.metric("Final Price", f"${final_price:,.2f}")

# --- Request Form ---
st.markdown("## Request a Quote")
with st.form("customer_form"):
    name = st.text_input("Name *")
    email = st.text_input("Email *")
    phone = st.text_input("Phone *")
    city = st.text_input("City *")
    submit_request = st.form_submit_button("Submit Request")

if submit_request:
    if not name or not email or not phone or not city:
        st.error("Name, Email, Phone, and City are required fields.")
    else:
        email_body = f"Customer: {name}\nEmail: {email}\nPhone: {phone}\nCity: {city}\n\nSelected Countertop: {selected_record['Full Name']}\nFinal Price: ${final_price:,.2f}"
        if send_email(f"New Quote Request from {name}", email_body):
            st.success("Request submitted successfully!")