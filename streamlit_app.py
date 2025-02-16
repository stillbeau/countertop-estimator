import streamlit as st
import pandas as pd
import requests
from io import StringIO

# ✅ Updated Google Sheets direct CSV link
file_url = "https://docs.google.com/spreadsheets/d/166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ/gviz/tq?tqx=out:csv"

@st.cache_data
def load_data():
    """Load and clean the Google Sheets data."""
    try:
        response = requests.get(file_url)
        if response.status_code != 200:
            st.error(f"❌ Error: Unable to fetch data. Status Code: {response.status_code}")
            return None

        # Read CSV data from Google Sheets
        df = pd.read_csv(StringIO(response.text))

        # Clean column names
        df.columns = df.columns.str.strip()

        # Convert numerical fields
        df["Available Qty"] = pd.to_numeric(df["Available Qty"], errors='coerce')
        df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].replace('[\$,]', '', regex=True).astype(float)

        # 📌 Extract Brand, Location, Color, and Thickness
        df["Brand"] = df["Product Variant"].str.extract(r'- ([\w\s]+)\(')
        df["Location"] = df["Product Variant"].str.extract(r'\((\w+)\)')
        df["Thickness"] = df["Product Variant"].str.extract(r'(\d+\.?\d*cm)')
        
        # Extract Color correctly (keeping # if present)
        df["Color"] = df["Product Variant"].str.extract(r'\) (.+) (\d+\.?\d*cm)')[0]

        return df

    except Exception as e:
        st.error(f"❌ Error loading the file: {e}")
        return None

# Load data
df_inventory = load_data()
if df_inventory is None:
    st.stop()  # Stop execution if data fails to load

# 🎨 Streamlit UI - Title & Instructions
st.title("🛠️ Countertop Cost Estimator")
st.write("Select options below to estimate costs based on available inventory.")

# 🎛️ Select Thickness (Dropdown)
thickness_options = df_inventory["Thickness"].dropna().unique()
selected_thickness = st.selectbox("Select Thickness:", thickness_options)

# 🎛️ Filter Colors based on Thickness
filtered_df = df_inventory[df_inventory["Thickness"] == selected_thickness]
color_options = filtered_df["Color"].dropna().unique()
selected_color = st.selectbox("Select Color:", color_options if len(color_options) > 0 else ["No colors available"])

# 🧮 Editable Cost Inputs
st.subheader("🔧 Adjustable Pricing")
temp_install = st.number_input("Temp/Install Cost per sq.ft", value=23, min_value=0)
fabrication_cost = st.number_input("Fabrication Cost per sq.ft", value=23, min_value=0)

# 📊 Calculate Costs based on Selections
selected_row = filtered_df[filtered_df["Color"] == selected_color]

if not selected_row.empty:
    slab_cost = selected_row["Serialized On Hand Cost"].values[0]
    slab_sqft = selected_row["Available Qty"].values[0]

    sq_ft_price = slab_cost / slab_sqft
    ib_sq_ft_price = (sq_ft_price + fabrication_cost) * 1.2
    sale_price = (ib_sq_ft_price + temp_install) * 1.2

    # 💰 Estimate Button
    if st.button("💰 Estimate Price"):
        st.success(f"Estimated Sale Price: **${sale_price:.2f} per sq.ft**")

        # 🧐 Cost Breakdown Toggle
        with st.expander("📊 Full Cost Breakdown"):
            st.write(f"**Slab Cost:** ${slab_cost:.2f}")
            st.write(f"**Slab Sq Ft:** {slab_sqft:.2f} sq.ft")
            st.write(f"**Price per Sq Ft:** ${sq_ft_price:.2f}")
            st.write(f"**IB Sq Ft Price:** ${ib_sq_ft_price:.2f}")
            st.write(f"**Sale Price per Sq Ft:** ${sale_price:.2f}")

else:
    st.warning("⚠️ No matching slabs found. Try another selection.")
