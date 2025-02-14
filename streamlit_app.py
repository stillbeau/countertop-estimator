import pandas as pd
import streamlit as st
import requests
from io import BytesIO

# ✅ Correct GitHub RAW File URL
file_url = "https://raw.githubusercontent.com/stillbeau/countertop-estimator/main/deadfeb.xlsx"

# 🔑 Admin Password (Change this!)
ADMIN_PASSWORD = "floform2024"

# ✅ Initialize session state for settings
if "sq_ft_prices" not in st.session_state:
    st.session_state.sq_ft_prices = {}  # Store slab prices per color
if "install_cost" not in st.session_state:
    st.session_state.install_cost = 23  # Default install cost
if "fabrication_cost" not in st.session_state:
    st.session_state.fabrication_cost = 23  # Default fab cost
if "admin_access" not in st.session_state:
    st.session_state.admin_access = False  # Admin access flag
if "available_colors" not in st.session_state:
    st.session_state.available_colors = []  # Store colors from Excel

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

        # ✅ Extract Material, Color, and Thickness from "Product Variant"
        df[['Material', 'Color_Thickness']] = df['Product Variant'].str.split(' - ', n=1, expand=True)
        df[['Color', 'Thickness']] = df['Color_Thickness'].str.rsplit(' ', n=1, expand=True)

        # ✅ Normalize Thickness Formatting
        df['Thickness'] = df['Thickness'].str.replace("cm", " cm", regex=False).str.strip()

        # ✅ Filter thickness to only valid options (1.2 cm, 2 cm, 3 cm)
        valid_thicknesses = ["1.2 cm", "2 cm", "3 cm"]
        df = df[df['Thickness'].isin(valid_thicknesses)]

        # ✅ Store unique colors in session state
        st.session_state.available_colors = sorted(df['Color'].dropna().unique())

        return df[['Color', 'Thickness', 'Material']]
    
    except Exception as e:
        st.error(f"❌ Error while loading the file: {e}")
        return None

df_inventory = load_data()

# 🎨 **Admin Panel for Pricing Settings**
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
        st.subheader("💰 Update Pricing")
        
        # Editable install cost
        st.session_state.install_cost = st.number_input("🚚 Install Cost per sq ft:", 
                                                        value=st.session_state.install_cost, step=1)
        
        # Editable fabrication cost
        st.session_state.fabrication_cost = st.number_input("🛠 Fabrication Cost per sq ft:", 
                                                             value=st.session_state.fabrication_cost, step=1)

        # Editable slab pricing per color
        new_price_color = st.selectbox("🎨 Select Color to Update:", st.session_state.available_colors)
        new_price_value = st.number_input("💰 Slab Price (Total Slab Cost in $):", min_value=0.0, step=50.0)
        new_slab_sq_ft = st.number_input("📏 Slab Size in Square Feet:", min_value=1.0, step=1.0)

        if st.button("✅ Update Price"):
            if new_price_color and new_price_value and new_slab_sq_ft:
                st.session_state.sq_ft_prices[new_price_color] = new_price_value / new_slab_sq_ft
                st.success(f"✅ Price updated: {new_price_color} → ${st.session_state.sq_ft_prices[new_price_color]:.2f}/sq ft")
            else:
                st.error("⚠️ Please enter a valid color, slab price, and slab size.")

# 🎨 **UI Setup**
st.title("🛠 Countertop Cost Estimator")
st.markdown("### Select your requirements and get a cost estimate!")

# 📏 **Square Feet Input**
square_feet = st.number_input("📐 Enter Square Feet Needed:", min_value=1, step=1)

# 🔲 **Thickness Dropdown**
thickness_options = ["1.2 cm", "2 cm", "3 cm"]
selected_thickness = st.selectbox("🔲 Select Thickness:", thickness_options)

# 🎨 **Color Dropdown (Auto-Populated from Excel)**
if st.session_state.available_colors:
    selected_color = st.selectbox("🎨 Select Color:", st.session_state.available_colors)
else:
    st.warning("⚠️ No colors available. Please check the Excel file or update pricing in Admin Panel.")
    selected_color = None

# 📊 **Estimate Cost Button**
if st.button("📊 Estimate Cost"):
    if not selected_color or selected_color not in st.session_state.sq_ft_prices:
        st.error("❌ No price set for this color. Update it in Admin Panel.")
    else:
        # 🔢 **Dynamic Pricing Calculations**
        sq_ft_price = st.session_state.sq_ft_prices[selected_color]  # Price per sq ft
        required_sqft = square_feet * 1.2  # **20% Waste Factor**
        fabrication_cost = st.session_state.fabrication_cost
        install_cost = st.session_state.install_cost

        ib_sq_ft_price = (sq_ft_price + fabrication_cost) * 1.2
        sale_price = (ib_sq_ft_price + install_cost) * 1.2 * required_sqft

        # ✅ **Display Final Price**
        st.success(f"💰 **Estimated Sale Price: ${sale_price:.2f}**")

        # 🧐 **Expander for Cost Breakdown**
        with st.expander("🧐 Show Full Cost Breakdown"):
            st.write(f"📌 **Material**: {selected_color} ({selected_thickness})")
            st.write(f"🔲 **Required Sq Ft (20% waste included)**: {required_sqft:.2f} sq ft")
            
            st.markdown(f"""
            **💰 Cost Breakdown**  
            - **Material Cost (per sq ft):** ${sq_ft_price:.2f}  
            - **Fabrication Cost (per sq ft):** ${fabrication_cost:.2f}  
            - **Installation Cost (per sq ft):** ${install_cost:.2f}  
            - **IB Cost per sq ft:** ${ib_sq_ft_price:.2f}  
            - **Total Sale Price:** ${sale_price:.2f}  
            """)

