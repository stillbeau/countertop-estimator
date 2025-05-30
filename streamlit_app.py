import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz # For timezone-aware datetime objects
import requests # For making HTTP requests (e.g., to Auth0 /token endpoint)
import jwt # PyJWT for handling JSON Web Tokens
from datetime import datetime

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
    # gspread expects a dictionary for service account credentials
    gcp_creds_dict = dict(st.secrets["gcp_service_account"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file" # if you need to create new sheets
    ]
    google_credentials = Credentials.from_service_account_info(gcp_creds_dict, scopes=scopes)
    gc = gspread.authorize(google_credentials)

    # Auth0 Config
    AUTH0_DOMAIN = st.secrets["AUTH0_DOMAIN"]
    AUTH0_CLIENT_ID = st.secrets["AUTH0_CLIENT_ID"]
    AUTH0_CLIENT_SECRET = st.secrets["AUTH0_CLIENT_SECRET"]
    AUTH0_CALLBACK_URL = st.secrets["AUTH0_CALLBACK_URL"]
    AUTH0_AUDIENCE = st.secrets.get("AUTH0_AUDIENCE", "") # Optional: API audience

except KeyError as e:
    st.error(f"Missing secret: {e}. Please check your .streamlit/secrets.toml file.")
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
            server.starttls()  # Secure the connection
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
# This is a simplified conceptualization. Real Auth0 flow is more complex.

def get_auth_url():
    # For a more robust solution, consider using an OAuth library
    auth_endpoint = f"https://{AUTH0_DOMAIN}/authorize"
    params = {
        "response_type": "code", # or "token id_token" for implicit flow (less secure for web apps)
        "client_id": AUTH0_CLIENT_ID,
        "redirect_uri": AUTH0_CALLBACK_URL,
        "scope": "openid profile email", # Standard scopes
        "audience": AUTH0_AUDIENCE, # If you have an API audience
        "state": "your_random_state_string" # For CSRF protection, generate and store securely
    }
    import urllib.parse
    return f"{auth_endpoint}?{urllib.parse.urlencode(params)}"

def exchange_code_for_tokens(auth_code):
    token_endpoint = f"https://{AUTH0_DOMAIN}/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": AUTH0_CLIENT_ID,
        "client_secret": AUTH0_CLIENT_SECRET, # Server-side exchange
        "code": auth_code,
        "redirect_uri": AUTH0_CALLBACK_URL,
    }
    headers = {"content-type": "application/x-www-form-urlencoded"}
    try:
        response = requests.post(token_endpoint, data=payload, headers=headers)
        response.raise_for_status() # Raise an exception for bad status codes
        return response.json() # Contains access_token, id_token, etc.
    except requests.exceptions.RequestException as e:
        st.error(f"Error exchanging code for tokens: {e}")
        if e.response is not None:
            st.error(f"Response content: {e.response.text}")
        return None

def decode_jwt(token):
    try:
        # To verify the signature, you need the JWKS (JSON Web Key Set) from Auth0
        # This involves fetching https://{AUTH0_DOMAIN}/.well-known/jwks.json
        # The pyjwt library can use this to verify the token's signature.
        # For simplicity here, we'll decode without full verification,
        # BUT IN PRODUCTION, YOU MUST VERIFY THE SIGNATURE.
        
        # Simplified: Get the key from JWKS URI
        jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
        jwks_client = jwt.PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        decoded_token = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"], # Algorithm used by Auth0
            audience=AUTH0_AUDIENCE if AUTH0_AUDIENCE else None, # Validate audience if provided
            issuer=f"https://{AUTH0_DOMAIN}/"
        )
        return decoded_token
    except jwt.ExpiredSignatureError:
        st.error("Token has expired.")
        return None
    except jwt.InvalidTokenError as e:
        st.error(f"Invalid token: {e}")
        return None
    except Exception as e:
        st.error(f"Error decoding JWT: {e}")
        return None

# --- Streamlit App UI ---
st.set_page_config(page_title="My App with Integrations", layout="wide")
st.title("Application Dashboard")

# Initialize session state for user info and tokens
if 'user_info' not in st.session_state:
    st.session_state.user_info = None
