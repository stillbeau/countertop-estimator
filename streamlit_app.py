import streamlit as st
import pandas as pd
import gspread
import json
import smtplib
import pytz
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Page config & CSS ---
st.set_page_config(page_title="CounterPro", layout="centered")
st.markdown(
    """
    <style>
    /* Smaller font for selectboxes/labels */
    div[data-baseweb="select"] { font-size: 0.8rem; }
    .stLabel, label { font-size: 0.8rem; }
    /* Slightly larger headings */
    h1 { font-size: 2rem; }
    h2 { font-size: 1.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Constants ---
MINIMUM_SQ_FT             = 35
MARKUP_FACTOR             = 1.25
INSTALL_COST_PER_SQFT     = 27
FABRICATION_COST_PER_SQFT = 17
ADDITIONAL_IB_RATE        = 0
GST_RATE                  = 0.05

# ————————————————————————————————————————————————————————————
# Use your published‐to‐CSV PIO sheet URL here:
INVENTORY_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vRzPf_DEc7ojcjqCsk_5O9HtSFWy7aj2Fi_bPjUh6HVaN38coQSINDps0RGrpiM9ox58izhsNkzD51j/"
    "pub?output=csv"
)

# We still load “Salespeople” from Google Sheets via gspread:
SPREADSHEET_ID   = "166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ"
SALESPEOPLE_TAB  = "Salespeople"
# ————————————————————————————————————————————————————————————

# --- Load Salespeople sheet via gspread ---
@st.cache_data(show_spinner=False)
def load_salespeople_sheet(tab_name: str) -> pd.DataFrame:
    try:
        raw = st.secrets["gcp_service_account"]
        creds = json.loads(raw) if isinstance(raw, str) else raw
        gc = gspread.service_account_from_dict(creds)
        ws = gc.open_by_key(SPREADSHEET_ID).worksheet(tab_name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"❌ Could not load Google Sheet tab '{tab_name}': {e}")
        return pd.DataFrame()


# --- Cost‐calculation helper ---
def calculate_cost(rec: dict, sq: float) -> dict:
    uc  = rec.get("unit_cost", 0) or 0
    mat = uc * MARKUP_FACTOR * sq
    fab = FABRICATION_COST_PER_SQFT * sq
    ins = INSTALL_COST_PER_SQFT * sq
    ib  = (uc + FABRICATION_COST_PER_SQFT + ADDITIONAL_IB_RATE) * sq
    return {
        "base_material_and_fab_component": mat + fab,
        "base_install_cost_component":     ins,
        "ib_cost_component":               ib,
        "total_customer_facing_base_cost": mat + fab + ins
    }


# --- Compose HTML email body ---
def compose_breakdown_email_body(
    job_name: str,
    selected_branch: str,
    selected_salesperson: str,
    rec: dict,
    costs: dict,
    fab_plant: str,
    selected_thickness: str,
    sq_ft_used: float,
    additional_costs: float,
    subtotal: float,
    gst_amount: float,
    final_total: float
) -> str:
    def fmt(v): 
        return f"${v:,.2f}"
    tz  = pytz.timezone("America/Vancouver")
    now = pd.Timestamp.now(tz=tz).strftime("%Y-%m-%d %H:%M:%S %Z")
    job = job_name or "Unnamed Job"

    return f"""<html>
<head><style>
  body {{ font-family: Arial, sans-serif; color: #333; }}
  .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
  h1 {{ color: #0056b3; margin-bottom: 4px; }}
  p.meta {{ margin: 0; font-size: 0.9rem; color: #555; }}
  h2 {{ color: #0056b3; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-top: 20px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
  th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
  th {{ background: #f0f0f0; }}
  .grand-total-row td {{ font-weight: bold; background: #c9e0ff; font-size: 1rem; }}
  .footer {{ font-size: 10px; color: #666; text-align: center; margin-top: 20px; }}
</style></head>
<body>
  <div class="container">
    <h1>CounterPro Estimate</h1>
    <p class="meta">
      <strong>Branch:</strong> {selected_branch} &nbsp;&nbsp;
      <strong>Salesperson:</strong> {selected_salesperson}
    </p>

    <h2>Project &amp; Material Overview</h2>
    <table>
      <tr><th>Detail</th><th>Value</th></tr>
      <tr><td>Job Name:</td><td>{job}</td></tr>
      <tr><td>Slab Selected:</td><td>{rec.get("Full Name", "N/A")}</td></tr>
      <tr><td>Material Source:</td><td>{rec.get("Location", "N/A")}</td></tr>
      <tr><td>Fabrication Plant:</td><td>{fab_plant}</td></tr>
      <tr><td>Thickness:</td><td>{selected_thickness}</td></tr>
      <tr><td>Sq Ft (for pricing):</td><td>{sq_ft_used} sq.ft</td></tr>
      <tr><td>Slab Sq Ft (Total):</td><td>{rec.get("available_sq_ft", 0):.2f} sq.ft</td></tr>
      <tr><td>Unique Slabs:</td><td>{rec.get("slab_count", 0)}</td></tr>
      <tr><td>Serial Numbers:</td><td>{rec.get("serial_numbers", "N/A")}</td></tr>
    </table>

    <h2>Cost Components</h2>
    <table>
      <tr><th>Component</th><th>Amount</th></tr>
      <tr><td>Material &amp; Fabrication:</td><td>{fmt(costs["base_material_and_fab_component"])}</td></tr>
      <tr><td>Installation:</td><td>{fmt(costs["base_install_cost_component"])}</td></tr>
      <tr><td>IB Cost (Internal):</td><td>{fmt(costs["ib_cost_component"])}</td></tr>
    </table>

    <h2>Totals</h2>
    <table>
      <tr><th>Description</th><th>Amount</th></tr>
      <tr><td>Base Estimate:</td><td>{fmt(costs["total_customer_facing_base_cost"])}</td></tr>
      <tr><td>Additional Costs (sinks, tile, plumbing):</td><td>{fmt(additional_costs)}</td></tr>
      <tr><td>Subtotal:</td><td>{fmt(subtotal)}</td></tr>
      <tr><td>GST (5%):</td><td>{fmt(gst_amount)}</td></tr>
      <tr class="grand-total-row"><td>Final Total:</td><td>{fmt(final_total)}</td></tr>
    </table>

    <div class="footer">Generated by CounterPro on {now}</div>
  </div>
</body>
</html>"""


# --- Send email helper ---
def send_email(subject: str, body: str, to_email: str):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = st.secrets["SENDER_FROM_EMAIL"]
        msg["To"]      = to_email
        msg.attach(MIMEText(body, "html"))

        recipients = [to_email]
        cc = st.secrets.get("QUOTE_TRACKING_CC_EMAIL")
        if cc:
            msg["Cc"] = cc
            recipients.append(cc)

        with smtplib.SMTP(
            st.secrets["SMTP_SERVER"],
            st.secrets["SMTP_PORT"]
        ) as server:
            server.starttls()
            server.login(
                st.secrets["EMAIL_USER"],
                st.secrets["EMAIL_PASSWORD"]
            )
            server.sendmail(msg["From"], recipients, msg.as_string())

        st.success("✅ Quote emailed successfully.")
    except Exception as e:
        st.error(f"Email failed: {e}")


def get_fab_plant(branch: str) -> str:
    """If branch is one of (Vernon, Victoria, Vancouver), return 'Abbotsford'; else 'Saskatoon'."""
    return "Abbotsford" if branch in ["Vernon", "Victoria", "Vancouver"] else "Saskatoon"


# --- MAIN APP UI ---
st.title("CounterPro")

# ── 1) Branch & Salesperson (side by side) ───────────────────────────────────────
df_sp = load_salespeople_sheet(SALESPEOPLE_TAB)
selected_email = None

if not df_sp.empty:
    df_sp["Branch"] = df_sp["Branch"].astype(str).str.strip().str.title()
    branch_list = sorted(df_sp["Branch"].dropna().unique())

    col1, col2 = st.columns(2)
    with col1:
        selected_branch = st.selectbox("Select Branch", branch_list)
    with col2:
        sales_for_branch = df_sp[df_sp["Branch"] == selected_branch]
        sp_options = ["None"] + sales_for_branch["SalespersonName"].tolist()
        selected_salesperson = st.selectbox("Select Salesperson", sp_options)

    if selected_salesperson != "None":
        selected_email = sales_for_branch.loc[
            sales_for_branch["SalespersonName"] == selected_salesperson, "Email"
        ].iat[0]
else:
    st.warning("⚠️ No salespeople data loaded.")
    selected_branch = ""
    selected_salesperson = ""

# ── 2) Load Inventory from PIO CSV ──────────────────────────────────────────────
try:
    df_inv = pd.read_csv(INVENTORY_CSV_URL)
    df_inv.columns = df_inv.columns.str.strip()
except Exception as e:
    st.error(f"❌ Could not fetch inventory CSV: {e}")
    st.stop()

if df_inv.empty:
    st.error("❌ Loaded inventory CSV is empty.")
    st.stop()

# ── 3) FILTER BY BRANCH→SOURCE LOCATIONS ────────────────────────────────────────
branch_to_material_sources = {
    "Vernon":    ["Vernon", "Abbotsford"],
    "Victoria":  ["Vernon", "Abbotsford"],
    "Vancouver": ["Vernon", "Abbotsford"],
    "Calgary":   ["Edmonton", "Saskatoon"],
    "Edmonton":  ["Edmonton", "Saskatoon"],
    "Saskatoon": ["Edmonton", "Saskatoon"],
    "Winnipeg":  ["Edmonton", "Saskatoon"],
}

allowed_sources = branch_to_material_sources.get(selected_branch, [])
if allowed_sources:
    df_inv = df_inv[df_inv["Location"].isin(allowed_sources)]
else:
    st.warning(f"No material‐source mapping for branch '{selected_branch}'. Showing all inventory.")

# ── 4) Normalize “Available Qty” → “Available Sq Ft” ────────────────────────────
if "Available Qty" in df_inv.columns:
    df_inv["Available Sq Ft"] = pd.to_numeric(df_inv["Available Qty"], errors="coerce")
elif "Available Sq Ft" in df_inv.columns:
    df_inv["Available Sq Ft"] = pd.to_numeric(df_inv["Available Sq Ft"], errors="coerce")
else:
    st.error(
        "❌ Could not find either 'Available Qty' or 'Available Sq Ft' in the inventory CSV.\n"
        f"Columns found: {df_inv.columns.tolist()}"
    )
    st.stop()

# ── 5) Normalize “Serialized Unit Cost” → per-sq.ft `unit_cost` ─────────────────
if "Serialized Unit Cost" in df_inv.columns:
    df_inv["unit_cost"] = pd.to_numeric(
        df_inv["Serialized Unit Cost"]
            .astype(str)
            .str.replace(r"[\$,]", "", regex=True),
        errors="coerce"
    )
elif "Serialized On Hand Cost" in df_inv.columns:
    df_inv["SerialOnHandCost"] = pd.to_numeric(
        df_inv["Serialized On Hand Cost"]
            .astype(str)
            .str.replace(r"[\$,]", "", regex=True),
        errors="coerce"
    )
    df_inv["unit_cost"] = df_inv["SerialOnHandCost"] / df_inv["Available Sq Ft"].replace(0, pd.NA)
else:
    st.error(
        "❌ Could not find 'Serialized Unit Cost' or 'Serialized On Hand Cost' in the inventory CSV.\n"
        f"Columns found: {df_inv.columns.tolist()}"
    )
    st.stop()

df_inv = df_inv[
    df_inv["Available Sq Ft"].notna() & (df_inv["Available Sq Ft"] > 0) &
    df_inv["unit_cost"].notna() & (df_inv["unit_cost"] > 0)
]

# ── 6) Build “Full Name” column ─────────────────────────────────────────────────
df_inv["Brand"] = df_inv["Brand"].astype(str).str.strip()
df_inv["Color"] = df_inv["Color"].astype(str).str.strip()
df_inv["Full Name"] = df_inv["Brand"] + " - " + df_inv["Color"]

# ── 7) Thickness selector ──────────────────────────────────────────────────────
df_inv["Thickness"] = df_inv["Thickness"].astype(str).str.strip().str.lower()
th_list = sorted(df_inv["Thickness"].unique())
selected_thickness = st.selectbox(
    "Select Thickness",
    th_list,
    index=th_list.index("3cm") if "3cm" in th_list else 0
)
df_inv = df_inv[df_inv["Thickness"] == selected_thickness]

# ── 8) Square footage input ────────────────────────────────────────────────────
sq_ft_input = st.number_input("Enter Square Footage Needed", min_value=1, value=40, step=1)
sq_ft_used  = max(sq_ft_input, MINIMUM_SQ_FT)

# ── 9) Group, filter, and price ────────────────────────────────────────────────
df_agg = df_inv.groupby(["Full Name", "Location"]).agg(
    available_sq_ft = ("Available Sq Ft", "sum"),
    unit_cost       = ("unit_cost", "mean"),
    slab_count      = ("Serial Number", "nunique"),
    serial_numbers  = ("Serial Number", lambda x: ", ".join(sorted(x.astype(str).unique())))
).reset_index()

required = sq_ft_used * 1.1
df_agg = df_agg[df_agg["available_sq_ft"] >= required]
df_agg["price"] = df_agg.apply(
    lambda r: calculate_cost(r, sq_ft_used)["total_customer_facing_base_cost"],
    axis=1
)

if df_agg.empty:
    st.error("❌ No slabs have enough material (including 10% buffer).")
    st.stop()

# ── 10) Defensive slider for “Max Job Cost” ──────────────────────────────────────
mi, ma = int(df_agg["price"].min()), int(df_agg["price"].max())
span = ma - mi
step = 100 if span >= 100 else (span if span > 0 else 1)
budget = st.slider("Max Job Cost ($)", mi, ma, ma, step=step)

df_agg = df_agg[df_agg["price"] <= budget]
if df_agg.empty:
    st.error("❌ No materials fall within that budget.")
    st.stop()

# ── 11) “Choose a material” dropdown (updated formatting) ───────────────────────
records = df_agg.to_dict("records")
selected = st.selectbox(
    "Choose a material",
    records,
    format_func=lambda r: f"{r['Full Name']} – ${r['unit_cost']:.2f}"
)

if selected:
    costs = calculate_cost(selected, sq_ft_used)

    st.markdown(f"**Material:** {selected['Full Name']}")
    st.markdown(f"**Source Location:** {selected['Location']}")
    q = selected["Full Name"].replace(" ", "+")
    st.markdown(f"[🔎 Google Image Search](https://www.google.com/search?q={q}+countertop)")

    st.markdown("---")

    job_name         = st.text_input("Job Name (optional)")
    additional_costs = st.number_input(
        "Additional Costs – sinks, tile, plumbing",
        value=0.0, min_value=0.0, step=10.0, format="%.2f"
    )

    subtotal   = costs["total_customer_facing_base_cost"] + additional_costs
    gst_amount = subtotal * GST_RATE
    final_total = subtotal + gst_amount

    st.markdown(
        f"**Subtotal:** <span style='color:green'>${subtotal:,.2f}</span>", 
        unsafe_allow_html=True
    )
    st.markdown(
        f"**GST (5%):** <span style='color:green'>${gst_amount:,.2f}</span>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"### <span style='color:green'>Final Total: ${final_total:,.2f}</span>",
        unsafe_allow_html=True
    )

    if selected["slab_count"] > 1:
        st.info("Note: This selection uses multiple slabs; color/pattern may vary slightly.")

    if selected_email and st.button("📧 Email Quote"):
        body = compose_breakdown_email_body(
            job_name,
            selected_branch,
            selected_salesperson,
            selected,
            costs,
            get_fab_plant(selected_branch),
            selected_thickness,
            sq_ft_used,
            additional_costs,
            subtotal,
            gst_amount,
            final_total
        )
        subject = f"CounterPro Quote – {job_name or 'Unnamed Job'}"
        send_email(subject, body, selected_email)
