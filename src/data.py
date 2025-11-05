import json
import pandas as pd
import gspread
from gspread import Client
from gspread.exceptions import WorksheetNotFound
import streamlit as st


def _open_worksheet_by_title(gc: Client, spreadsheet_id: str, tab_name: str):
    """Return the worksheet matching ``tab_name`` (case/space insensitive)."""

    def _normalize(name: str) -> str:
        return " ".join(name.strip().split()).lower()

    sh = gc.open_by_key(spreadsheet_id)

    try:
        return sh.worksheet(tab_name)
    except WorksheetNotFound:
        normalized_target = _normalize(tab_name)
        for ws in sh.worksheets():
            if _normalize(ws.title) == normalized_target:
                return ws
        raise


def load_salespeople_sheet(spreadsheet_id: str, tab_name: str) -> pd.DataFrame:
    """Load a tab from a Google Sheet into a DataFrame."""
    try:
        raw = st.secrets["gcp_service_account"]
        creds = json.loads(raw) if isinstance(raw, str) else raw
        gc = gspread.service_account_from_dict(creds)
        ws = _open_worksheet_by_title(gc, spreadsheet_id, tab_name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = df.columns.str.strip()
        return df
    except WorksheetNotFound:
        try:
            sh = gc.open_by_key(spreadsheet_id)
            available = ", ".join(ws.title for ws in sh.worksheets())
        except Exception:
            available = "unavailable"
        st.error(
            "❌ Could not find the Google Sheet tab "
            f"'{tab_name}'. Available tabs: {available}"
        )
        return pd.DataFrame()
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
