import streamlit as st
import pandas as pd
import requests
from io import StringIO
import webbrowser

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

        # 📌 Extract Brand, Location, Color, Thickness, and Serial Number
        df["Brand"] = df["Product Variant"].str.extract(r'- ([\w\s]+)\(')
        df["Location"] = df["Product Variant"].str.extract(r'\((\w+)\)')
        df["Thickness"] = df["Product Variant"].str.extract(r'(\d+\.?\d*cm)')
        df["Color"] = df["Product Variant"].str.extract(r'\) (.+) (\d+\.?\d*cm)')[0]
        df["Serial Number"] = df["Serial Number"].astype(str)  # Ensure it's treated as text

        # ✅ Combine Brand & Color for selection
        df["Brand_Color"] = df["Brand"].str.strip() + " - " + df["Color"].str.strip()

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

# 🏢 Select Location (Vernon or Abbotsford)
location_options = df_inventory["Location"].dropna().unique()
selected_location = st.selectbox("Select Location:", location_options)

# Filter inventory based on selected location
filtered_df = df_inventory[df_inventory["Location"] == selected_location]

# 🎛️ Select Thickness (Dropdown)
thickness_options = filtered_df["Thickness"].dropna().unique()
selected_thickness = st.selectbox("Select Thickness:", thickness_options)

# 🎛️ Filter Colors based on Thickness
filtered_df = filtered_df[filtered_df["Thickness"] == selected_thickness]
color_options = filtered_df["Brand_Color"].dropna().unique()
selected_brand_color = st.selectbox("Select Material (Brand - Color):", color_options if len(color_options) > 0 else ["No colors available"])

# 🔢 Enter Required Square Footage
required_sq_ft = st.number_input("Enter Required Square Footage:", min_value=1, value=20)

# 🛠️ Admin Settings for Pricing (Hidden from Main Page)
with st.sidebar:
    st.header("🔑 Admin Settings")
    temp_install = st.number_input("Temp/Install Cost per sq.ft", value=23, min_value=0)
    fabrication_cost = st.number_input("Fabrication Cost per sq.ft", value=23, min_value=0)

# 📊 Calculate Costs based on Selections
selected_row = filtered_df[filtered_df["Brand_Color"] == selected_brand_color]

if not selected_row.empty:
    slab_cost = selected_row["Serialized On Hand Cost"].values[0]
    slab_sqft = selected_row["Available Qty"].values[0]
    serial_number = selected_row["Serial Number"].values[0]  # Get Serial Number

    # 🚨 Ensure required square footage is available
    required_with_waste = required_sq_ft * 1.2  # Adding 20% waste factor
    if required_with_waste > slab_sqft:
        st.warning("⚠️ Not enough material available for this selection. Choose a different slab.")
    else:
        sq_ft_price = slab_cost / slab_sqft
        ib_sq_ft_price = (sq_ft_price + fabrication_cost) * 1.2
        sale_price = (ib_sq_ft_price + temp_install) * 1.2
        total_cost = sale_price * required_sq_ft

        # 💰 Estimate Button
        if st.button("💰 Estimate Price"):
            st.success(f"Estimated Total Cost: **${total_cost:.2f}** for {required_sq_ft} sq.ft")

            # 🧐 Cost Breakdown Toggle
            with st.expander("📊 Full Cost Breakdown"):
                st.write(f"**Slab Cost:** ${slab_cost:.2f}")
                st.write(f"**Slab Sq Ft:** {slab_sqft:.2f} sq.ft")
                st.write(f"**Serial Number:** {serial_number}")
                st.write(f"**Price per Sq Ft:** ${sq_ft_price:.2f}")
                st.write(f"**IB Sq Ft Price:** ${ib_sq_ft_price:.2f}")
                st.write(f"**Sale Price per Sq Ft:** ${sale_price:.2f}")
                st.write(f"**Total Cost for {required_sq_ft} sq.ft:** ${total_cost:.2f}")

            # 🔍 Google Image Search Button
            google_search_url = f"https://www.google.com/search?tbm=isch&q={selected_brand_color}+countertop"
            if st.button("🔍 Search for Images on Google"):
                webbrowser.open(google_search_url)

else:
    st.warning("⚠️ No matching slabs found. Try another selection.")