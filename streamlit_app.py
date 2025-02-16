import streamlit as st
import pandas as pd
import requests
import io

# Google Sheets URL
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ/export?format=csv"

def load_data():
    """Fetches and loads data from Google Sheets."""
    try:
        response = requests.get(GOOGLE_SHEET_URL)
        if response.status_code != 200:
            st.error("❌ Error loading the file. Check the Google Sheets URL.")
            return None

        df = pd.read_csv(io.StringIO(response.text))
        df.columns = df.columns.str.strip()  # Clean column names

        # Ensure numerical values are converted properly
        df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].replace("[\$,]", "", regex=True).astype(float)
        df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors='coerce')
        df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors='coerce').fillna(0).astype(int)

        return df
    except Exception as e:
        st.error(f"❌ Failed to load data: {e}")
        return None

st.title("Countertop Cost Estimator")

# Load data
df_inventory = load_data()
if df_inventory is None:
    st.stop()

# Select location
location = st.selectbox("Select Location", options=["VER", "ABB"], index=0)
df_filtered = df_inventory[df_inventory["Location"] == location]

# Select thickness
thickness = st.selectbox("Select Thickness", options=["1.2cm", "2cm", "3cm"], index=1)
df_filtered = df_filtered[df_filtered["Thickness"] == thickness]

# Select color
df_filtered["Full Name"] = df_filtered["Brand"] + " - " + df_filtered["Color"]
selected_color = st.selectbox("Select Color", options=df_filtered["Full Name"].unique())

# Get selected slab
selected_slab = df_filtered[df_filtered["Full Name"] == selected_color].iloc[0]

# Enter required square footage
sq_ft_needed = st.number_input("Enter Square Footage Needed", min_value=1.0, value=20.0, step=1.0)

# Extracting values for calculations
available_sq_ft = selected_slab["Available Sq Ft"]
serial_number = selected_slab["Serial Number"]
slab_cost = selected_slab["Serialized On Hand Cost"] * 1.15  # 15% markup
install_cost_per_sq_ft = 23
fabrication_cost_per_sq_ft = 23
ib_price_per_sq_ft = (slab_cost / available_sq_ft) + fabrication_cost_per_sq_ft

# Ensure we have enough material
red_flag = sq_ft_needed * 1.2 > available_sq_ft  # 20% waste buffer
if red_flag:
    st.error("⚠️ Not enough material available! Consider selecting another slab.")

# Calculate total costs
material_cost = (slab_cost / available_sq_ft) * sq_ft_needed
install_cost = install_cost_per_sq_ft * sq_ft_needed
total_cost = material_cost + install_cost

# Display estimated total cost
st.subheader("💰 Estimated Total Cost")
st.markdown(f"**${total_cost:,.2f}**")

# Show full cost breakdown
if st.checkbox("🔍 Full Cost Breakdown"):
    st.write(f"**Slab Sq Ft:** {available_sq_ft:.2f} sq.ft")
    st.write(f"**Serial Number:** {serial_number}")
    st.write(f"**Material Cost for {sq_ft_needed} sq.ft:** ${material_cost:,.2f}")
    st.write(f"**Installation Cost for {sq_ft_needed} sq.ft:** ${install_cost:,.2f}")
    st.write(f"**Total Cost for {sq_ft_needed} sq.ft:** **${total_cost:,.2f}**")

# Google Search button
google_search_query = f"{selected_color} Countertop"
search_url = f"https://www.google.com/search?q={google_search_query.replace(' ', '+')}"
st.markdown(f"[🔎 Search on Google]({search_url})")
