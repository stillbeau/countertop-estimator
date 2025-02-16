import streamlit as st
import pandas as pd
import requests

# Google Sheets URL
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ/export?format=csv"

# Load data from Google Sheets
@st.cache_data
def load_data():
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL)
        df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors="coerce")
        df["Serialized On Hand Cost"] = df["Serialized On Hand Cost"].replace({'\$': '', ',': ''}, regex=True).astype(float)
        return df
    except Exception as e:
        st.error(f"❌ Failed to load data: {str(e)}")
        return None

df_inventory = load_data()

if df_inventory is not None:
    st.title("Countertop Estimator")

    # Select Location
    location = st.selectbox("Select Location", df_inventory["Location"].unique())
    filtered_df = df_inventory[df_inventory["Location"] == location]
    
    # Select Thickness First
    thickness = st.selectbox("Select Thickness", sorted(filtered_df["Thickness"].unique()))
    thickness_df = filtered_df[filtered_df["Thickness"] == thickness]
    
    # Select Color (Brand + Color Combined)
    thickness_df["Full Color Name"] = thickness_df["Brand"] + " " + thickness_df["Color"]
    selected_color = st.selectbox("Select Color", thickness_df["Full Color Name"].unique())
    color_df = thickness_df[thickness_df["Full Color Name"] == selected_color]
    
    # Enter Required Square Footage
    job_sq_ft = st.number_input("Enter Square Footage Required", min_value=1, step=1)
    
    if not color_df.empty:
        # Get available material details
        available_sq_ft = color_df.iloc[0]["Available Sq Ft"]
        slab_cost = color_df.iloc[0]["Serialized On Hand Cost"]
        slab_sq_ft = available_sq_ft  # Assuming the slab size is the available sq ft
        serial_number = color_df.iloc[0]["Serial Number"]
        
        # Check for availability
        needed_sq_ft = job_sq_ft * 1.2  # Including 20% extra for waste
        if needed_sq_ft > available_sq_ft:
            st.error(f"🚨 Not enough material available! Needed: {needed_sq_ft:.2f} sq.ft, Available: {available_sq_ft:.2f} sq.ft")
        
        # Price Calculations
        slab_price_per_sqft = (slab_cost / slab_sq_ft) * 1.15  # Adding 15% markup
        install_cost_per_sqft = 23
        fabrication_cost_per_sqft = 23
        total_price = (slab_price_per_sqft + install_cost_per_sqft + fabrication_cost_per_sqft) * job_sq_ft
        
        # Display Estimate
        st.subheader("💰 Estimated Total Cost")
        st.markdown(f"**${total_price:,.2f}**")
        
       with st.expander("🔍 Full Cost Breakdown"):
    st.write(f"**Slab Sq Ft:** {slab_sq_ft} sq.ft")
    st.write(f"**Serial Number:** {serial_number}")
    
    # New Material Cost (Total)
    material_total_cost = material_cost_per_sqft * sqft_required
    st.write(f"**Material Cost (Total):** ${material_total_cost:,.2f}")
    
    # Installation Cost (Total)
    total_install_cost = install_cost_per_sqft * sqft_required
    st.write(f"**Installation Cost (Total):** ${total_install_cost:,.2f}")
    
    # IB Cost (Material + Fabrication)
    st.write(f"**IB Cost (Material + Fabrication):** ${ib_cost_per_sqft:,.2f} per sq.ft")

    # Total Cost for Requested Sq Ft
    st.write(f"**Total Cost for {sqft_required} sq.ft:** ${total_price:,.2f}")

        
        # Google Search Button
        search_query = f"{selected_color} countertop"
        search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
        st.markdown(f"[🔍 Search '{selected_color}' on Google]({search_url})")
    else:
        st.error("❌ No matching slabs found. Please check your selection.")
