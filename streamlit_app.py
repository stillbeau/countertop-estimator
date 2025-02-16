import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import webbrowser

# Corrected Google Sheets URL
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ/export?format=csv"

# Adjustable Pricing (Controlled via Admin Panel)
DEFAULT_FAB_COST = 23.0  # $ per sq.ft
DEFAULT_INSTALL_COST = 23.0  # $ per sq.ft
DEFAULT_MATERIAL_MARKUP = 1.15  # 15%
DEFAULT_SALE_MARKUP = 1.2  # 20%
DEFAULT_IB_MARKUP = 1.0  # Disabled
WASTE_FACTOR = 1.2  # 20% for availability check only

def load_data():
    response = requests.get(GOOGLE_SHEET_URL)
    if response.status_code != 200:
        st.error("Error loading the file. Check the Google Sheets URL.")
        return None
    
    df = pd.read_csv(BytesIO(response.content))
    df.columns = df.columns.str.strip()
    return df

df_inventory = load_data()
if df_inventory is None:
    st.stop()

# Sidebar - Admin Panel
st.sidebar.header("Admin Settings")
fab_cost = st.sidebar.number_input("Fabrication Cost ($ per sq.ft)", min_value=0.0, value=float(DEFAULT_FAB_COST))
install_cost = st.sidebar.number_input("Install Cost ($ per sq.ft)", min_value=0.0, value=float(DEFAULT_INSTALL_COST))
material_markup = st.sidebar.number_input("Material Markup (%)", min_value=1.0, value=float(DEFAULT_MATERIAL_MARKUP))
sale_markup = st.sidebar.number_input("Final Sale Markup (%)", min_value=1.0, value=float(DEFAULT_SALE_MARKUP))
ib_markup = 1.0  # IB Markup disabled

# User Inputs
st.title("Countertop Cost Estimator")
location = st.selectbox("Select Location", options=["ABB", "VER"])
thickness = st.selectbox("Select Thickness", options=["1.2cm", "2cm", "3cm"])

# Filter available colors based on location and thickness
available_colors = df_inventory[(df_inventory["Location"] == location) & (df_inventory["Thickness"] == thickness)]
color_options = available_colors["Brand"].astype(str) + " - " + available_colors["Color"].astype(str)
color = st.selectbox("Select Brand & Color", options=color_options.unique())

req_sq_ft = st.number_input("Enter Required Sq Ft", min_value=1, value=20)

# Filter Data Based on Selection
filtered_df = available_colors[available_colors["Brand"] + " - " + available_colors["Color"] == color]

if not filtered_df.empty:
    try:
        # Ensure numeric conversion and clean currency values
        slab_cost = pd.to_numeric(filtered_df.iloc[0]["Serialized On Hand Cost"].replace("$", ""), errors='coerce')
        slab_sq_ft = pd.to_numeric(filtered_df.iloc[0]["Available Qty"], errors='coerce')
        serial_number = filtered_df.iloc[0]["Serial Number"]
        
        # Ensure values are valid before performing calculations
        if pd.isna(slab_cost) or pd.isna(slab_sq_ft) or slab_sq_ft == 0:
            st.error("Error: Invalid data for slab cost or slab square footage.")
        else:
            # Apply Waste Factor for Availability Check
            required_sq_ft_with_waste = req_sq_ft * WASTE_FACTOR
            if required_sq_ft_with_waste > slab_sq_ft:
                st.error("Not enough material available!")
            else:
                # Material Cost with 15% Markup
                base_sq_ft_price = slab_cost / slab_sq_ft
                material_cost = base_sq_ft_price * req_sq_ft * material_markup
                
                # Fabrication & Install Costs
                fab_total = fab_cost * req_sq_ft
                install_total = install_cost * req_sq_ft
                
                # IB Cost (IB Markup Disabled)
                ib_total = (material_cost + fab_total) * ib_markup
                
                # Final Sale Price
                sale_price = (ib_total + install_total) * sale_markup
                
                # Display Results
                st.success(f"Estimated Total Cost: ${sale_price:,.2f}")
                
                # Expandable Breakdown
                with st.expander("Full Cost Breakdown"):
                    st.write(f"**Slab Cost:** ${slab_cost:,.2f}")
                    st.write(f"**Slab Sq Ft:** {slab_sq_ft} sq.ft")
                    st.write(f"**Serial Number:** {serial_number}")
                    st.write(f"**Price per Sq Ft:** ${base_sq_ft_price:,.2f}")
                    st.write(f"**Material Cost (15% Markup):** ${material_cost:,.2f}")
                    st.write(f"**Fabrication Cost:** ${fab_total:,.2f}")
                    st.write(f"**Install Cost:** ${install_total:,.2f}")
                    st.write(f"**Final Sale Price:** ${sale_price:,.2f}")
                    
                # Google Image Search Button
                query = f"{color} countertop"
                google_search_url = f"https://www.google.com/search?tbm=isch&q={query.replace(' ', '+')}"
                if st.button("Search Google Images"):
                    webbrowser.open(google_search_url)
    except Exception as e:
        st.error(f"An error occurred: {e}")
