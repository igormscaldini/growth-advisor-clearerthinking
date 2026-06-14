"""One-time OAuth flow for Google read-only access (GA4 + Search Console).

Opens a browser, walks you through Google sign-in + consent, and saves a
refresh token to secrets/ga4-token.json. After this runs once, the rest of
the codebase reuses the saved token without prompting again.

The token file is shared across Google services — GA4 and GSC clients both
load from it. If you add another Google scope later, append it to SCOPES
below and re-run this script.
"""
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/adwords",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/gmail.send",  # weekly advisor email (Gmail API send)
    "https://www.googleapis.com/auth/gmail.modify",  # reply handler: read replies + mark them read
]
CLIENT_FILE = Path(__file__).parent / "secrets" / "oauth-client.json"
TOKEN_FILE = Path(__file__).parent / "secrets" / "ga4-token.json"


def main() -> None:
    if not CLIENT_FILE.exists():
        raise SystemExit(f"Missing {CLIENT_FILE}. Download the OAuth client JSON from GCP and save it there.")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
    creds = flow.run_local_server(
        port=0,
        prompt="consent",
        access_type="offline",
        authorization_prompt_message="Opening browser for Google sign-in...",
        success_message="Authentication complete. You can close this tab.",
    )

    if not creds.refresh_token:
        raise SystemExit(
            "No refresh token returned. Re-run after revoking prior access at "
            "https://myaccount.google.com/permissions, or ensure the consent screen requests offline access."
        )

    TOKEN_FILE.write_text(creds.to_json())
    print(f"Saved credentials to {TOKEN_FILE}")
    print(f"Authenticated as: {creds.id_token if creds.id_token else '(account info not in token)'}")


if __name__ == "__main__":
    main()
