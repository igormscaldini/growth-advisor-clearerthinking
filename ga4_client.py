"""Shared GA4 client — loads OAuth creds from secrets/ga4-token.json."""
import os
from pathlib import Path

from dotenv import load_dotenv
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.oauth2.credentials import Credentials

load_dotenv()

ROOT = Path(__file__).parent
TOKEN_FILE = (ROOT / os.getenv("GA4_TOKEN_FILE", "./secrets/ga4-token.json")).resolve()
PROPERTY_ID = os.getenv("GA4_PROPERTY_ID")


def get_client() -> BetaAnalyticsDataClient:
    if not TOKEN_FILE.exists():
        raise SystemExit(f"Missing {TOKEN_FILE}. Run `python auth_ga4.py` first.")
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    return BetaAnalyticsDataClient(credentials=creds)


def property_path() -> str:
    if not PROPERTY_ID:
        raise SystemExit("GA4_PROPERTY_ID not set in .env")
    return f"properties/{PROPERTY_ID}"
