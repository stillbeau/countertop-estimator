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

# --- Email Configuration using st.secrets ---
SMTP_SERVER = st.secrets["SMTP_SERVER"]
SMTP_PORT = int(st.secrets["SMTP_PORT"])
EMAIL_USER = st.secrets["EMAIL_USER"]
EMAIL_PASSWORD = st.secrets["EMAIL_PASSWORD"]
RECIPIENT_EMAIL = st.secrets.get("RECIPIENT_EMAIL", "sambeaumont@me.com")

# --- Google Sheets URL for cost data ---
GOOGLE_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ/export?format=csv"
)

@st.cache_data
def load_data():
    try:
        response = requests.get(GOOGLE_SHEET_URL)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        df = pd.read_csv(io.StringIO(response.text))
        df.columns = df.columns.str.strip()
        df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].replace("[\<span class="math-inline">,\]", "", regex\=True\)\.astype\(float\)
df\["Available Sq Ft"\] \= pd\.to\_numeric\(df\["Available Sq Ft"\], errors\="coerce"\)
df\["Serial Number"\] \= pd\.to\_numeric\(df\["Serial Number"\], errors\="coerce"\)\.fillna\(0\)\.astype\(int\)
return df
except requests\.exceptions\.RequestException as e\:
st\.error\(f"❌ Error loading data\: \{e\}"\)
return None
except pd\.errors\.ParserError as e\:
st\.error\(f"❌ Error parsing CSV\: \{e\}"\)
return None
except Exception as e\:
st\.error\(f"❌ An unexpected error occurred\: \{e\}"\)
return None
def calculate\_material\_cost\(record, sq\_ft\_used\)\:
unit\_cost \= record\["unit\_cost"\]
return unit\_cost \* MARKUP\_FACTOR \* sq\_ft\_used
def calculate\_fabrication\_cost\(sq\_ft\_used\)\:
return FABRICATION\_COST\_PER\_SQFT \* sq\_ft\_used
def calculate\_installation\_cost\(sq\_ft\_used\)\:
return INSTALL\_COST\_PER\_SQFT \* sq\_ft\_used
def calculate\_installation\_base\_cost\(record, sq\_ft\_used\)\:
unit\_cost \= record\["unit\_cost"\]
return \(unit\_cost \+ FABRICATION\_COST\_PER\_SQFT \+ ADDITIONAL\_IB\_RATE\) \* sq\_ft\_used
def calculate\_aggregated\_costs\(record, sq\_ft\_used\)\:
material\_cost \= calculate\_material\_cost\(record, sq\_ft\_used\)
fabrication\_cost \= calculate\_fabrication\_cost\(sq\_ft\_used\)
installation\_cost \= calculate\_installation\_cost\(sq\_ft\_used\)
installation\_base\_cost \= calculate\_installation\_base\_cost\(record, sq\_ft\_used\)
total\_cost \= material\_cost \+ fabrication\_cost \+ installation\_cost
return \{
"available\_sq\_ft"\: record\["available\_sq\_ft"\],
"material\_and\_fab"\: material\_cost \+ fabrication\_cost,
"install\_cost"\: installation\_cost,
"total\_cost"\: total\_cost,
"ib\_cost"\: installation\_base\_cost,
\}
def send\_email\(subject, body\)\:
msg \= MIMEMultipart\(\)
msg\["From"\] \= "Sc countertops <sam@sccountertops\.ca\>"
<0\>msg\["To"\] \= RECIPIENT\_EMAIL
msg\["Subject"\] \= subject
msg\.attach\(MIMEText\(body, "plain"\)\)
<1\>try\:
server \= smtplib\.SMTP\(SMTP\_SERVER, SMTP\_PORT\)
server\.starttls\(\)
server\.login\(EMAIL\_USER,</0\> EMAIL\_PASSWORD\)
server\.send\_message\(msg\)
server\.quit\(\)</1\>
return True
except smtplib\.SMTPException as e\:
st\.error\(f"❌ Email sending error\: \{e\}"\)
return False
except Exception as e\:
st\.error\(f"❌ An unexpected error occurred during email sending\: \{e\}"\)
return False
\# \-\-\- UI \-\-\-
st\.title\("Countertop Cost Estimator"\)
st\.write\("Get an accurate estimate for your custom countertop project"\)
\# \-\-\- Load Data with Progress Bar \-\-\-
with st\.spinner\("Loading data\.\.\."\)\:
df\_inventory \= load\_data\(\)
if df\_inventory is None\:
st\.error\("Data could not be loaded\."\)
st\.stop\(\)
\# \-\-\- Sidebar Filters \-\-\-
with st\.sidebar\:
thickness \= st\.selectbox\("Select Thickness", options\=\["1\.2cm", "2cm", "3cm"\], index\=2\)
sq\_ft\_input \= st\.number\_input\(
"Enter Square Footage Needed",
min\_value\=1,
value\=20,
step\=1,
format\="%d",
help\="Measure the front edge and depth \(in inches\), multiply them, and divide by 144\.",
\)
max\_job\_cost \= st\.slider\(
"Select Maximum Job Cost \(</span>)",
        min_value=0,  # Initialize to 0 for flexibility
        max_value=df_inventory["Serialized On Hand Cost"].max() * 2 if not df_inventory.empty else 100000, # Provide a default max value
        value=df_inventory["Serialized On Hand Cost"].max() * 2 if not df_inventory.empty else 100000,
        step=100
    )

# --- Data Processing ---
df_inventory = df_inventory[df_inventory["Thickness"] == thickness]
if df_inventory.empty:
    st.error("No slabs match the selected thickness. Please adjust your filter.")
    st.stop()

supplier_mapping = {"VER": "Vernon", "ABB": "Abbotsford"}
df_inventory["Supplier"] = df_inventory["Location"].map(supplier_mapping)
df_inventory["Full Name"] = df_inventory["Brand"] + " - " + df_inventory["Color"]
df_inventory["unit_cost"] = df_inventory["Serialized On Hand Cost"] / df_inventory["Available Sq Ft"]

if sq_ft_input < MINIMUM_SQ_FT:
    sq_ft_used = MINIMUM_SQ_FT
    st.info(f"Minimum square footage is {MINIMUM_SQ_FT} sq ft. Using {MINIMUM_SQ_FT} sq ft for pricing.")
else:
    sq_ft_used = sq_ft_input

df_agg = df_inventory.groupby(["Full Name", "Supplier"]).agg(
    available_sq_ft=("Available Sq Ft", "sum"),
    unit_cost=("unit_cost", "max"),
    slab_count=("Serial Number", "count"),
    serial_numbers=("Serial Number", lambda x: ", ".join(x.astype(str))),
).reset_index()

required_material = sq_ft_used * 1.2
df_agg = df_agg[df_agg["available_sq_ft"] >= required_material]
if df_agg.empty:
    st.error("No colors have enough total material for the selected square footage.")
    st.stop()

def compute_final_price(row):
    cost_info = calculate_aggregated_costs(row, sq_ft_used)
    total = cost_info["total_cost"]
    final = total + (total * GST_RATE)
    return final

df_agg["final_price"] = df_agg.apply(compute_final_price, axis=1)

df_agg_filtered = df_agg[df_agg["final_price"] <= max_job_cost]
if df_agg_filtered.empty:
    st.error("No colors available within the selected cost range.")
    st.stop()

# --- Tabs ---
tabs = ["Slab Selection", "Cost Breakdown", "Request a Quote"]
selected_tab = st.tabs(tabs)

if selected_tab == "Slab Selection":
    st.subheader("Select a Slab")
    records = df_
