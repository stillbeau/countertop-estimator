import streamlit as st
import pandas as pd
from src.data import load_salespeople_sheet, load_inventory_csv, get_fab_plant
from src.costs import calculate_cost
from src.email import compose_breakdown_email_body, send_email

# --- Page config & CSS ---
st.set_page_config(page_title="CounterPro", layout="centered")

# iOS‑style visual tweaks -------------------------------------------------------
st.markdown(
    """
    <style>
    html, body, [class*="css"]  {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", sans-serif;
        background-color: #1c1c1e;
        color: #f2f2f7;
    }

    /* Input controls */
    div[data-baseweb="select"] > div,
    input[type="number"] {
        background-color: #2c2c2e;
        border: 1px solid #3a3a3c;
        border-radius: 12px;
        color: #f2f2f7;
    }

    /* Buttons */
    .stButton>button {
        background-color: #0a84ff;
        color: white;
        border: none;
        border-radius: 12px;
        padding: 8px 16px;
        font-size: 0.9rem;
    }

    /* Slider accent */
    div[data-baseweb="slider"] [role="slider"] {
        background-color: #0a84ff;
    }

    /* Smaller label fonts */
    .stLabel, label { font-size: 0.85rem; }
    h1 { font-size: 2rem; }
    h2 { font-size: 1.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Constants ---
MINIMUM_SQ_FT             = 35
GST_RATE                  = 0.05
WASTE_FACTOR              = 1.05

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

# --- MAIN APP UI ---
st.title("CounterPro")

# ── 1) Branch & Salesperson (side by side) ───────────────────────────────────────
df_sp = load_salespeople_sheet(SPREADSHEET_ID, SALESPEOPLE_TAB)
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
df_inv = load_inventory_csv(INVENTORY_CSV_URL)
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
# Normalize thickness like "3 cm" → "3cm" so we can safely default to 3cm.
df_inv["Thickness"] = (
    df_inv["Thickness"]
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "", regex=False)
)
th_list = sorted(df_inv["Thickness"].unique())
selected_thickness = st.selectbox(
    "Select Thickness",
    th_list,
    index=th_list.index("3cm") if "3cm" in th_list else 0,
    format_func=lambda t: t.replace("cm", " cm")
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

required = sq_ft_used * WASTE_FACTOR
df_agg = df_agg[df_agg["available_sq_ft"] >= required]
df_agg["price"] = df_agg.apply(
    lambda r: calculate_cost(r, sq_ft_used)["total_customer_facing_base_cost"],
    axis=1
)

if df_agg.empty:
    st.error(f"❌ No slabs have enough material (including {((WASTE_FACTOR * 100) - 100):.0f}% buffer).")
    st.stop()

# ── 10) Defensive slider for “Max Job Cost” ──────────────────────────────────────
# Use float values so rounding doesn't drop the highest‑priced option
mi, ma = float(df_agg["price"].min()), float(df_agg["price"].max())
span = ma - mi
step = 100.0 if span >= 100 else (span if span > 0 else 1.0)
budget = st.slider("Max Job Cost ($)", mi, ma, ma, step=step)

df_agg = df_agg[df_agg["price"] <= budget]
if df_agg.empty:
    st.error("❌ No materials fall within that budget.")
    st.stop()

# ── 11) “Choose a material” dropdown (showing final $/sq ft) ────────────────────
records = df_agg.to_dict("records")
selected = st.selectbox(
    "Choose a material",
    records,
    format_func=lambda r: (
        f"{r['Full Name']} – "
        f"${calculate_cost(r, sq_ft_used)['total_customer_facing_base_cost'] / sq_ft_used:,.2f}/sq ft"
    )
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
