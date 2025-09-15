import streamlit as st
import pandas as pd
import gspread
import json
import smtplib
import pytz
from decimal import Decimal, ROUND_HALF_UP
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import quote

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
    pre, code { white-space: pre-wrap !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Constants ---
MINIMUM_SQ_FT = 35
MARKUP_FACTOR = 1.51
INSTALL_COST_PER_SQFT = 21.0
FABRICATION_COST_PER_SQFT = 15.0  # CHANGED to $15 as requested
WASTE_FACTOR = 1.05
IB_MATERIAL_MARKUP = 1.05
IB_MIN_MARGIN = 0.18  # NEW: ensure IB is at least 18% gross margin over (slab + fab)

# --- Tax configuration by branch ---
BRANCH_TAX_RATES = {
    "Vernon":    {"gst": 0.05, "pst": 0.00, "pst_name": "PST"},
    "Victoria":  {"gst": 0.05, "pst": 0.00, "pst_name": "PST"},
    "Vancouver": {"gst": 0.05, "pst": 0.00, "pst_name": "PST"},
    "Calgary":   {"gst": 0.05, "pst": 0.00, "pst_name": "PST"},
    "Edmonton":  {"gst": 0.05, "pst": 0.00, "pst_name": "PST"},
    "Saskatoon": {"gst": 0.05, "pst": 0.06, "pst_name": "PST"},
    "Winnipeg":  {"gst": 0.05, "pst": 0.00, "pst_name": "RST"},
    "default":   {"gst": 0.05, "pst": 0.00, "pst_name": "PST"},
}

# ————————————————————————————————————————————————————————————
# Inventory CSV + Salespeople GSheet
INVENTORY_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vRzPf_DEc7ojcjqCsk_5O9HtSFWy7aj2Fi_bPjUh6HVaN38coQSINDps0RGrpiM9ox58izhsNkzD51j/"
    "pub?output=csv"
)
SPREADSHEET_ID = "166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ"
SALESPEOPLE_TAB = "Salespeople"
# ————————————————————————————————————————————————————————————

# --- Helpers -------------------------------------------------------------------

def money(x: float | Decimal) -> str:
    try:
        d = Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        d = Decimal("0.00")
    return f"${d:,.2f}"


def parse_email_list(s: str | None) -> list[str]:
    if not s:
        return []
    parts = [p.strip() for p in s.replace(";", ",").split(",")]
    return [p for p in parts if p]


def safe_get_secret(key: str, required: bool = False, default: str | None = None) -> str | None:
    try:
        val = st.secrets.get(key, default)
        if required and not val:
            st.error(f"Missing required secret: `{key}`")
        return val
    except Exception as e:
        if required:
            st.error(f"Error reading secret `{key}`: {e}")
        return default


def get_fab_plant(branch: str) -> str:
    return "Abbotsford" if branch in ["Vernon", "Victoria", "Vancouver"] else "Saskatoon"

# --- Data loading & normalization ---------------------------------------------

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


@st.cache_data(show_spinner=False)
def load_inventory_csv(url: str) -> pd.DataFrame:
    return pd.read_csv(url)


