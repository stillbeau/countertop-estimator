import streamlit as st
import pandas as pd
import requests
from io import BytesIO

# ✅ GitHub RAW File URL (Your Excel Data)
file_url = "https://raw.githubusercontent.com/stillbeau/countertop-estimator/main/deadfeb.xlsx"

# 🔑 Admin Password
ADMIN_PASSWORD = "floform2024"

# ✅ Load and clean the Excel file
@st.cache_data
def load_data():
    """Load slab data from the Excel sheet with error handling."""
    response = requests.get(file_url, timeout=10)
    
    if response.status_code != 200:
        st.error(f"⚠️ Error loading file: HTTP {response.status_code}")
        return None
    
    xls = pd.ExcelFile(BytesIO(response.content), engine="openpyxl")
    df = pd.read_excel(xls, sheet_name='Sheet1')

    # ✅ Clean column names (remove hidden spaces & non-printable characters)
    df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=True)

    # ✅ Debug: Print available columns if key error occurs
    if "Product Variant" not in df.columns:
        st.error("❌ 'Product Variant' column is missing. Available columns:")
        st.write(df.columns)
        return None

    # ✅ Extract Material, Color, and Thickness from "Product Variant"
    df[['Material', 'Color_Thickness']] = df['Product Variant'].str.split(' - ', n=1, expand=True)
    df[['Color', 'Thickness']] = df['Color_Thickness'].str.rsplit(' ', n=1, expand=True)

    # ✅ Normalize Thickness Formatting
    df['Thickness'] = df['Thickness'].str.replace("cm", " cm", regex=False).str.strip()

    # ✅ Filter valid thicknesses
    valid_thicknesses = ["1.2 cm", "2 cm", "3 cm"]
    df = df[df['Thickness'].isin(valid_thicknesses)]

    # ✅ Convert numeric columns safely
    numeric_cols = ['Available Qty', 'SQ FT PRICE']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            st.warning(f"⚠️ Column '{col}' not found in the Excel file.")

    return df

df_inventory = load_data()

# ✅ If the data failed to load, stop execution
if df_inventory is None:
    st.stop()

# ✅ Initialize Admin Rates
if "fab_cost" not in st.session_state:
    st.session_state.fab_cost = 23  
if "install_cost" not in st.session_state:
    st.session_state.install_cost = 23  
if "ib_margin" not in st.session_state:
    st.session_state.ib_margin = 0.15  
if "sale_margin" not in st.session_state:
    st.session_state.sale_margin = 0.15  
if "admin_access" not in st.session_state:
    st.session_state.admin_access = False  

# 🎛 **Admin Panel (Password Protected)**
with st.sidebar:
    st.header("🔑 Admin Panel")

    if not st.session_state.admin_access:
        password_input = st.text_input("Enter Admin Password:", type="password", key="admin_password_input")
        if st.button("🔓 Login"):
            if password_input == ADMIN_PASSWORD:
                st.session_state.admin_access = True
                st.experimental_rerun()

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

        if st.button("🔒 Logout"):
            st.session_state.admin_access = False
            st.experimental_rerun()

# 🎨 **Main UI**
st.title("🛠 Countertop Cost Estimator")

square_feet = st.number_input("📐 Square Feet:", min_value=1, step=1)
thickness_options = ["1.2 cm", "2 cm", "3 cm"]
selected_thickness = st.selectbox("🔲 Thickness:", thickness_options, index=2)

available_colors = df_inventory[df_inventory["Thickness"] == selected_thickness]["Color"].dropna().unique()
selected_color = st.selectbox("🎨 Color:", sorted(available_colors)) if len(available_colors) > 0 else None

if st.button("📊 Estimate Cost"):
    if selected_color is None:
        st.error("❌ Please select a valid color.")
    else:
        selected_slabs = df_inventory[(df_inventory["Color"] == selected_color) & (df_inventory["Thickness"] == selected_thickness)]
        
        total_available_sqft = selected_slabs["Available Qty"].sum()
        required_sqft = square_feet * 1.2  # **20% Waste Factor**

        if required_sqft > total_available_sqft:
            st.error("❌ Not enough material available!")
        else:
            # ✅ Cost Calculations
            sq_ft_price = selected_slabs.iloc[0]["SQ FT PRICE"]
            material_cost = sq_ft_price * required_sqft
            fabrication_cost = st.session_state.fab_cost * required_sqft
            install_cost = st.session_state.install_cost * required_sqft
            ib_cost = (material_cost + fabrication_cost) * (1 + st.session_state.ib_margin)
            sale_price = (ib_cost + install_cost) * (1 + st.session_state.sale_margin)

            # ✅ Google Search URL
            google_url = f"https://www.google.com/search?tbm=isch&q={selected_color.replace(' ', '+')}+countertop"

            # ✅ Display Estimate
            st.success(f"💰 **Estimated Sale Price: ${sale_price:.2f}**")

            # ✅ View Images Button
            st.markdown(f"""
            <div style="text-align: center;">
                <a href="{google_url}" target="_blank" style="
                    display: inline-block;
                    background-color: #007AFF;
                    color: white;
                    font-size: 18px;
                    font-weight: 500;
                    padding: 10px 20px;
                    border-radius: 8px;
                    text-decoration: none;
                    margin-top: 10px;">
                    🔍 View Images
                </a>
            </div>
            """, unsafe_allow_html=True)

            # ✅ Full Cost Breakdown
            serial_numbers = ", ".join(selected_slabs["Serial Number"].astype(str).unique())
            with st.expander("🧐 Show Full Cost Breakdown"):
                st.markdown(f"""
                - **Serial Numbers Used:** {serial_numbers}  
                - **Material Cost:** ${material_cost:.2f}  
                - **Fabrication Cost:** ${fabrication_cost:.2f}  
                - **IB Cost:** ${ib_cost:.2f}  
                - **Installation Cost:** ${install_cost:.2f}  
                - **Total Sale Price:** ${sale_price:.2f}  
                """)