"""Shared Gmail-API / SMTP / Slack transport for advisor emails.

Primary path: Gmail API using the shared Google OAuth token (needs the gmail.send scope) —
works from cloud IPs (GitHub Actions). SMTP is a local-only fallback (Google blocks
app-password login from datacenter IPs). Slack is the last resort when email itself is down.

Shared by weekly_advisor.py and seo_advisor.py so both reports use one send path.
"""
from __future__ import annotations

import os
import smtplib
import ssl
import sys
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

# Use `or` (not getenv defaults): CI passes these as empty strings when the secret is
# unset, and an empty string is not the same as an absent key.
EMAIL_FROM = os.getenv("GMAIL_ADDRESS") or "igormscaldini@gmail.com"
# Gmail app passwords are 16 chars; Google displays them in 4 space-separated groups.
# Strip spaces so the secret works whether pasted with or without them.
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()

TRANSPORT_FIX = (
    "Email send failed. The Gmail API needs the gmail.send scope on the shared Google token — "
    "re-run `python auth_ga4.py` to re-consent, then update the GOOGLE_TOKEN_JSON secret. "
    "(SMTP fallback only works from your local IP.)"
)


def build_mime(subject: str, body: str, to_addr: str, from_label: str, header_tag: str) -> MIMEText:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"{from_label} <{EMAIL_FROM}>"
    msg["To"] = to_addr
    # Marks this as advisor-sent so the reply poller never tries to "answer" our own report.
    msg["X-CT-Advisor"] = header_tag
    return msg


def send_via_gmail_api(subject: str, body: str, to_addr: str, from_label: str, header_tag: str) -> None:
    import base64

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    from ga4_client import TOKEN_FILE

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
    raw = base64.urlsafe_b64encode(build_mime(subject, body, to_addr, from_label, header_tag).as_bytes()).decode()
    svc.users().messages().send(userId="me", body={"raw": raw}).execute()


def send_via_smtp(subject: str, body: str, to_addr: str, from_label: str, header_tag: str) -> None:
    """Fallback transport (works locally; Google blocks it from cloud IPs)."""
    if not GMAIL_APP_PASSWORD:
        raise RuntimeError("GMAIL_APP_PASSWORD not set")
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
        server.login(EMAIL_FROM, GMAIL_APP_PASSWORD)
        server.sendmail(
            EMAIL_FROM, [to_addr], build_mime(subject, body, to_addr, from_label, header_tag).as_string()
        )


def send_email(
    subject: str,
    body: str,
    to_addr: str,
    from_label: str = "CT Growth Advisor",
    header_tag: str = "report",
) -> None:
    """Try the Gmail API first, then SMTP. Raise with both errors if both fail."""
    try:
        send_via_gmail_api(subject, body, to_addr, from_label, header_tag)
        return
    except Exception as api_err:  # noqa: BLE001
        print(f"[warn] Gmail API send failed: {api_err}", file=sys.stderr)
        try:
            send_via_smtp(subject, body, to_addr, from_label, header_tag)
            return
        except Exception as smtp_err:  # noqa: BLE001
            raise RuntimeError(
                f"Gmail API failed ({api_err}); SMTP fallback failed ({smtp_err})"
            ) from smtp_err


def slack_fallback(reason: str, report_label: str, extra_fix: str = "") -> bool:
    """Last resort when email transport is down. Returns True if Slack accepted the message."""
    token = os.getenv("SLACK_BOT_TOKEN", "").strip()
    channel = os.getenv("SLACK_DEFAULT_CHANNEL", "").strip()
    if not token or not channel:
        return False
    import requests

    text = (
        f":warning: {report_label} could not be emailed.\n"
        f"Reason: {reason}\n"
        f"Fix: {TRANSPORT_FIX} {extra_fix}"
    )
    try:
        r = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": channel, "text": text},
            timeout=15,
        )
        return r.ok and r.json().get("ok", False)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] slack fallback failed: {e}", file=sys.stderr)
        return False