def normalize_inventory_df(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip()

    # Available Sq Ft
    if "Available Qty" in df.columns:
        df["Available Sq Ft"] = pd.to_numeric(df["Available Qty"], errors="coerce")
    elif "Available Sq Ft" in df.columns:
        df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors="coerce")
    else:
        st.error(
            "❌ Could not find either 'Available Qty' or 'Available Sq Ft' in the inventory CSV.\n"
            f"Columns found: {df.columns.tolist()}"
        )
        st.stop()

    # Unit Cost (per sq ft)
    if "Serialized Unit Cost" in df.columns:
        df["unit_cost"] = pd.to_numeric(
            df["Serialized Unit Cost"].astype(str).str.replace(r"[\$,]", "", regex=True),
            errors="coerce",
        )
    elif "Serialized On Hand Cost" in df.columns:
        df["SerialOnHandCost"] = pd.to_numeric(
            df["Serialized On Hand Cost"].astype(str).str.replace(r"[\$,]", "", regex=True),
            errors="coerce",
        )
        denom = df["Available Sq Ft"].replace(0, pd.NA)
        df["unit_cost"] = df["SerialOnHandCost"] / denom
    else:
        st.error(
            "❌ Could not find 'Serialized Unit Cost' or 'Serialized On Hand Cost' in the inventory CSV.\n"
            f"Columns found: {df.columns.tolist()}"
        )
        st.stop()

    # Basic filtering
    df = df[
        df["Available Sq Ft"].notna() & (df["Available Sq Ft"] > 0)
        & df["unit_cost"].notna() & (df["unit_cost"] > 0)
    ]

    # Clean text fields
    for c in ["Brand", "Color", "Thickness"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
        else:
            df[c] = ""

    df["Full Name"] = df["Brand"] + " - " + df["Color"]

    # Normalize thickness for robust matching (e.g., "3 cm" => "3cm")
    df["Thickness_norm"] = df["Thickness"].str.lower().str.replace(" ", "", regex=False)

    return df

# --- Pricing -------------------------------------------------------------------

def calculate_cost(rec: dict, sq: float) -> dict:
    uc = float(rec.get("unit_cost", 0) or 0)

    # Customer-facing build (material markup on unit cost, then add fab + install)
    mat_component = uc * MARKUP_FACTOR * sq
    fab_component = FABRICATION_COST_PER_SQFT * sq
    ins_component = INSTALL_COST_PER_SQFT * sq

    # IB pricing — ensure at least 18% margin on (slab + fabrication rate)
    base_cost_for_ib_per_sq = uc + FABRICATION_COST_PER_SQFT
    ib_candidate_margin_per_sq = base_cost_for_ib_per_sq / (1.0 - IB_MIN_MARGIN)
    ib_candidate_markup_per_sq = (uc * IB_MATERIAL_MARKUP) + FABRICATION_COST_PER_SQFT

    if ib_candidate_margin_per_sq >= ib_candidate_markup_per_sq:
        ib_per_sq = ib_candidate_margin_per_sq
        ib_method = "margin_floor"  # 18% floor applied
    else:
        ib_per_sq = ib_candidate_markup_per_sq
        ib_method = "markup_chain"   # legacy markup method

    ib_total = ib_per_sq * sq

    # Margin % is (price - cost) / price
    ib_margin_pct = 0.0
    if ib_per_sq > 0:
        ib_margin_pct = 1.0 - (base_cost_for_ib_per_sq / ib_per_sq)

    return {
        "base_material_and_fab_component": mat_component + fab_component,
        "base_install_cost_component":     ins_component,
        "ib_cost_component":               ib_total,
        "total_customer_facing_base_cost": mat_component + fab_component + ins_component,
        # Extras for UI transparency
        "ib_per_sq": ib_per_sq,
        "ib_base_cost_per_sq": base_cost_for_ib_per_sq,
        "ib_margin_pct": ib_margin_pct,
        "ib_method": ib_method,
    }


def compute_taxes(subtotal: float, tax_rates: dict) -> dict:
    gst_rate = float(tax_rates.get("gst", 0.05))
    pst_rate = float(tax_rates.get("pst", 0.00))
    pst_name = tax_rates.get("pst_name", "PST")

    gst_amt = Decimal(str(subtotal * gst_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    pst_amt = Decimal(str(subtotal * pst_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    final   = Decimal(str(subtotal)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) + gst_amt + pst_amt

    return {
        "gst_rate": gst_rate,
        "pst_rate": pst_rate,
        "pst_name": pst_name,
        "gst_amount": float(gst_amt),
        "pst_amount": float(pst_amt),
        "final_total": float(final),
    }


def compute_taxes(subtotal: float, tax_rates: dict) -> dict:
    gst_rate = float(tax_rates.get("gst", 0.05))
    pst_rate = float(tax_rates.get("pst", 0.00))
    pst_name = tax_rates.get("pst_name", "PST")

    gst_amt = Decimal(str(subtotal * gst_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    pst_amt = Decimal(str(subtotal * pst_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    final   = Decimal(str(subtotal)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) + gst_amt + pst_amt

    return {
        "gst_rate": gst_rate,
        "pst_rate": pst_rate,
        "pst_name": pst_name,
        "gst_amount": float(gst_amt),
        "pst_amount": float(pst_amt),
        "final_total": float(final),
    }

# --- Email & HTML --------------------------------------------------------------

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
    tax_info: dict,
    final_total: float,
) -> str:
    tz = pytz.timezone("America/Vancouver")
    now = pd.Timestamp.now(tz=tz).strftime("%Y-%m-%d %H:%M:%S %Z")
    job = job_name or "Unnamed Job"

    # Transfer request button (supports multiple recipients)
    transfer_button_html = ""
    try:
        to_emails = parse_email_list(st.secrets.get("TRANSFER_REQUEST_EMAIL"))
        to_display = ",".join(to_emails) if to_emails else ""
        if rec.get("Location") != fab_plant and to_display:
            subject = f"Slab Transfer Request - Job: {job}"
            body = f"""
Please initiate a transfer for the following slab(s):

PO: 
JOB LINK: 

Job Name: {job}
Material: {rec.get("Full Name", "N/A")}
Serial Number(s): {rec.get("serial_numbers", "N/A")}

FROM (Current Location): {rec.get("Location", "N/A")}
TO (Fabrication Plant): {fab_plant}

Thank you,
{selected_salesperson}
            """
            mailto_link = f"mailto:{quote(to_display)}?subject={quote(subject)}&body={quote(body)}"
            transfer_button_html = f"""
<p style="text-align: center; margin-top: 25px;">
  <a href="{mailto_link}" target="_blank" style="background-color: #2563eb; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; font-size: 16px;">
    Request Slab Transfer
  </a>
</p>
<p style="text-align: center; font-size: 12px; color: #666;">
  (Material is at a different location from the fabrication plant)
</p>
            """
    except Exception:
        transfer_button_html = "<p style='color: red; text-align: center;'>Could not create transfer button.</p>"

    pst_row_html = ""
    if tax_info.get("pst_amount", 0) > 0:
        pst_name = tax_info.get("pst_name", "PST")
        pst_rate_pct = tax_info.get("pst_rate", 0) * 100
        pst_row_html = f"""
        <tr>
            <td>{pst_name} ({pst_rate_pct:.0f}%):</td>
            <td>{money(tax_info["pst_amount"])}</td>
        </tr>
        """

    return f"""<html>
<head><style>
  body {{ font-family: Arial, sans-serif; color: #333; }}
  .container {{ max-width: 640px; margin: 0 auto; padding: 20px; }}
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
      <tr><td>Material &amp; Fabrication:</td><td>{money(costs["base_material_and_fab_component"])}</td></tr>
      <tr><td>Installation:</td><td>{money(costs["base_install_cost_component"])}</td></tr>
      <tr><td>IB Cost (Internal):</td><td>{money(costs["ib_cost_component"])}</td></tr>
    </table>

    <h2>Totals</h2>
    <table>
      <tr><th>Description</th><th>Amount</th></tr>
      <tr><td>Base Estimate:</td><td>{money(costs["total_customer_facing_base_cost"])}</td></tr>
      <tr><td>Additional Costs (sinks, tile, plumbing):</td><td>{money(additional_costs)}</td></tr>
      <tr><td>Subtotal:</td><td>{money(subtotal)}</td></tr>
      <tr><td>GST ({tax_info.get("gst_rate", 0) * 100:.0f}%):</td><td>{money(tax_info.get("gst_amount", 0))}</td></tr>
      {pst_row_html}
      <tr class="grand-total-row"><td>Final Total:</td><td>{money(final_total)}</td></tr>
    </table>

    {transfer_button_html}
    <div class="footer">Generated by CounterPro on {now}</div>
  </div>
</body>
</html>"""


def send_email(subject: str, body: str, to_email: str):
    try:
        frm = safe_get_secret("SENDER_FROM_EMAIL", required=True)
        smtp_server = safe_get_secret("SMTP_SERVER", required=True)
        smtp_port = int(safe_get_secret("SMTP_PORT", required=True) or 587)
        smtp_user = safe_get_secret("EMAIL_USER", required=True)
        smtp_pass = safe_get_secret("EMAIL_PASSWORD", required=True)
        cc_list = parse_email_list(st.secrets.get("QUOTE_TRACKING_CC_EMAIL"))
        to_list = parse_email_list(to_email) or [to_email]

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = frm
        msg["To"] = ", ".join(to_list)
        if cc_list:
            msg["Cc"] = ", ".join(cc_list)
        msg.attach(MIMEText(body, "html"))

        recipients = to_list + cc_list
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(frm, recipients, msg.as_string())

        st.success("✅ Quote emailed successfully.")
    except Exception as e:
        st.error(f"Email failed: {e}")

# --- MAIN APP UI ---------------------------------------------------------------

st.title("CounterPro")

# 1) Branch & Salesperson
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
        hit = sales_for_branch.loc[
            sales_for_branch["SalespersonName"] == selected_salesperson, "Email"
        ]
        if not hit.empty:
            selected_email = hit.iat[0]
else:
    st.warning("⚠️ No salespeople data loaded.")
    selected_branch = ""
    selected_salesperson = ""

# 2) Load & normalize Inventory
try:
    df_inv_raw = load_inventory_csv(INVENTORY_CSV_URL)
except Exception as e:
    st.error(f"❌ Could not fetch inventory CSV: {e}")
    st.stop()

if df_inv_raw.empty:
    st.error("❌ Loaded inventory CSV is empty.")
    st.stop()

df_inv = normalize_inventory_df(df_inv_raw)

# 3) Filter by Branch→Source location
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
    st.warning(f"No material-source mapping for branch '{selected_branch}'. Showing all inventory.")

# 4) Thickness selector — default to 3 cm (normalized to '3cm')
th_values = sorted(df_inv["Thickness_norm"].dropna().unique())
default_th_idx = th_values.index("3cm") if "3cm" in th_values else 0
selected_thickness_norm = st.selectbox(
    "Select Thickness",
    th_values,
    index=default_th_idx,
    format_func=lambda t: "3 cm" if t == "3cm" else t,
)

df_inv = df_inv[df_inv["Thickness_norm"] == selected_thickness_norm]
selected_thickness_label = "3 cm" if selected_thickness_norm == "3cm" else selected_thickness_norm

# 5) Square footage input
sq_ft_input = st.number_input("Enter Square Footage Needed", min_value=1, value=40, step=1)
sq_ft_used = max(sq_ft_input, MINIMUM_SQ_FT)
if sq_ft_input < MINIMUM_SQ_FT:
    st.caption(f"Minimum charge applies: using {MINIMUM_SQ_FT} sq.ft for pricing.")

# 6) Aggregate & ensure material sufficiency with waste buffer
required = sq_ft_used * WASTE_FACTOR
df_agg = (
    df_inv.groupby(["Full Name", "Location"])  # group within location to respect transfers
    .agg(
        available_sq_ft=("Available Sq Ft", "sum"),
        unit_cost=("unit_cost", "mean"),
        slab_count=("Serial Number", "nunique"),
        serial_numbers=("Serial Number", lambda x: ", ".join(sorted(x.astype(str).unique()))),
    )
    .reset_index()
)

df_agg = df_agg[df_agg["available_sq_ft"] >= required]

if df_agg.empty:
    st.error(f"❌ No slabs have enough material (including {int((WASTE_FACTOR - 1) * 100)}% buffer).")
    st.stop()

# Price each option

df_agg["price"] = df_agg.apply(
    lambda r: calculate_cost(r, sq_ft_used)["total_customer_facing_base_cost"],
    axis=1,
)

df_agg = df_agg.sort_values("price", ascending=True, ignore_index=True)

# 7) Defensive budget slider
mi, ma = int(df_agg["price"].min()), int(df_agg["price"].max())
if mi == ma:
    st.caption(f"All qualifying options are ~{money(mi)}. Budget slider skipped.")
else:
    span = ma - mi
    step = 100 if span >= 100 else (span if span > 0 else 1)
    budget = st.slider("Max Job Cost ($)", mi, ma, ma, step=step)
    df_agg = df_agg[df_agg["price"] <= budget]
    if df_agg.empty:
        st.error("❌ No materials fall within that budget.")
        st.stop()

# 8) Choose a material (shows final $/sq ft)
records = df_agg.to_dict("records")
selected = st.selectbox(
    "Choose a material",
    records,
    format_func=lambda r: (
        f"{r['Full Name']} – "
        f"{money(calculate_cost(r, sq_ft_used)['total_customer_facing_base_cost'] / sq_ft_used)}/sq ft"
    ),
)

# 9) Detail + quote
if selected:
    costs = calculate_cost(selected, sq_ft_used)

    # IB transparency readout
    ib_base = costs.get("ib_base_cost_per_sq", 0.0)
    ib_rate = costs.get("ib_per_sq", 0.0)
    ib_margin_pct = costs.get("ib_margin_pct", 0.0)
    ib_method = costs.get("ib_method", "")
    method_label = "18% floor applied" if ib_method == "margin_floor" else "standard IB markup"
    st.caption(
        f"**IB check** — Base cost (slab+fab): {money(ib_base)}/sq ft → IB rate: {money(ib_rate)}/sq ft → "
        f"Margin: {ib_margin_pct*100:.1f}% ({method_label})."
    )

    st.markdown(f"**Material:** {selected['Full Name']}")
    st.markdown(f"**Source Location:** {selected['Location']}")
    q = selected["Full Name"].replace(" ", "+")
    st.markdown(f"[🔎 Google Image Search](https://www.google.com/search?q={q}+countertop)")

    st.markdown("---")

    job_name = st.text_input("Job Name (optional)")
    additional_costs = st.number_input(
        "Additional Costs – sinks, tile, plumbing",
        value=0.0, min_value=0.0, step=10.0, format="%.2f",
    )

    subtotal = costs["total_customer_facing_base_cost"] + additional_costs
    tax_rates = BRANCH_TAX_RATES.get(selected_branch, BRANCH_TAX_RATES["default"]) 
    tax_info = compute_taxes(subtotal, tax_rates)
    final_total = tax_info["final_total"]

    st.markdown(f"**Subtotal:** <span style='color:green'>{money(subtotal)}</span>", unsafe_allow_html=True)
    st.markdown(
        f"**GST ({tax_info['gst_rate']*100:.0f}%):** <span style='color:green'>{money(tax_info['gst_amount'])}</span>",
        unsafe_allow_html=True,
    )
    if tax_info["pst_amount"] > 0:
        st.markdown(
            f"**{tax_info['pst_name']} ({tax_info['pst_rate']*100:.0f}%):** "
            f"<span style='color:green'>{money(tax_info['pst_amount'])}</span>",
            unsafe_allow_html=True,
        )
    st.markdown(f"### <span style='color:green'>Final Total: {money(final_total)}</span>", unsafe_allow_html=True)

    if selected["slab_count"] > 1:
        st.info("Note: This selection uses multiple slabs; color/pattern may vary slightly.")

    # Compose HTML for download/email
    body_html = compose_breakdown_email_body(
        job_name=job_name,
        selected_branch=selected_branch,
        selected_salesperson=selected_salesperson,
        rec=selected,
        costs=costs,
        fab_plant=get_fab_plant(selected_branch),
        selected_thickness=selected_thickness_label,
        sq_ft_used=sq_ft_used,
        additional_costs=additional_costs,
        subtotal=subtotal,
        tax_info={
            "gst_rate": tax_info["gst_rate"],
            "gst_amount": tax_info["gst_amount"],
            "pst_rate": tax_info["pst_rate"],
            "pst_amount": tax_info["pst_amount"],
            "pst_name": tax_info["pst_name"],
        },
        final_total=final_total,
    )

    # Download quote as HTML
    st.download_button(
        label="⬇️ Download Quote (HTML)",
        data=body_html,
        file_name=f"CounterPro_Quote_{(job_name or 'Unnamed').replace(' ', '_')}.html",
        mime="text/html",
        use_container_width=True,
    )

    # Email to selected salesperson ONLY (no override field)
    if selected_email:
        if st.button("📧 Email Quote", use_container_width=True):
            subject = f"CounterPro Quote – {job_name or 'Unnamed Job'}"
            send_email(subject, body_html, selected_email)
    else:
        st.warning("No salesperson email found for the selected branch.")
