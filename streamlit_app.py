import streamlit as st
import pandas as pd
import requests

# Google Sheets URL (Ensure it's a published CSV link)
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ/edit?usp=sharing"

# Load Data
@st.cache_data
def load_data():
    response = requests.get(GOOGLE_SHEET_URL)
    if response.status_code != 200:
        st.error("❌ Failed to load data: Check Google Sheets URL.")
        return None
    df = pd.read_csv(response.content.decode("utf-8"))
    df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors='coerce')
    df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].replace('[\$,]', '', regex=True).astype(float)
    return df

df_inventory = load_data()
if df_inventory is None:
    st.stop()

# Sidebar for Location Selection
location = st.sidebar.radio("Select Location:", df_inventory["Location"].unique())
filtered_df = df_inventory[df_inventory["Location"] == location]

# Main UI
st.title("Countertop Cost Estimator")

# Dropdown for Thickness
thickness = st.selectbox("Select Thickness:", sorted(filtered_df["Thickness"].unique()))
filtered_df = filtered_df[filtered_df["Thickness"] == thickness]

# Dropdown for Color (Brand + Color Combined)
filtered_df["Color Option"] = filtered_df["Brand"] + " - " + filtered_df["Color"]
color = st.selectbox("Select Color:", sorted(filtered_df["Color Option"].unique()))

# Get Selected Row Data
selected_row = filtered_df[filtered_df["Color Option"] == color].iloc[0]
serial_number = selected_row["Serial Number"]
slab_cost = selected_row["Serialized On Hand Cost"]
slab_sq_ft = selected_row["Available Sq Ft"]

# Input for Square Footage
sqft_required = st.number_input("Enter Square Footage Required:", min_value=1, step=1)

# Ensure Material Availability
sqft_required_with_waste = sqft_required * 1.2  # 20% Waste Factor
if sqft_required_with_waste > slab_sq_ft:
    st.error("⚠️ Not enough material available! Consider choosing another option.")
    st.stop()

# Pricing Constants
INSTALL_COST_PER_SQFT = 23  # Fixed Install Price
FAB_COST_PER_SQFT = 23  # Fixed Fabrication Price
MATERIAL_MARKUP = 1.15  # 15% Material Markup

# Calculate Pricing
material_cost_per_sqft = (slab_cost / slab_sq_ft) * MATERIAL_MARKUP
ib_cost_per_sqft = (material_cost_per_sqft + FAB_COST_PER_SQFT)  # Material + Fabrication
sale_price = (ib_cost_per_sqft + INSTALL_COST_PER_SQFT) * sqft_required  # Total Sale Price

# Display Estimated Cost
st.subheader("💰 Estimated Total Cost")
st.write(f"**${sale_price:,.2f}**")

# Expandable Cost Breakdown
with st.expander("🔍 Full Cost Breakdown"):
    st.write(f"**Slab Sq Ft:** {slab_sq_ft} sq.ft")
    st.write(f"**Serial Number:** {serial_number}")
    
    # New Material Cost (Total)
    material_total_cost = material_cost_per_sqft * sqft_required
    st.write(f"**Material Cost (Total):** ${material_total_cost:,.2f}")
    
    # Installation Cost (Total)
    total_install_cost = INSTALL_COST_PER_SQFT * sqft_required
    st.write(f"**Installation Cost (Total):** ${total_install_cost:,.2f}")
    
    # IB Cost (Material + Fabrication)
    ib_total_cost = ib_cost_per_sqft * sqft_required
    st.write(f"**IB Cost (Total Material + Fabrication):** ${ib_total_cost:,.2f}")
    
    # Final Total Price
    st.write(f"**Total Cost for {sqft_required} sq.ft:** ${sale_price:,.2f}")

# Google Search Button
search_query = f"{color} Countertop"
search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
st.markdown(f"[🔍 Search on Google]({search_url})", unsafe_allow_html=True)
