import streamlit as st
import pandas as pd
import requests
import io

# === CONFIGURATION SECTION (Hidden in code) ===
MARKUP_FACTOR = 1.15            # 15% markup on material cost
INSTALL_COST_PER_SQFT = 23      # Installation cost per square foot
FABRICATION_COST_PER_SQFT = 23  # Fabrication cost per square foot
ADDITIONAL_IB_RATE = 0          # Extra rate added to material in IB calculation (per sq.ft)
GST_RATE = 0.05                 # 5% GST
# ==============================================

# Google Sheets URL for cost data
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
        df["Serialized On Hand Cost"] = (
            df["Serialized On Hand Cost"].replace("[\$,]", "", regex=True).astype(float)
        )
        df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors="coerce")
        df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors="coerce").fillna(0).astype(int)
        return df
    except Exception as e:
        st.error(f"❌ Failed to load data: {e}")
        return None

def calculate_costs(slab, sq_ft_needed):
    """
    Returns a dictionary with:
      - total_cost: material + fab + install (no tax)
      - ib_cost: base material + fab (for breakdown)
      - other details (available_sq_ft, serial_number, etc.)
    """
    available_sq_ft = slab["Available Sq Ft"]

    # Material cost (with 15% markup) without fabrication
    material_cost_with_markup = (
        slab["Serialized On Hand Cost"] * MARKUP_FACTOR / available_sq_ft
    ) * sq_ft_needed

    # Fabrication total cost
    fabrication_total = FABRICATION_COST_PER_SQFT * sq_ft_needed

    # Material & Fab
    material_and_fab = material_cost_with_markup + fabrication_total

    # Installation
    install_cost = INSTALL_COST_PER_SQFT * sq_ft_needed

    # Total (before tax)
    total_cost = material_and_fab + install_cost

    # IB Calculation (base material + fabrication + optional IB rate)
    ib_total_cost = (
        (slab["Serialized On Hand Cost"] / available_sq_ft)
        + FABRICATION_COST_PER_SQFT
        + ADDITIONAL_IB_RATE
    ) * sq_ft_needed

    return {
        "available_sq_ft": available_sq_ft,
        "serial_number": slab["Serial Number"],
        "material_and_fab": material_and_fab,
        "install_cost": install_cost,
        "total_cost": total_cost,  # before tax
        "ib_cost": ib_total_cost,
    }

# --- TITLE & SUBTITLE (no HTML) ---
st.title("Countertop Cost Estimator")
st.write("Get an accurate estimate for your custom countertop project")

# Load data
with st.spinner("Loading data..."):
    df_inventory = load_data()

if df_inventory is None:
    st.error("Data could not be loaded.")
    st.stop()

# Location & thickness filters
location = st.selectbox("Select Location", options=["VER", "ABB"], index=0)
df_filtered = df_inventory[df_inventory["Location"] == location]
if df_filtered.empty:
    st.warning("No slabs found for the selected location.")
    st.stop()

thickness = st.selectbox("Select Thickness", options=["1.2cm", "2cm", "3cm"], index=1)
df_filtered = df_filtered[df_filtered["Thickness"] == thickness]
if df_filtered.empty:
    st.warning("No slabs match the selected thickness. Please adjust your filter.")
    st.stop()

# Color & edge profile
df_filtered = df_filtered.copy()
df_filtered["Full Name"] = df_filtered["Brand"] + " - " + df_filtered["Color"]
selected_full_name = st.selectbox("Select Color", options=df_filtered["Full Name"].unique())

edge_profiles = ["Bullnose", "Eased", "Beveled", "Ogee", "Waterfall"]
selected_edge_profile = st.selectbox("Select Edge Profile", options=edge_profiles)
st.write("For more details on edge profiles, visit [Floform Edge Profiles](https://floform.com/countertops/edge-profiles/)")

# Retrieve selected slab
selected_slab_df = df_filtered[df_filtered["Full Name"] == selected_full_name]
if selected_slab_df.empty:
    st.error("Selected slab not found. Please choose a different option.")
    st.stop()
selected_slab = selected_slab_df.iloc[0]

# Square footage input
sq_ft_needed = st.number_input("Enter Square Footage Needed", min_value=1.0, value=20.0, step=1.0)

# Calculate costs
costs = calculate_costs(selected_slab, sq_ft_needed)

# Check material availability
if sq_ft_needed * 1.2 > costs["available_sq_ft"]:
    st.error("⚠️ Not enough material available! Consider selecting another slab.")

# Calculate GST
sub_total = costs["total_cost"]
gst_amount = sub_total * GST_RATE
final_price = sub_total + gst_amount

# --- Display Price Breakdown (Markdown only) ---
st.markdown("### Price Breakdown")
st.markdown(
    f"""
**Total (before tax):**  
${sub_total:,.2f}

**GST (5%):**  
${gst_amount:,.2f}

**Total Price:**  
## ${final_price:,.2f}
"""
)

# (Optional) Add a "Request Contact" button here:
# st.button("Request Contact")

# Password-protected breakdown
with st.expander("View Full Cost Breakdown (password required)"):
    pwd = st.text_input("Enter password to view breakdown:", type="password")
    if pwd:
        if pwd == "sam":
            st.write(f"**Slab Sq Ft:** {costs['available_sq_ft']:.2f} sq.ft")
            st.write(f"**Serial Number:** {costs['serial_number']}")
            st.write(f"**Material & Fab:** ${costs['material_and_fab']:,.2f}")
            st.write(f"**Installation:** ${costs['install_cost']:,.2f}")
            st.write(f"**IB:** ${costs['ib_cost']:,.2f}")
            st.write(f"**Total (before tax):** ${costs['total_cost']:,.2f}")
            st.write(f"**Edge Profile Selected:** {selected_edge_profile}")
        else:
            st.error("Incorrect password.")