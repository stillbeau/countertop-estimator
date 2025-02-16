import streamlit as st
import pandas as pd
import requests

# Google Sheets URL
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ/export?format=csv"

@st.cache_data
def load_data():
    try:
        response = requests.get(GOOGLE_SHEET_URL)
        if response.status_code != 200:
            st.error("❌ Error loading the file. Check the Google Sheets URL.")
            return None

        df = pd.read_csv(pd.compat.StringIO(response.text))

        # Strip whitespace from column headers
        df.columns = df.columns.str.strip()

        # Convert serialized cost column (remove "$" and convert to float)
        df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].replace("[\$,]", "", regex=True).astype(float)

        # Convert available square footage column to numeric
        df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors='coerce')

        return df

    except Exception as e:
        st.error(f"❌ Failed to load data: {e}")
        return None

# Load inventory data
df_inventory = load_data()

if df_inventory is None:
    st.stop()

# Debugging: Show dataframe and column types
st.write("✅ Data Preview:")
st.write(df_inventory.head())

st.write("✅ Column Data Types:")
st.write(df_inventory.dtypes)

# User selection
st.sidebar.header("Select Options")
location_selected = st.sidebar.selectbox("Select Location", df_inventory["Location"].unique())
filtered_df = df_inventory[df_inventory["Location"] == location_selected]

# Ensure location filtering works
if filtered_df.empty:
    st.error(f"No materials found for {location_selected}")
    st.stop()

# Select Thickness First
thickness_selected = st.sidebar.selectbox("Select Thickness", filtered_df["Thickness"].unique())

# Now filter available colors for that thickness
filtered_df = filtered_df[filtered_df["Thickness"] == thickness_selected]
color_selected = st.sidebar.selectbox("Select Color", filtered_df["Color"].unique())

# Find the selected slab
selected_slab = filtered_df[filtered_df["Color"] == color_selected]

if selected_slab.empty:
    st.error(f"No slabs available for {color_selected} at {location_selected}")
    st.stop()

# Extract relevant values
slab_cost = selected_slab["Serialized On Hand Cost"].values[0]
slab_sq_ft = selected_slab["Available Sq Ft"].values[0]
serial_number = selected_slab["Serial Number"].values[0]

# Debugging: Ensure correct values before calculations
st.write(f"🛠 Debug - Slab Cost: {slab_cost}, Slab Sq Ft: {slab_sq_ft}, Serial Number: {serial_number}")

# Validate data before performing calculations
if pd.isna(slab_cost) or pd.isna(slab_sq_ft) or slab_sq_ft == 0:
    st.error("❌ Error: Invalid data for slab cost or slab square footage.")
    st.stop()

# Calculate the total cost for user input square footage
sq_ft_needed = st.number_input("Enter required square footage:", min_value=1.0, step=0.5)
total_material_cost = (slab_cost / slab_sq_ft) * sq_ft_needed

# Display pricing breakdown
with st.expander("📋 Pricing Breakdown"):
    st.write(f"🔹 **Slab Cost:** ${slab_cost:,.2f}")
    st.write(f"🔹 **Available Sq Ft:** {slab_sq_ft} sq.ft")
    st.write(f"🔹 **Serial Number:** {serial_number}")
    st.write(f"🔹 **Price per Sq Ft:** ${slab_cost / slab_sq_ft:,.2f}")
    st.write(f"🔹 **Total Cost for {sq_ft_needed} sq.ft:** ${total_material_cost:,.2f}")
