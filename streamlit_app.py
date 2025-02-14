import pandas as pd
import streamlit as st
import requests
from io import BytesIO

# ✅ Correct GitHub RAW File URL
file_url = "https://raw.githubusercontent.com/stillbeau/countertop-estimator/main/deadfeb.xlsx"

# ✅ Load and clean the Excel file
@st.cache_data
def load_data():
    """Load and clean the Excel file from GitHub."""
    try:
        response = requests.get(file_url, timeout=10)
        if response.status_code != 200:
            st.error(f"⚠️ Error loading file: HTTP {response.status_code}")
            return None

        xls = pd.ExcelFile(BytesIO(response.content), engine="openpyxl")
        df = pd.read_excel(xls, sheet_name='Sheet1')

        # ✅ Clean column names (remove hidden spaces)
        df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=True)

        # ✅ Ensure "Serial Number" is a string
        for col in df.columns:
            if "serial" in col.lower():
                df[col] = df[col].astype(str)

        # ✅ Extract Material, Color, and Thickness from "Product Variant"
        df[['Material', 'Color_Thickness']] = df['Product Variant'].str.split(' - ', n=1, expand=True)
        df[['Color', 'Thickness']] = df['Color_Thickness'].str.rsplit(' ', n=1, expand=True)

        # ✅ Normalize Thickness Formatting
        df['Thickness'] = df['Thickness'].str.replace("cm", " cm", regex=False).str.strip()

        # ✅ Filter thickness to only valid options (1.2 cm, 2 cm, 3 cm)
        valid_thicknesses = ["1.2 cm", "2 cm", "3 cm"]
        df = df[df['Thickness'].isin(valid_thicknesses)]

        # ✅ Convert numeric columns
        numeric_cols = ['Available Qty', 'SQ FT PRICE', 'FAB', 'TEMP/Install', 'IB SQ FT Price', 'Sale price']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        return df[['Material', 'Color', 'Thickness', 'Available Qty', 'SQ FT PRICE', 'FAB', 'TEMP/Install', 'IB SQ FT Price', 'Sale price']]
    
    except Exception as e:
        st.error(f"❌ Error while loading the file: {e}")
        return None

df_inventory = load_data()

if df_inventory is None or df_inventory.empty:
    st.error("⚠️ No valid data found. Please check the Excel file format.")
    st.stop()

# 🎨 **UI Setup**
st.title("🛠 Countertop Cost Estimator")
st.markdown("### Select your requirements and get a cost estimate!")

# 📏 **Square Feet Input**
square_feet = st.number_input("📐 Enter Square Feet Needed:", min_value=1, step=1)

# 🔲 **Thickness Dropdown** (Only 1.2 cm, 2 cm, 3 cm)
thickness_options = ["1.2 cm", "2 cm", "3 cm"]
selected_thickness = st.selectbox("🔲 Select Thickness:", thickness_options)

# 🎨 **Color Dropdown (Auto-Filters by Thickness)**
filtered_colors = df_inventory[df_inventory['Thickness'] == selected_thickness]['Color'].dropna().unique()
selected_color = st.selectbox("🎨 Select Color:", sorted(filtered_colors) if len(filtered_colors) > 0 else [])

# 📊 **Estimate Cost Button**
if st.button("📊 Estimate Cost"):
    if not selected_color:
        st.error("⚠️ Please select a color.")
    else:
        # 📌 Filter for selected material
        filtered_df = df_inventory[
            (df_inventory['Color'] == selected_color) & (df_inventory['Thickness'] == selected_thickness)
        ]
        
        if filtered_df.empty:
            st.error("❌ No matching slabs found.")
        else:
            selected_slab = filtered_df.iloc[0]
            available_sqft = selected_slab['Available Qty']
            
            required_sqft = square_feet * 1.2  # **20% Waste Factor**
            
            if required_sqft > available_sqft:
                st.error("❌ Not enough material available for this selection (including 20% waste).")
            else:
                # **Cost Calculations**
                material_cost = required_sqft * selected_slab['SQ FT PRICE']
                fab_cost = required_sqft * selected_slab['FAB']
                install_cost = required_sqft * selected_slab['TEMP/Install']
                ib_cost = material_cost + fab_cost  # **IB Cost: Material + Fabrication**
                sale_price = required_sqft * selected_slab['Sale price']

                # ✅ **Display Final Price**
                st.success(f"💰 **Estimated Sale Price: ${sale_price:.2f}**")

                # 🧐 **Show More Details Button**
                if st.button("🧐 Show Full Cost Breakdown"):
                    st.write(f"📌 **Material**: {selected_slab['Material']} {selected_slab['Color']} {selected_slab['Thickness']}")
                    st.write(f"📦 **Available Slab Quantity**: {available_sqft:.2f} sq ft")
                    st.write(f"🔲 **Required Sq Ft (20% waste included)**: {required_sqft:.2f} sq ft")
                    
                    st.markdown(f"""
                    **💰 Cost Breakdown**  
                    - **Material Cost:** ${material_cost:.2f}  
                    - **Fabrication Cost:** ${fab_cost:.2f}  
                    - **Installation Cost:** ${install_cost:.2f}  
                    - **IB Cost:** ${ib_cost:.2f}  
                    - **Sale Price:** ${sale_price:.2f}  
                    """)

