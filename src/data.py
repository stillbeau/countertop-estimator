import json
import pandas as pd
import gspread
from gspread import Client
from gspread.exceptions import WorksheetNotFound, APIError
import streamlit as st


def _open_worksheet_by_title(gc: Client, spreadsheet_id: str, tab_name: str):
    """Return the worksheet matching ``tab_name`` (case/space insensitive)."""

    def _normalize(name: str) -> str:
        return " ".join(name.strip().split()).lower()

    sh = gc.open_by_key(spreadsheet_id)
    normalized_target = _normalize(tab_name)

    try:
        return sh.worksheet(tab_name)
    except WorksheetNotFound:
        pass
    except APIError as err:
        status = getattr(getattr(err, "response", None), "status_code", None)
        if status == 404:
            # Treat the 404 like a WorksheetNotFound and fall back to manual search.
            pass
        else:
            raise

    for ws in sh.worksheets():
        if _normalize(ws.title) == normalized_target:
            return ws

    raise WorksheetNotFound(tab_name)


def _list_available_tabs(gc: Client | None, spreadsheet_id: str) -> list[str]:
    if gc is None:
        return []

    try:
        sh = gc.open_by_key(spreadsheet_id)
        return [ws.title for ws in sh.worksheets()]
    except Exception:
        return []


def load_salespeople_sheet(spreadsheet_id: str, tab_name: str) -> pd.DataFrame:
    """Load a tab from a Google Sheet into a DataFrame."""

    creds: dict = {}
    gc: Client | None = None

    try:
        raw = st.secrets["gcp_service_account"]
        creds = json.loads(raw) if isinstance(raw, str) else dict(raw)
        gc = gspread.service_account_from_dict(creds)
        ws = _open_worksheet_by_title(gc, spreadsheet_id, tab_name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = df.columns.str.strip()
        return df
    except WorksheetNotFound:
        available_tabs = _list_available_tabs(gc, spreadsheet_id)
        available = ", ".join(available_tabs) if available_tabs else "unavailable"
        st.error(
            "❌ Could not find the Google Sheet tab "
            f"'{tab_name}'. Available tabs: {available}"
        )
        return pd.DataFrame()
    except APIError as err:
        status = getattr(getattr(err, "response", None), "status_code", None)
        if status in (403, 404):
            client_email = creds.get("client_email", "the service account")
            st.error(
                "❌ Unable to access the Google Sheet. "
                "Please confirm the spreadsheet ID is correct and that "
                f"{client_email} has been granted access."
            )
            return pd.DataFrame()
        st.error(f"❌ Could not load Google Sheet tab '{tab_name}': {err}")
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
