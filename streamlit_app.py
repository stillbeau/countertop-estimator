import streamlit as st
import pandas as pd
import requests
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Email Configuration using st.secrets ---
SMTP_SERVER = st.secrets["SMTP_SERVER"]          
SMTP_PORT = int(st.secrets["SMTP_PORT"])         
EMAIL_USER = st.secrets["EMAIL_USER"]            
EMAIL_PASSWORD = st.secrets["EMAIL_PASSWORD"]
RECIPIENT_EMAIL = st.secrets.get("RECIPIENT_EMAIL", "sambeaumont@me.com")

# --- Other Configurations ---
MARKUP_FACTOR = 1.15            # 15% markup on material cost
INSTALL_COST_PER_SQFT = 23      # Installation cost per square foot
FABRICATION_COST_PER_SQFT = 23  # Fabrication cost per square foot
ADDITIONAL_IB_RATE = 0          # Extra rate added to material in IB calculation (per sq.ft)
GST_RATE = 0.05                 # 5% GST

# --- Google Sheets URL for cost data ---
GOOGLE_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ/export?format=csv"
)

@st.cache_data
def load_data():
    try:
        response = requests.get(GOOGLE_SHEET_URL)
        if response.status_code != 200:
            st.error("❌ Error loading the file. Check the Google Sheets URL.")
            return None
        df = pd.read_csv(io.StringIO(response.text))
        df.columns = df.columns.str.strip()
        df["Serialized On Hand Cost"] = (
            df["Serialized On Hand Cost"].replace("[\$,]", "", regex=True).astype(float)
        )
        df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors="coerce")
        df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors="coerce").fillna(0).astype(int)
        return df
    except Exception as e:
        st.error(f"❌ Failed to load data: {e}")
        return None

def calculate_costs(slab, sq_ft_needed):
    available_sq_ft = slab["Available Sq Ft"]
    # Material cost with markup (without fabrication)
    material_cost_with_markup = (slab["Serialized On Hand Cost"] * MARKUP_FACTOR / available_sq_ft) * sq_ft_needed
    # Fabrication cost
    fabrication_total = FABRICATION_COST_PER_SQFT * sq_ft_needed
    # Material & Fab total
    material_and_fab = material_cost_with_markup + fabrication_total
    # Installation cost
    install_cost = INSTALL_COST_PER_SQFT * sq_ft_needed
    # Total (before tax)
    total_cost = material_and_fab + install_cost
    # IB Calculation: base material (without markup) + fabrication cost + any additional rate
    ib_total_cost = ((slab["Serialized On Hand Cost"] / available_sq_ft) + FABRICATION_COST_PER_SQFT + ADDITIONAL_IB_RATE) * sq_ft_needed

    return {
        "available_sq_ft": available_sq_ft,
        "serial_number": slab["Serial Number"],
        "material_and_fab": material_and_fab,
        "install_cost": install_cost,
        "total_cost": total_cost,  # before tax
        "ib_cost": ib_total_cost
    }

def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = "Sc countertops <sam@sccountertops.ca>"
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

# --- UI: Title & Subtitle ---
st.title("Countertop Cost Estimator")
st.write("Get an accurate estimate for your custom countertop project")

# --- Load Data ---
with st.spinner("Loading data..."):
    df_inventory = load_data()
if df_inventory is None:
    st.error("Data could not be loaded.")
    st.stop()

# --- Filters for Slab Selection ---
location = st.selectbox("Select Location", options=["VER", "ABB"], index=0)
df_filtered = df_inventory[df_inventory["Location"] == location]
if df_filtered.empty:
    st.warning("No slabs found for the selected location.")
    st.stop()

thickness = st.selectbox("Select Thickness", options=["1.2cm", "2cm", "3cm"], index=1)
df_filtered = df_filtered[df_filtered["Thickness"] == thickness]
if df_filtered.empty:
    st.warning("No slabs match the selected thickness. Please adjust your filter.")
    st.stop()

