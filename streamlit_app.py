import pandas as pd
import streamlit as st
import requests

# ✅ Google Sheets Import
SHEET_ID = "17uClLZ2FpynR6Qck_Vq-OkLetvxGv_w0VLQFVct0GHQ"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv"

# 🔑 Admin Password
ADMIN_PASSWORD = "floform2024"

# ✅ **Load Data from Google Sheets**
@st.cache_data
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=True)  # ✅ Clean column names

        # ✅ Extract Material, Color, Thickness
        df[['Material', 'Color_Thickness']] = df['Product Variant'].str.split(' - ', n=1, expand=True)
        df[['Color', 'Thickness']] = df['Color_Thickness'].str.rsplit(' ', 1, expand=True)
        df['Thickness'] = df['Thickness'].str.replace("cm", " cm", regex=False).str.strip()

        # ✅ Convert Pricing Data
        df["Serialized On Hand Cost"] = pd.to_numeric(df["Serialized On Hand Cost"], errors="coerce").fillna(0)
        df["Available Qty"] = pd.to_numeric(df["Available Qty"], errors="coerce").fillna(0)

        # ✅ Group by Color & Thickness
        df_grouped = df.groupby(["Color", "Thickness"], as_index=False).agg({
            "Available Qty": "sum",
            "Serialized On Hand Cost": "max",
            "Serial Number": lambda x: ', '.join(map(str, x.dropna().unique()))
        })

        return df_grouped

    except Exception as e:
        st.error(f"❌ Error loading Google Sheet: {e}")
        return None

# ✅ Load the data
df_inventory = load_data()

# 🎨 **Main UI**
st.title("🛠 Countertop Cost Estimator")

square_feet = st.number_input("📐 Square Feet:", min_value=1, step=1)
selected_thickness = st.selectbox("🔲 Thickness:", ["1.2 cm", "2 cm", "3 cm"], index=2)

# Ensure colors exist for the selected thickness
available_colors = df_inventory[df_inventory["Thickness"] == selected_thickness]["Color"].dropna().unique()
selected_color = st.selectbox("🎨 Color:", sorted(available_colors) if len(available_colors) > 0 else [])

if st.button("📊 Estimate Cost"):
    if not selected_color:
        st.error("❌ Please select a valid color.")
    else:
        selected_slab = df_inventory[(df_inventory["Color"] == selected_color) & (df_inventory["Thickness"] == selected_thickness)]
        total_available_sqft = selected_slab["Available Qty"].sum()
        required_sqft = square_feet * 1.2  # Including waste factor

        if required_sqft > total_available_sqft:
            st.error(f"🚨 Not enough material available! ({total_available_sqft} sq ft available, {required_sqft} sq ft needed)")
        else:
            # ✅ **Use max pricing from Google Sheet**
            material_cost = selected_slab["Serialized On Hand Cost"].max()
            if material_cost == 0:
                st.warning("⚠️ Price missing! Check inventory data.")

            material_cost_total = required_sqft * material_cost / total_available_sqft
            fabrication_cost = 23 * required_sqft
            install_cost = 23 * required_sqft
            ib_cost = (material_cost_total + fabrication_cost) * 1.15
            sale_price = (ib_cost + install_cost) * 1.15

            st.success(f"💰 **Estimated Sale Price: ${sale_price:.2f}**")

            # ✅ Google Search for Slab Images
            query = f"{selected_color} {selected_thickness} countertop"
            google_url = f"https://www.google.com/search?tbm=isch&q={query.replace(' ', '+')}"
            st.markdown(f"🔍 [Click here to view {selected_color} images]({google_url})", unsafe_allow_html=True)

            # ✅ Show Breakdown
            serial_numbers = selected_slab["Serial Number"].iloc[0] if "Serial Number" in selected_slab.columns else "N/A"

            with st.expander("🧐 Show Full Cost Breakdown"):
                st.markdown(f"""
                - **Material Cost:** ${material_cost_total:.2f}  
                - **Fabrication Cost:** ${fabrication_cost:.2f}  
                - **IB Cost:** ${ib_cost:.2f}  
                - **Installation Cost:** ${install_cost:.2f}  
                - **Total Sale Price:** ${sale_price:.2f}  
                - **Slab Serial Number(s):** {serial_numbers}  
                """)