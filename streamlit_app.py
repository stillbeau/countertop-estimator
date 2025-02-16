import streamlit as st
import pandas as pd
import requests
import io

# Google Sheets URL
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ/export?format=csv"

@st.cache_data
def load_data():
    """
    Fetches and loads data from Google Sheets.
    
    Returns:
        pd.DataFrame: A DataFrame with cleaned and properly typed data, or None on error.
    """
    try:
        response = requests.get(GOOGLE_SHEET_URL)
        if response.status_code != 200:
            st.error("❌ Error loading the file. Check the Google Sheets URL.")
            return None

        df = pd.read_csv(io.StringIO(response.text))
        df.columns = df.columns.str.strip()  # Clean column names

        # Convert columns to appropriate data types
        df["Serialized On Hand Cost"] = (
            df["Serialized On Hand Cost"].replace("[\$,]", "", regex=True).astype(float)
        )
        df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors='coerce')
        df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors='coerce').fillna(0).astype(int)

        return df
    except Exception as e:
        st.error(f"❌ Failed to load data: {e}")
        return None

def calculate_costs(slab, sq_ft_needed):
    """
    Calculates the material, installation, and IB costs based on the slab details and required square footage.
    
    Args:
        slab (pd.Series): A row from the DataFrame containing slab information.
        sq_ft_needed (float): The square footage needed.
    
    Returns:
        dict: A dictionary with the cost breakdown.
    """
    # Adjustable constants:
    MARKUP_FACTOR = 1.15         # 15% markup
    INSTALL_COST_PER_SQFT = 23   # $23 per sq.ft installation cost
    FABRICATION_COST_PER_SQFT = 23  # $23 per sq.ft fabrication cost (used in IB calculation)

    available_sq_ft = slab["Available Sq Ft"]

    # Material cost with markup (for total cost calculation)
    slab_cost = slab["Serialized On Hand Cost"] * MARKUP_FACTOR  
    material_cost = (slab_cost / available_sq_ft) * sq_ft_needed

    # Installation cost (based on a fixed rate)
    install_cost = INSTALL_COST_PER_SQFT * sq_ft_needed

    # Total cost = material (with markup) + installation
    total_cost = material_cost + install_cost

    # IB Calculation: based on base material cost (before markup) plus fabrication cost
    base_material_cost_per_sq_ft = slab["Serialized On Hand Cost"] / available_sq_ft
    ib_cost_per_sq_ft = base_material_cost_per_sq_ft + FABRICATION_COST_PER_SQFT
    ib_total_cost = ib_cost_per_sq_ft * sq_ft_needed

    return {
        "available_sq_ft": available_sq_ft,
        "serial_number": slab["Serial Number"],
        "material_cost": material_cost,
        "install_cost": install_cost,
        "total_cost": total_cost,
        "ib_cost": ib_total_cost
    }

# Application title
st.title("Countertop Cost Estimator")

# Load data with a spinner for better user feedback
with st.spinner("Loading data..."):
    df_inventory = load_data()

if df_inventory is None:
    st.error("Data could not be loaded.")
    st.stop()

# Filter by location
location = st.selectbox("Select Location", options=["VER", "ABB"], index=0)
df_filtered = df_inventory[df_inventory["Location"] == location]
if df_filtered.empty:
    st.warning("No slabs found for the selected location.")
    st.stop()

# Filter by thickness
thickness = st.selectbox("Select Thickness", options=["1.2cm", "2cm", "3cm"], index=1)
df_filtered = df_filtered[df_filtered["Thickness"] == thickness]
if df_filtered.empty:
    st.warning("No slabs match the selected thickness. Please adjust your filter.")
    st.stop()

# Create a new column for display: "Brand - Color"
df_filtered = df_filtered.copy()  # Prevent SettingWithCopyWarning
df_filtered["Full Name"] = df_filtered["Brand"] + " - " + df_filtered["Color"]

# Select color/brand combination
unique_full_names = df_filtered["Full Name"].unique()
if len(unique_full_names) == 0:
    st.warning("No slabs available with the current filters.")
    st.stop()

selected_full_name = st.selectbox("Select Color", options=unique_full_names)

# Get selected slab from the filtered DataFrame
selected_slab_df = df_filtered[df_filtered["Full Name"] == selected_full_name]
if selected_slab_df.empty:
    st.error("Selected slab not found. Please choose a different option.")
    st.stop()
selected_slab = selected_slab_df.iloc[0]

# Enter required square footage
sq_ft_needed = st.number_input("Enter Square Footage Needed", min_value=1.0, value=20.0, step=1.0)

# Calculate costs using the separate function
costs = calculate_costs(selected_slab, sq_ft_needed)

# Check if there's enough material (with a 20% waste buffer)
if sq_ft_needed * 1.2 > costs["available_sq_ft"]:
    st.error("⚠️ Not enough material available! Consider selecting another slab.")

# Display the estimated total cost
st.subheader("💰 Estimated Total Cost")
st.markdown(f"**${costs['total_cost']:,.2f}**")

# Show full cost breakdown with simplified wording
if st.checkbox("🔍 Full Cost Breakdown"):
    st.write(f"**Slab Sq Ft:** {costs['available_sq_ft']:.2f} sq.ft")
    st.write(f"**Serial Number:** {costs['serial_number']}")
    st.write(f"**Material & Fab:** ${costs['material_cost']:,.2f}")
    st.write(f"**Installation:** ${costs['install_cost']:,.2f}")
    st.write(f"**IB:** ${costs['ib_cost']:,.2f}")
    st.write(f"**Total:** ${costs['total_cost']:,.2f}")

# Provide a Google Search link for the selected countertop style
google_search_query = f"{selected_full_name} Countertop"
search_url = f"https://www.google.com/search?q={google_search_query.replace(' ', '+')}"
st.markdown(f"[🔎 Search on Google]({search_url})")