df_filtered = df_filtered.copy()
df_filtered["Full Name"] = df_filtered["Brand"] + " - " + df_filtered["Color"]
selected_full_name = st.selectbox("Select Color", options=df_filtered["Full Name"].unique())

# --- Edge Profile and Google Search Link in Columns ---
col1, col2 = st.columns([2,1])
with col1:
    selected_edge_profile = st.selectbox("Select Edge Profile", options=["Bullnose", "Eased", "Beveled", "Ogee", "Waterfall"])
with col2:
    # Create a dynamic Google search query using only the brand + color
    google_search_query = f"{selected_full_name} countertop"
    search_url = f"https://www.google.com/search?q={google_search_query.replace(' ', '+')}"
    # Display as a markdown link (should appear as clickable text)
    st.write(f"[🔎 Google Image Search]({search_url})")

st.write("For more details on edge profiles, visit [Floform Edge Profiles](https://floform.com/countertops/edge-profiles/)")

selected_slab_df = df_filtered[df_filtered["Full Name"] == selected_full_name]
if selected_slab_df.empty:
    st.error("Selected slab not found. Please choose a different option.")
    st.stop()
selected_slab = selected_slab_df.iloc[0]

# --- Number Input for Square Footage (whole number, no decimal) ---
sq_ft_needed = st.number_input(
    "Enter Square Footage Needed", 
    min_value=1, 
    value=20, 
    step=1, 
    format="%d"  # Ensures no decimal places are displayed
)

# --- Calculate Costs ---
costs = calculate_costs(selected_slab, sq_ft_needed)
if sq_ft_needed * 1.2 > costs["available_sq_ft"]:
    st.error("⚠️ Not enough material available! Consider selecting another slab.")

sub_total = costs["total_cost"]
gst_amount = sub_total * GST_RATE
final_price = sub_total + gst_amount

# --- Display Final Price (Green Text) ---
st.markdown(f"### Your Total Price: :green[${final_price:,.2f}]")

with st.expander("View Subtotal & GST"):
    st.markdown(f"**Subtotal (before tax):** ${sub_total:,.2f}")
    st.markdown(f"**GST (5%):** ${gst_amount:,.2f}")

# --- Customer Contact Form ---
st.markdown("## Request a Quote")
st.write("Fill in your contact information below and we'll get in touch with you.")

with st.form("customer_form"):
    name = st.text_input("Name")
    email = st.text_input("Email")
    phone = st.text_input("Phone Number")
    address = st.text_area("Address")
    city = st.text_input("City")
    postal_code = st.text_input("Postal Code")
    submit_request = st.form_submit_button("Submit Request")

if submit_request:
    # Build full breakdown details for the email (not shown in the UI)
    breakdown_info = f"""
Countertop Cost Estimator Details:
--------------------------------------------------
- Slab: {selected_full_name}
- Edge Profile: {selected_edge_profile}
- Square Footage: {sq_ft_needed}
- Slab Sq Ft: {costs['available_sq_ft']:.2f} sq.ft
- Serial Number: {costs['serial_number']}
- Material & Fab: ${costs['material_and_fab']:,.2f}
- Installation: ${costs['install_cost']:,.2f}
- IB: ${costs['ib_cost']:,.2f}
- Subtotal (before tax): ${sub_total:,.2f}
- GST (5%): ${gst_amount:,.2f}
- Final Price: ${final_price:,.2f}
--------------------------------------------------
"""
    customer_info = f"""
Customer Information:
--------------------------------------------------
- Name: {name}
- Email: {email}
- Phone: {phone}
- Address: {address}
- City: {city}
- Postal Code: {postal_code}
--------------------------------------------------
"""
    email_body = f"New Countertop Request:\n\n{customer_info}\n\n{breakdown_info}"
    subject = f"New Countertop Request from {name}"
    if send_email(subject, email_body):
        st.success("Your request has been submitted successfully! We will contact you soon.")
        st.experimental_rerun()  # Clear the form by re-running the app
    else:
        st.error("Failed to send email. Please try again later.")