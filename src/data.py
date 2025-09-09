import json
import pandas as pd
import gspread
import streamlit as st


def load_salespeople_sheet(spreadsheet_id: str, tab_name: str) -> pd.DataFrame:
    """Load a tab from a Google Sheet into a DataFrame."""
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


def load_inventory_csv(url: str) -> pd.DataFrame:
    """Fetch inventory data from a CSV URL."""
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"❌ Could not fetch inventory CSV: {e}")
        return pd.DataFrame()


def get_fab_plant(branch: str) -> str:
    """If branch is one of (Vernon, Victoria, Vancouver), return 'Abbotsford'; else 'Saskatoon'."""
    return "Abbotsford" if branch in ["Vernon", "Victoria", "Vancouver"] else "Saskatoon"