if 'id_token' not in st.session_state:
    st.session_state.id_token = None
if 'access_token' not in st.session_state:
    st.session_state.access_token = None


# --- Authentication Flow ---
# 1. Check for Auth code in URL (after redirect from Auth0)
query_params = st.query_params # Use st.query_params for newer Streamlit versions
auth_code = query_params.get("code")

if not st.session_state.user_info and auth_code:
    with st.spinner("Authenticating..."):
        tokens = exchange_code_for_tokens(auth_code)
        if tokens and "id_token" in tokens:
            st.session_state.id_token = tokens["id_token"]
            st.session_state.access_token = tokens.get("access_token") # May not always be present
            user_info_from_token = decode_jwt(st.session_state.id_token)
            if user_info_from_token:
                st.session_state.user_info = user_info_from_token
                # Clear the code from URL to prevent re-processing
                # This basic approach might not always work perfectly depending on server/proxy.
                # A more robust way is to redirect to the app's base URL without query params.
                st.query_params.clear() # Clear query params
                st.rerun() # Rerun to reflect logged-in state and clear URL artifacts
            else:
                st.error("Failed to decode token or token was invalid.")
        else:
            st.error("Could not retrieve tokens from Auth0.")

# 2. Display Login or Logout based on session state
if st.session_state.user_info:
    st.sidebar.subheader(f"Welcome, {st.session_state.user_info.get('name', st.session_state.user_info.get('email', 'User'))}!")
    if st.sidebar.button("Logout"):
        # Construct logout URL
        # Note: You might also want to call Auth0's logout endpoint to clear the Auth0 session
        logout_url_auth0 = f"https://{AUTH0_DOMAIN}/v2/logout?client_id={AUTH0_CLIENT_ID}&returnTo={AUTH0_CALLBACK_URL.split('/callback')[0]}" # Redirect to app home
        
        # Clear local session
        st.session_state.user_info = None
        st.session_state.id_token = None
        st.session_state.access_token = None
        st.query_params.clear() # Clear any remaining query params

        # Redirect to Auth0 logout, then back to the app
        # Using st.markdown for a link click, as st.redirect is not for external URLs.
        # A more seamless experience might involve JavaScript.
        st.sidebar.markdown(f'[Click here to complete logout]({logout_url_auth0})', unsafe_allow_html=True)
        st.info("Please click the link above to complete logout from Auth0.")
        st.rerun()

else:
    auth_url = get_auth_url()
    # Using st.link_button for a direct navigation button
    st.sidebar.link_button("Login with Auth0", auth_url)


# --- Main Application Area (Only if logged in) ---
if st.session_state.user_info:
    st.header("Main Application Features")

    # Example: Google Sheets Interaction
    st.subheader("Google Sheets Data")
    sheet_url_input = st.text_input("Enter Google Sheet URL (ensure it's shared with service account):", "YOUR_DEFAULT_SHEET_URL_HERE_OR_LEAVE_EMPTY")
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
    recipient_email = st.text_input("Recipient Email:", "test@example.com")
    email_subject = st.text_input("Email Subject:", "Test Email from Streamlit")
    email_body = st.text_area("Email Body (HTML):", "<p>This is a <b>test email</b> sent from the Streamlit app.</p>")

    if st.button("Send Email"):
        if recipient_email and email_subject and email_body:
            send_email(recipient_email, email_subject, email_body, cc_email=QUOTE_TRACKING_CC_EMAIL)
        else:
            st.warning("Please fill in all email fields.")
    
    st.subheader("User Information (from ID Token)")
    st.json(st.session_state.user_info)

    if st.session_state.access_token:
        st.subheader("Access Token (first 20 chars for brevity):")
        st.text(st.session_state.access_token[:20] + "...")
        # Here you could use the access_token to call a protected API (if AUTH0_AUDIENCE was set)
        # e.g. requests.get(YOUR_API_ENDPOINT, headers={"Authorization": f"Bearer {st.session_state.access_token}"})

else:
    st.info("Please login using the sidebar to access the application features.")

# --- Footer Example ---
st.markdown("---")
st.markdown(f"© {datetime.now(pytz.timezone('America/Vancouver')).year} Your Company Name")

