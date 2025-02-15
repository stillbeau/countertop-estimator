import pandas as pd
import streamlit as st
import requests
from io import BytesIO

# ✅ GitHub RAW File URL
file_url = "https://raw.githubusercontent.com/stillbeau/countertop-estimator/main/deadfeb.xlsx"

# 🔑 Admin Passwords
ADMIN_PASSWORD = "floform2024"
BREAKDOWN_PASSWORD = "floform"  # 🔒 Password for cost breakdown

# ✅ Initialize session state for settings
if "fab_cost" not in st.session_state or not isinstance(st.session_state.fab_cost, (int, float)):
    st.session_state.fab_cost = float(23)  # ✅ Default fabrication cost per sq ft
if "install_cost" not in st.session_state or not isinstance(st.session_state.install_cost, (int, float)):
    st.session_state.install_cost = float(23)  # Default install cost per sq ft
if "ib_margin" not in st.session_state or not isinstance(st.session_state.ib_margin, (int, float)):
    st.session_state.ib_margin = float(0.15)  # Default IB margin (15%)
if "sale_margin" not in st.session_state or not isinstance(st.session_state.sale_margin, (int, float)):
    st.session_state.sale_margin = float(0.15)  # Default Sale margin (15%)
if "admin_access" not in st.session_state:
    st.session_state.admin_access = False  # Admin access flag
if "breakdown_access" not in st.session_state:
    st.session_state.breakdown_access = False  # 🔒 Cost breakdown access flag
if "df_inventory" not in st.session_state:
    st.session_state.df_inventory = pd.DataFrame()  # Empty DataFrame until loaded

# ✅ Load and clean the Excel file
@st.cache_data
def load_data():
    """Load slab data from the Excel sheet."""
    try:
        response = requests.get(file_url, timeout=10)
        if response.status_code != 200:
            st.error(f"⚠️ Error loading file: HTTP {response.status_code}")
            return None

        xls = pd.ExcelFile(BytesIO(response.content), engine="openpyxl")
        df = pd.read_excel(xls, sheet_name='Sheet1')

        # ✅ Clean column names (remove hidden spaces)
        df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=True)

        # ✅ Extract Material, Color, and Thickness from "Product Variant"
        df[['Material', 'Color_Thickness']] = df['Product Variant'].str.split(' - ', n=1, expand=True)
        df[['Color', 'Thickness']] = df['Color_Thickness'].str.rsplit(' ', n=1, expand=True)

        # ✅ Normalize Thickness Formatting
        df['Thickness'] = df['Thickness'].str.replace("cm", " cm", regex=False).str.strip()

        # ✅ Filter thickness to only valid options (1.2 cm, 2 cm, 3 cm)
        valid_thicknesses = ["1.2 cm", "2 cm", "3 cm"]
        df = df[df['Thickness'].isin(valid_thicknesses)]

        # ✅ Convert numeric columns
        numeric_cols = ['Available Qty', 'SQ FT PRICE']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)  # ✅ Replace NaN with 0

        # ✅ Store DataFrame in session state
        st.session_state.df_inventory = df

        return df

    except Exception as e:
        st.error(f"❌ Error loading the file: {e}")
        return None

# Load the data if not already loaded
if st.session_state.df_inventory.empty:
    df_inventory = load_data()
else:
    df_inventory = st.session_state.df_inventory

