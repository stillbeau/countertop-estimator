import streamlit as st
import pandas as pd
import requests
from io import BytesIO

# 🔹 File URL from your updated Google Sheet or GitHub
file_url = "YOUR_NEW_FILE_URL_HERE.xlsx"  # Replace with actual file URL

@st.cache_data
def load_data():
    """Load and clean the updated Excel file."""
    response = requests.get(file_url)
    if response.status_code != 200:
        st.error("Error loading the file. Check the file URL.")
        return None

    xls = pd.ExcelFile(BytesIO(response.content), engine="openpyxl")
    df = pd.read_excel(xls, sheet_name='Sheet1')

    # Ensure column names are clean
    df.columns = df.columns.str.strip()

    # Convert numerical fields
    df["Available Qty"] = pd.to_numeric(df["Available Qty"], errors='coerce')
    df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].replace('[\$,]', '', regex=True).astype(float)

    return df

# Load inventory
df_inventory = load_data()

if df_inventory is None:
    st.stop()

# 🎛 Editable Control Panel for Pricing Adjustments
st.sidebar.header("🔧 Pricing Control Panel")
default_fabrication_cost = st.sidebar.number_input("Fabrication Cost per Sq Ft ($)", value=23.00)
default_temp_install_cost = st.sidebar.number_input("Temp/Install Cost per Sq Ft ($)", value=23.00)

# 🎨 Dropdowns based on the cleaned file
thickness_options = df_inventory["Thickness"].unique()
selected_thickness = st.selectbox("Select Thickness", thickness_options)

# Filter colors based on the selected thickness
filtered_colors = df_inventory[df_inventory["Thickness"] == selected_thickness]["Color"].unique()
selected_color = st.selectbox("Select Color", filtered_colors)

# Find matching slab details
selected_slab = df_inventory[(df_inventory["Thickness"] == selected_thickness) & (df_inventory["Color"] == selected_color)]

if selected_slab.empty:
    st.warning("No slabs found for the selected combination.")
    st.stop()

# Show available slabs and details
st.write(f"**Available Slabs:** {selected_slab['Available Qty'].sum()} sq ft")

# 📌 Pricing Calculations
slab_cost = selected_slab.iloc[0]["Serialized On Hand Cost"]
available_sqft = selected_slab.iloc[0]["Available Qty"]
sqft_price = slab_cost / available_sqft  # Price per sq ft
ib_price = (sqft_price + default_fabrication_cost) * 1.2  # IB Cost
sale_price = (ib_price + default_temp_install_cost) * 1.2  # Final sale price

# 🛒 Display Pricing
if st.button("Estimate Price"):
    st.subheader("💰 Estimated Pricing")
    st.write(f"**Sq Ft Price:** ${sqft_price:.2f}")
    st.write(f"**IB Price:** ${ib_price:.2f}")
    st.write(f"**Sale Price:** ${sale_price:.2f}")

    # Expandable full details
    with st.expander("📊 Full Cost Breakdown"):
        st.write(f"- **Fabrication Cost:** ${default_fabrication_cost}")
        st.write(f"- **Temp/Install Cost:** ${default_temp_install_cost}")
        st.write(f"- **Base Sq Ft Cost:** ${sqft_price:.2f}")
        st.write(f"- **IB Sq Ft Price:** ${ib_price:.2f}")
        st.write(f"- **Final Sale Price:** ${sale_price:.2f}")
