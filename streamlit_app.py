import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz # For timezone-aware datetime objects
from datetime import datetime
# import requests # Commented out: was primarily for Auth0 token exchange. Uncomment if needed for other API calls.
# import jwt # Commented out: PyJWT was for Auth0 token decoding.

# --- Configuration Loading (using Streamlit Secrets) ---
try:
    # Brevo SMTP Config
    SMTP_SERVER = st.secrets["SMTP_SERVER"]
    SMTP_PORT = st.secrets["SMTP_PORT"]
    EMAIL_USER = st.secrets["EMAIL_USER"]
    EMAIL_PASSWORD = st.secrets["EMAIL_PASSWORD"]
    SENDER_FROM_EMAIL = st.secrets["SENDER_FROM_EMAIL"]
    QUOTE_TRACKING_CC_EMAIL = st.secrets["QUOTE_TRACKING_CC_EMAIL"]

    # GCP Service Account Config for gspread
    gcp_creds_dict = dict(st.secrets["gcp_service_account"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file" # if you need to create new sheets
    ]
    google_credentials = Credentials.from_service_account_info(gcp_creds_dict, scopes=scopes)
    gc = gspread.authorize(google_credentials)

    # Auth0 Config - REMOVED/COMMENTED OUT
    # AUTH0_DOMAIN = st.secrets["AUTH0_DOMAIN"]
    # AUTH0_CLIENT_ID = st.secrets["AUTH0_CLIENT_ID"]
    # AUTH0_CLIENT_SECRET = st.secrets["AUTH0_CLIENT_SECRET"]
    # AUTH0_CALLBACK_URL = st.secrets["AUTH0_CALLBACK_URL"]
    # AUTH0_AUDIENCE = st.secrets.get("AUTH0_AUDIENCE", "")

except KeyError as e:
    st.error(f"Missing secret: {e}. Please check your .streamlit/secrets.toml file or Streamlit Cloud app settings.")
    st.stop()
except Exception as e:
    st.error(f"Error loading configurations: {e}")
    st.stop()

# --- Google Sheets Functions ---
def get_sheet_data(sheet_url, worksheet_name):
    try:
        spreadsheet = gc.open_by_url(sheet_url)
        worksheet = spreadsheet.worksheet(worksheet_name)
        data = worksheet.get_all_records() # Gets data as a list of dictionaries
        df = pd.DataFrame(data)
        return df
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Spreadsheet not found at URL: {sheet_url}")
        return pd.DataFrame()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Worksheet '{worksheet_name}' not found in the spreadsheet.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"An error occurred with Google Sheets: {e}")
        return pd.DataFrame()

# --- Email Function ---
def send_email(to_email, subject, body_html, cc_email=None):
    msg = MIMEMultipart('alternative')
    msg['From'] = SENDER_FROM_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject
    if cc_email:
        msg['Cc'] = cc_email

    msg.attach(MIMEText(body_html, 'html'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            recipients = [to_email]
            if cc_email:
                recipients.append(cc_email)
            server.sendmail(SENDER_FROM_EMAIL, recipients, msg.as_string())
        st.success(f"Email sent to {to_email} (CC: {cc_email if cc_email else 'None'})")
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

# --- Auth0 Helper Functions (Conceptual) ---
# ALL AUTH0 HELPER FUNCTIONS REMOVED/COMMENTED OUT
# def get_auth_url(): ...
# def exchange_code_for_tokens(auth_code): ...
# def decode_jwt(token): ...

# --- Streamlit App UI ---
st.set_page_config(page_title="My App without Login", layout="wide")
st.title("Application Dashboard")

# Session state for user info and tokens - REMOVED/COMMENTED OUT
# if 'user_info' not in st.session_state:
#     st.session_state.user_info = None
# if 'id_token' not in st.session_state:
#     st.session_state.id_token = None
# if 'access_token' not in st.session_state:
#     st.session_state.access_token = None


# --- Authentication Flow ---
# ALL AUTHENTICATION FLOW LOGIC (LOGIN/LOGOUT BUTTONS, TOKEN EXCHANGE) REMOVED
# query_params = st.query_params
# auth_code = query_params.get("code")
# ... etc ...

# --- Main Application Area (Now always accessible) ---
st.header("Main Application Features")

# Example: Google Sheets Interaction
st.subheader("Google Sheets Data")
sheet_url_input = st.text_input(
    "Enter Google Sheet URL (ensure it's shared with the service account):",
    "YOUR_DEFAULT_SHEET_URL_HERE_OR_LEAVE_EMPTY" # Replace with a default or leave empty
)
worksheet_name_input = st.text_input("Enter Worksheet Name:", "Sheet1")

if st.button("Load Data from Sheet"):
    if sheet_url_input and worksheet_name_input:
        sheet_df = get_sheet_data(sheet_url_input, worksheet_name_input)
        if not sheet_df.empty:
            st.dataframe(sheet_df)
    else:
        st.warning("Please provide both Sheet URL and Worksheet Name.")

# Example: Email Sending
st.subheader("Send Test Email")
recipient_email = st.text_input("Recipient Email:", "test@example.com") # Replace with a default or leave empty
email_subject = st.text_input("Email Subject:", "Test Email from Streamlit")
email_body = st.text_area("Email Body (HTML):", "<p>This is a <b>test email</b> sent from the Streamlit app.</p>")

if st.button("Send Email"):
    if recipient_email and email_subject and email_body:
        send_email(recipient_email, email_subject, email_body, cc_email=QUOTE_TRACKING_CC_EMAIL)
    else:
        st.warning("Please fill in all email fields.")

# Display of user information and tokens - REMOVED
# st.subheader("User Information (from ID Token)")
# st.json(st.session_state.user_info)
# if st.session_state.access_token:
#    st.subheader("Access Token (first 20 chars for brevity):")
#    st.text(st.session_state.access_token[:20] + "...")

# --- Footer Example ---
st.markdown("---")
# Making sure pytz is available for this line, or using a timezone-naive datetime
try:
    # Using a common timezone; adjust if needed or make timezone-naive
    app_timezone = pytz.timezone('America/Vancouver') # Or your preferred timezone
    current_year = datetime.now(app_timezone).year
except NameError: # If pytz was also commented out due to not being used elsewhere
    current_year = datetime.now().year
st.markdown(f"© {current_year} Your Company Name")

