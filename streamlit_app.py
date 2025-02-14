import pandas as pd
import streamlit as st
import openpyxl

# Load dataset
file_url = "https://raw.githubusercontent.com/stillbeau/countertop-estimator/main/Dead%20Stock%20Jan%209%202025%20revised.xlsx"


@st.cache_data
def load_data():
    """Load and clean the pre-uploaded data file."""
    xls = pd.ExcelFile(file_path)
    df = pd.read_excel(xls, sheet_name='Sheet1')
    df.columns = df.columns.str.strip().str.replace(" ", "", regex=True)
    df_cleaned = df[['Product Variant', 'Available Qty', 'SQ FT PRICE', 'FAB', 'TEMP/Install', 'IB SQ FT Price', 'Sale price']].copy()
    df_cleaned.columns = ['Product_Variant', 'Available_Qty_sqft', 'Sq_ft_price', 'Fab', 'Temp_Install', 'IB_sq_ft_price', 'Sale_price']
    df_cleaned[['Material', 'Color_Thickness']] = df_cleaned['Product_Variant'].str.split(' - ', n=1, expand=True)
    df_cleaned[['Color', 'Thickness']] = df_cleaned['Color_Thickness'].str.rsplit(' ', n=1, expand=True)
    df_cleaned['Available_Qty_sqft'] = pd.to_numeric(df_cleaned['Available_Qty_sqft'], errors='coerce')
    df_cleaned['Sq_ft_price'] = pd.to_numeric(df_cleaned['Sq_ft_price'], errors='coerce')
    df_cleaned['Fab'] = pd.to_numeric(df_cleaned['Fab'], errors='coerce')
    df_cleaned['Temp_Install'] = pd.to_numeric(df_cleaned['Temp_Install'], errors='coerce')
    df_cleaned['IB_sq_ft_price'] = pd.to_numeric(df_cleaned['IB_sq_ft_price'], errors='coerce')
    df_cleaned['Sale_price'] = pd.to_numeric(df_cleaned['Sale_price'], errors='coerce')
    return df_cleaned[['Material', 'Color', 'Thickness', 'Available_Qty_sqft', 'Sq_ft_price', 'Fab', 'Temp_Install', 'IB_sq_ft_price', 'Sale_price']]

df_inventory = load_data()

# Streamlit UI
st.title("📏 Countertop Cost Estimator")

# User inputs
square_feet = st.number_input("Enter Square Feet:", min_value=1.0, step=0.5)
thickness = st.selectbox("Select Thickness:", sorted(df_inventory['Thickness'].dropna().unique()))
filtered_colors = df_inventory[df_inventory['Thickness'] == thickness]['Color'].dropna().unique()
color = st.selectbox("Select Color:", sorted(filtered_colors) if len(filtered_colors) > 0 else [])

if st.button("📊 Estimate Cost"):
    match = df_inventory[(df_inventory['Color'] == color) & (df_inventory['Thickness'] == thickness)]
    if match.empty:
        st.error("No matching slabs found.")
    else:
        match = match.sort_values(by='Sq_ft_price')
        selected_slab = match.iloc[0]
        available_slabs = match[['Available_Qty_sqft']].sum().values[0]
        required_sq_ft = square_feet * 1.2  # Add 20% waste factor
        
        if required_sq_ft > available_slabs:
            st.warning("Not enough slab quantity available for the requested square footage (including 20% waste).")
        else:
            material_cost = required_sq_ft * selected_slab['Sq_ft_price']
            fab_cost = required_sq_ft * selected_slab['Fab']
            install_cost = required_sq_ft * selected_slab['Temp_Install']
            ib_cost = material_cost + fab_cost
            sale_price = required_sq_ft * selected_slab['Sale_price']
            
            st.success(f"Material Cost: ${material_cost:.2f}")
            st.success(f"Fabrication Cost: ${fab_cost:.2f}")
            st.success(f"Installation Cost: ${install_cost:.2f}")
            st.success(f"IB Cost: ${ib_cost:.2f}")
            st.success(f"Sale Price: ${sale_price:.2f}")
            st.info(f"Available Slab Quantity: {available_slabs:.2f} sq. ft.")
            
            # Google search button
            query = f"{color} {thickness} countertop"
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            st.markdown(f"[🔎 Search Online]({search_url})")
