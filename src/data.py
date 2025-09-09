import json
import pandas as pd
import streamlit as st
import gspread


@st.cache_data(show_spinner=False)
def load_salespeople_sheet(spreadsheet_id: str, tab_name: str) -> pd.DataFrame:
    """Load a worksheet from a Google Sheet and return it as a DataFrame."""
    try:
        raw = st.secrets["gcp_service_account"]
        creds = json.loads(raw) if isinstance(raw, str) else raw
        gc = gspread.service_account_from_dict(creds)
        ws = gc.open_by_key(spreadsheet_id).worksheet(tab_name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"❌ Could not load Google Sheet tab '{tab_name}': {e}")
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_inventory_csv(url: str) -> pd.DataFrame:
    """Fetch the inventory CSV published from PIO."""
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"❌ Could not fetch inventory CSV: {e}")
        return pd.DataFrame()


def get_fab_plant(branch: str) -> str:
    """Return the fabrication plant for a given branch."""
    return "Abbotsford" if branch in ["Vernon", "Victoria", "Vancouver"] else "Saskatoon"
