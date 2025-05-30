import streamlit as st
import pandas as pd
import gspread
import json
import smtplib
import pytz
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Set Page Config FIRST ---
st.set_page_config(
    page_title="CounterPro Estimator",
    page_icon="🧱",
    layout="centered",
    initial_sidebar_state="auto"
)

# --- Styling ---
st.markdown("""
    <style>
    div[data-baseweb="select"] { font-size: 0.8rem; }
    .stLabel, label { font-size: 0.8rem; }
    </style>
""", unsafe_allow_html=True)

# --- Configs ---
MINIMUM_SQ_FT = 35
MARKUP_FACTOR = 1.25
INSTALL_COST_PER_SQFT = 27
FABRICATION_COST_PER_SQFT = 17
ADDITIONAL_IB_RATE = 0
GST_RATE = 0.05
SPREADSHEET_ID = "166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ"
INVENTORY_TAB = "InventoryData"
SALESPEOPLE_TAB = "Salespeople"

# --- Load Google Sheet Data ---
@st.cache_data(show_spinner=False)
def load_sheet(tab):
    try:
        creds = json.loads(st.secrets["gcp_service_account"])
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(tab)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Failed to load Google Sheet tab '{tab}': {e}")
        return pd.DataFrame()

# --- Cost Calculation ---
def calculate_cost(record, sq_ft):
    unit_cost = record.get("unit_cost", 0)
    material_cost = unit_cost * MARKUP_FACTOR * sq_ft
    fabrication = FABRICATION_COST_PER_SQFT * sq_ft
    install = INSTALL_COST_PER_SQFT * sq_ft
    ib_cost = (unit_cost + FABRICATION_COST_PER_SQFT + ADDITIONAL_IB_RATE) * sq_ft
    return {
        "material_and_fab": material_cost + fabrication,
        "install": install,
        "ib_cost": ib_cost,
        "total_customer": material_cost + fabrication + install
    }

# --- Email Breakdown ---
def send_email(subject, body, to_email):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = st.secrets["SENDER_FROM_EMAIL"]
        msg["To"] = to_email
        msg.attach(MIMEText(body, "html"))

        recipients = [to_email]
        if "QUOTE_TRACKING_CC_EMAIL" in st.secrets:
            msg["Cc"] = st.secrets["QUOTE_TRACKING_CC_EMAIL"]
            recipients.append(st.secrets["QUOTE_TRACKING_CC_EMAIL"])

        with smtplib.SMTP(st.secrets["SMTP_SERVER"], st.secrets["SMTP_PORT"]) as server:
            server.starttls()
            server.login(st.secrets["EMAIL_USER"], st.secrets["EMAIL_PASSWORD"])
            server.sendmail(msg["From"], recipients, msg.as_string())

        st.success("✅ Quote emailed successfully.")
    except Exception as e:
        st.error(f"Email send failed: {e}")

# --- App UI ---
st.title("CounterPro Estimator")
st.write("Generate accurate countertop pricing based on inventory and branch settings.")

inventory = load_sheet(INVENTORY_TAB)
salespeople = load_sheet(SALESPEOPLE_TAB)

if inventory.empty:
    st.stop()

# --- Branch & Salesperson Selection ---
branches = ["Vernon", "Victoria", "Vancouver", "Calgary", "Edmonton", "Saskatoon", "Winnipeg"]
branch = st.selectbox("Branch", branches)

salesperson_email = None
salesperson_list = salespeople[salespeople["Branch"].str.lower() == branch.lower()]
if not salesperson_list.empty:
    names = ["None"] + salesperson_list["SalespersonName"].tolist()
    selection = st.selectbox("Salesperson (for emailing)", names)
    if selection != "None":
        row = salesperson_list[salesperson_list["SalespersonName"] == selection]
        if not row.empty:
            salesperson_email = row.iloc[0]["Email"]

# --- Material Filtering ---
inventory = inventory[inventory["Location"].isin(["Vernon", "Abbotsford", "Edmonton", "Saskatoon"])]
inventory["Full Name"] = inventory["Brand"] + " - " + inventory["Color"]
inventory["unit_cost"] = inventory["Serialized On Hand Cost"] / inventory["Available Sq Ft"]

thicknesses = inventory["Thickness"].dropna().unique().tolist()
selected_thickness = st.selectbox("Select Thickness", sorted(thicknesses))
inventory = inventory[inventory["Thickness"] == selected_thickness]

sq_ft = st.number_input("Square Footage", value=40, min_value=1)
sq_ft_used = max(sq_ft, MINIMUM_SQ_FT)

# --- Material Selection ---
inventory = inventory[inventory["Available Sq Ft"] >= sq_ft_used * 1.1]
agg = inventory.groupby(["Full Name", "Location"]).agg({
    "Available Sq Ft": "sum",
    "unit_cost": "mean"
}).reset_index()

if agg.empty:
    st.warning("No slabs available for required square footage.")
    st.stop()

agg["Estimated Price"] = agg["unit_cost"].apply(lambda u: (u * MARKUP_FACTOR + FABRICATION_COST_PER_SQFT + INSTALL_COST_PER_SQFT) * sq_ft_used)
max_price = st.slider("Max Budget", int(agg["Estimated Price"].min()), int(agg["Estimated Price"].max()), int(agg["Estimated Price"].max()))
agg = agg[agg["Estimated Price"] <= max_price]

selected_row = st.selectbox("Select Material", agg.to_dict("records"), format_func=lambda r: f"{r['Full Name']} ({r['Location']}) - ${r['Estimated Price']:.2f}")

if selected_row:
    st.markdown(f"**Selected Slab:** {selected_row['Full Name']} from {selected_row['Location']}")
    costs = calculate_cost(selected_row, sq_ft_used)

    add_cost = st.number_input("Additional Costs (sinks, plumbing)", value=0.0)
    subtotal = costs["total_customer"] + add_cost
    gst = subtotal * GST_RATE
    total = subtotal + gst

    st.markdown(f"### Final Quote: ${total:,.2f}")
    st.markdown(f"- Material & Fab: ${costs['material_and_fab']:,.2f}")
    st.markdown(f"- Install: ${costs['install']:,.2f}")
    st.markdown(f"- Add-ons: ${add_cost:,.2f}")
    st.markdown(f"- GST: ${gst:,.2f}")

    job_name = st.text_input("Job Name (optional)")

    if salesperson_email and st.button("Email Quote"):
        body = f"""
        <h2>Quote for {job_name or 'Unnamed Job'}</h2>
        <p><strong>Material:</strong> {selected_row['Full Name']}<br>
        <strong>Location:</strong> {selected_row['Location']}<br>
        <strong>Square Feet:</strong> {sq_ft_used} sq.ft<br>
        <strong>Total Price:</strong> ${total:,.2f}</p>
        """
        subject = f"CounterPro Quote - {job_name or 'Unnamed Job'}"
        send_email(subject, body, salesperson_email)