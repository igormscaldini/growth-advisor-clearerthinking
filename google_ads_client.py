"""Shared Google Ads client — composes credentials from .env + the shared OAuth token."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google.ads.googleads.client import GoogleAdsClient

load_dotenv()

ROOT = Path(__file__).parent
OAUTH_CLIENT_FILE = (ROOT / os.getenv("GA4_OAUTH_CLIENT_FILE", "./secrets/oauth-client.json")).resolve()
TOKEN_FILE = (ROOT / os.getenv("GA4_TOKEN_FILE", "./secrets/ga4-token.json")).resolve()

DEVELOPER_TOKEN = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
CUSTOMER_ID = os.getenv("GOOGLE_ADS_CUSTOMER_ID")
LOGIN_CUSTOMER_ID = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID")


def _load_oauth_client_secrets() -> tuple[str, str]:
    if not OAUTH_CLIENT_FILE.exists():
        raise SystemExit(f"Missing {OAUTH_CLIENT_FILE}")
    data = json.loads(OAUTH_CLIENT_FILE.read_text())
    bucket = data.get("installed") or data.get("web") or {}
    return bucket["client_id"], bucket["client_secret"]


def _load_refresh_token() -> str:
    if not TOKEN_FILE.exists():
        raise SystemExit(f"Missing {TOKEN_FILE}. Run `python auth_ga4.py` first.")
    data = json.loads(TOKEN_FILE.read_text())
    if not data.get("refresh_token"):
        raise SystemExit("No refresh_token in token file. Re-run `python auth_ga4.py`.")
    return data["refresh_token"]


def get_client() -> GoogleAdsClient:
    if not DEVELOPER_TOKEN:
        raise SystemExit("GOOGLE_ADS_DEVELOPER_TOKEN not set in .env")
    if not LOGIN_CUSTOMER_ID:
        raise SystemExit("GOOGLE_ADS_LOGIN_CUSTOMER_ID not set in .env")

    client_id, client_secret = _load_oauth_client_secrets()
    refresh_token = _load_refresh_token()

    return GoogleAdsClient.load_from_dict({
        "developer_token": DEVELOPER_TOKEN,
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "login_customer_id": LOGIN_CUSTOMER_ID,
        "use_proto_plus": True,
    })
