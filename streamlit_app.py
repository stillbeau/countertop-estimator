import streamlit as st
import pandas as pd
import gspread
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz

st.set_page_config(page_title="CounterPro", layout="centered")

st.markdown("""
    <style>
    div[data-baseweb="select"] { font-size: 0.8rem; }
    .stLabel, label { font-size: 0.8rem; }
    </style>
""", unsafe_allow_html=True)

MINIMUM_SQ_FT = 35
MARKUP_FACTOR = 1.25
INSTALL_COST_PER_SQFT = 27
FABRICATION_COST_PER_SQFT = 17
ADDITIONAL_IB_RATE = 0
GST_RATE = 0.05
SPREADSHEET_ID = "166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ"
INVENTORY_TAB = "InventoryData"
SALESPEOPLE_TAB = "Salespeople"

@st.cache_data(show_spinner=False)
def load_sheet(tab):
    try:
        creds = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(tab)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Failed to load Google Sheet tab '{tab}': {e}")
        return pd.DataFrame()

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

def send_email(subject, body, to_email):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = st.secrets["SENDER_FROM_EMAIL"]
        msg["To"] = to_email
        msg.attach(MIMEText(body, "html"))

        recipients = [to_email]
        cc = st.secrets.get("QUOTE_TRACKING_CC_EMAIL")
        if cc:
            msg["Cc"] = cc
            recipients.append(cc)

        with smtplib.SMTP(st.secrets["SMTP_SERVER"], st.secrets["SMTP_PORT"]) as server:
            server.starttls()
            server.login(st.secrets["EMAIL_USER"], st.secrets["EMAIL_PASSWORD"])
            server.sendmail(msg["From"], recipients, msg.as_string())

        st.success("â Quote emailed successfully.")
    except Exception as e:
        st.error(f"Email failed: {e}")

st.title("CounterPro")
st.write("Get an accurate estimate for your custom countertop project.")

df_inventory = load_sheet(INVENTORY_TAB)
df_salespeople = load_sheet(SALESPEOPLE_TAB)

if df_inventory.empty:
    st.stop()

df_inventory["Brand"] = df_inventory["Brand"].astype(str).str.strip()
df_inventory["Color"] = df_inventory["Color"].astype(str).str.strip()
df_inventory["Full Name"] = df_inventory["Brand"] + " - " + df_inventory["Color"]
df_inventory["Available Sq Ft"] = pd.to_numeric(df_inventory["Available Sq Ft"], errors="coerce")
df_inventory["Serialized On Hand Cost"] = pd.to_numeric(df_inventory["Serialized On Hand Cost"].astype(str).str.replace(r"[\$,]", "", regex=True), errors="coerce")
df_inventory = df_inventory[df_inventory["Available Sq Ft"].notna() & (df_inventory["Available Sq Ft"] > 0)]
df_inventory["unit_cost"] = df_inventory["Serialized On Hand Cost"] / df_inventory["Available Sq Ft"]

sq_ft_input = st.number_input("Enter Square Footage Needed", min_value=1, value=40, step=1)
sq_ft_used = max(sq_ft_input, MINIMUM_SQ_FT)

df_inventory["price"] = df_inventory.apply(lambda r: calculate_cost(r, sq_ft_used)["total_customer"], axis=1)

# --- Add slider for max job cost ---
min_price = int(df_inventory["price"].min())
max_price = int(df_inventory["price"].max())
max_budget = st.slider("Max Job Cost ($)", min_price, max_price, max_price, step=100)
df_inventory = df_inventory[df_inventory["price"] <= max_budget]

options = df_inventory.to_dict("records")
selected = st.selectbox("Choose a material", options, format_func=lambda r: f"{r['Full Name']} - ${r['price']:.2f}")

# --- Salesperson and Branch ---
selected_email = None
if not df_salespeople.empty:
    df_salespeople["Branch"] = df_salespeople["Branch"].astype(str).str.strip().str.title()
    branch_list = sorted(df_salespeople["Branch"].dropna().unique().tolist())
    selected_branch = st.selectbox("Select Branch", branch_list)
    branch_salespeople = df_salespeople[df_salespeople["Branch"] == selected_branch]
    salesperson_names = ["None"] + branch_salespeople["SalespersonName"].tolist()
    selected_salesperson = st.selectbox("Select Salesperson", salesperson_names)
    if selected_salesperson != "None":
        selected_email = branch_salespeople[branch_salespeople["SalespersonName"] == selected_salesperson]["Email"].values[0]

if selected:
    costs = calculate_cost(selected, sq_ft_used)
    st.markdown(f"**Material:** {selected['Full Name']}")
    st.markdown(f"**Source Location:** {selected.get('Location', 'N/A')}")
    
# ... (code truncated for brevity in preview)