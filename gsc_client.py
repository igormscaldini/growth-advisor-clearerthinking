"""Shared Search Console client — reuses the OAuth token from auth_ga4.py."""
import os
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()

ROOT = Path(__file__).parent
TOKEN_FILE = (ROOT / os.getenv("GA4_TOKEN_FILE", "./secrets/ga4-token.json")).resolve()
SITE_URL = os.getenv("GSC_SITE_URL")  # e.g. https://www.clearerthinking.org/ or sc-domain:clearerthinking.org


def get_client():
    if not TOKEN_FILE.exists():
        raise SystemExit(f"Missing {TOKEN_FILE}. Run `python auth_ga4.py` first.")
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def list_sites() -> list[dict]:
    """Return all GSC properties this account has access to."""
    svc = get_client()
    return svc.sites().list().execute().get("siteEntry", [])
