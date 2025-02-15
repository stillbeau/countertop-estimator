import pandas as pd
import streamlit as st
import requests
from io import BytesIO

# ✅ GitHub RAW File URL
file_url = "https://raw.githubusercontent.com/stillbeau/countertop-estimator/main/deadfeb.xlsx"

# 🔑 Admin Password
ADMIN_PASSWORD = "floform2024"

# ✅ Initialize session state for settings
if "install_cost" not in st.session_state:
    st.session_state.install_cost = 23  # Default install cost
if "fabrication_cost" not in st.session_state:
    st.session_state.fabrication_cost = 23  # Default fab cost
if "margin" not in st.session_state:
    st.session_state.margin = 1.2  # Default margin multiplier
if "admin_access" not in st.session_state:
    st.session_state.admin_access = False  # Admin access flag
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
            df[col] = pd.to_numeric(df[col], errors='coerce')

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
        
        # Editable install cost
        st.session_state.install_cost = st.number_input("🚚 Install & Template Cost per sq ft:", 
                                                        value=st.session_state.install_cost, step=1)
        
        # Editable fabrication cost
        st.session_state.fabrication_cost = st.number_input("🛠 Fabrication Cost per sq ft:", 
                                                             value=st.session_state.fabrication_cost, step=1)

        # Editable margin multiplier
        st.session_state.margin = st.number_input("📈 Margin Multiplier:", 
                                                  value=st.session_state.margin, step=0.1)

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
        # 🔢 **Get Slab Price from Excel**
        selected_slab = df_inventory[
            (df_inventory["Color"] == selected_color) & (df_inventory["Thickness"] == selected_thickness)
        ]

        if selected_slab.empty:
            st.error("❌ No slab found for the selected color and thickness.")
        else:
            selected_slab = selected_slab.iloc[0]  # Get first match

            available_sqft = selected_slab["Available Qty"]
            sq_ft_price = selected_slab["SQ FT PRICE"]  # From Excel

            required_sqft = square_feet * 1.2  # **20% Waste Factor**
            
            if required_sqft > available_sqft:
                st.error("❌ Not enough material available for this selection (including 20% waste).")
            else:
                # **Cost Calculations**
                fabrication_cost = st.session_state.fabrication_cost
                install_cost = st.session_state.install_cost
                margin = st.session_state.margin

                material_cost = sq_ft_price * required_sqft
                total_fabrication_cost = fabrication_cost * required_sqft
                total_install_cost = install_cost * required_sqft

                ib_sq_ft_price = (sq_ft_price + fabrication_cost) * margin
                total_ib_cost = ib_sq_ft_price * required_sqft

                sale_price = (ib_sq_ft_price + install_cost) * margin * required_sqft

                # ✅ **Display Final Price**
                st.success(f"💰 **Estimated Sale Price: ${sale_price:.2f}**")

                # 🧐 **Expander for Cost Breakdown**
                with st.expander("🧐 Show Full Cost Breakdown"):
                    st.write(f"📌 **Material**: {selected_color} ({selected_thickness})")
                    st.write(f"🔲 **Required Sq Ft (20% waste included)**: {required_sqft:.2f} sq ft")
                    
                    st.markdown(f"""
                    **💰 Cost Breakdown**  
                    - **Material Cost:** ${material_cost:.2f}  
                    - **Fabrication Cost:** ${total_fabrication_cost:.2f}  
                    - **Installation Cost:** ${total_install_cost:.2f}  
                    - **IB Cost (Material + Fab * Margin):** ${total_ib_cost:.2f}  
                    - **Total Sale Price:** ${sale_price:.2f}  
                    """)