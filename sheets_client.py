"""Shared Google Sheets client — reuses the OAuth token from auth_ga4.py."""
import os
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()

ROOT = Path(__file__).parent
TOKEN_FILE = (ROOT / os.getenv("GA4_TOKEN_FILE", "./secrets/ga4-token.json")).resolve()


def get_client():
    if not TOKEN_FILE.exists():
        raise SystemExit(f"Missing {TOKEN_FILE}. Run `python auth_ga4.py` first.")
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def get_values(spreadsheet_id: str, a1_range: str) -> list[list[str]]:
    """Read values from a single A1-style range. Empty trailing cells are dropped per row."""
    svc = get_client()
    resp = svc.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=a1_range).execute()
    return resp.get("values", [])