# 🎨 **Admin Panel for Adjustable Pricing Settings**
with st.sidebar:
    st.header("🔑 Admin Panel")

    # Ask for password
    password_input = st.text_input("Enter Admin Password:", type="password")
    if st.button("🔓 Login"):
        if password_input == ADMIN_PASSWORD:
            st.session_state.admin_access = True
            st.success("✅ Admin Access Granted!")
        else:
            st.error("❌ Incorrect Password")

    if st.session_state.admin_access:
        st.subheader("⚙️ Adjustable Rates")

        st.session_state.fab_cost = st.number_input("🛠 Fabrication Cost per sq ft:", 
                                                    value=float(st.session_state.fab_cost), step=1.0)

        st.session_state.ib_margin = st.number_input("📈 IB Margin (%)", 
                                                     value=float(st.session_state.ib_margin), step=0.01, format="%.2f")

        st.session_state.install_cost = st.number_input("🚚 Install & Template Cost per sq ft:", 
                                                        value=float(st.session_state.install_cost), step=1.0)

        st.session_state.sale_margin = st.number_input("📈 Sale Margin (%)", 
                                                       value=float(st.session_state.sale_margin), step=0.01, format="%.2f")

# 🎨 **UI Setup**
st.title("🛠 Countertop Cost Estimator")
st.markdown("### Select your slab and get an estimate!")

# 📏 **Square Feet Input**
square_feet = st.number_input("📐 Enter Square Feet Needed:", min_value=1, step=1)

# 🔲 **Thickness Dropdown**
thickness_options = ["1.2 cm", "2 cm", "3 cm"]
selected_thickness = st.selectbox("🔲 Select Thickness:", thickness_options)

# 🎨 **Color Dropdown (Populated from Excel)**
available_colors = df_inventory[df_inventory["Thickness"] == selected_thickness]["Color"].dropna().unique()
if len(available_colors) > 0:
    selected_color = st.selectbox("🎨 Select Color:", sorted(available_colors))
else:
    st.warning("⚠️ No colors available for this thickness.")
    selected_color = None

# 📊 **Estimate Cost Button**
if st.button("📊 Estimate Cost"):
    if selected_color is None:
        st.error("❌ Please select a valid color.")
    else:
        selected_slab = df_inventory[
            (df_inventory["Color"] == selected_color) & (df_inventory["Thickness"] == selected_thickness)
        ]

        if selected_slab.empty:
            st.error("❌ No slab found for the selected color and thickness.")
        else:
            selected_slab = selected_slab.iloc[0]
            available_sqft = selected_slab["Available Qty"]
            sq_ft_price = float(selected_slab["SQ FT PRICE"])  # ✅ Ensure it's a valid number
            required_sqft = square_feet * 1.2  # **20% Waste Factor**

            if required_sqft > available_sqft:
                st.error("❌ Not enough material available.")
            else:
                # **Cost Calculations**
                material_cost = sq_ft_price * required_sqft
                fabrication_cost = float(st.session_state.fab_cost) * required_sqft
                install_cost = float(st.session_state.install_cost) * required_sqft

                ib_cost = (material_cost + fabrication_cost) * (1 + float(st.session_state.ib_margin))
                sale_price = (ib_cost + install_cost) * (1 + float(st.session_state.sale_margin))

                # ✅ **Display Final Price**
                st.success(f"💰 **Estimated Sale Price: ${sale_price:.2f}**")

                # 🧐 **Password-Protected Cost Breakdown**
                if not st.session_state.breakdown_access:
                    breakdown_password = st.text_input("🔒 Enter password for full breakdown:", type="password")
                    if st.button("🔓 Unlock Breakdown"):
                        if breakdown_password == BREAKDOWN_PASSWORD:
                            st.session_state.breakdown_access = True
                            st.success("✅ Cost Breakdown Unlocked!")
                        else:
                            st.error("❌ Incorrect password!")

                if st.session_state.breakdown_access:
                    st.markdown(f"""
                    **💰 Cost Breakdown**  
                    - **Material Cost (from Excel):** ${material_cost:.2f}  
                    - **Fabrication Cost:** ${fabrication_cost:.2f}  
                    - **IB Cost (Material + Fab + IB Margin):** ${ib_cost:.2f}  
                    - **Installation Cost:** ${install_cost:.2f}  
                    - **Total Sale Price (IB + Install + Sale Margin):** ${sale_price:.2f}  
                    """)