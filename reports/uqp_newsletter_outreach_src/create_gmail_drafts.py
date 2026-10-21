"""Create one Gmail draft per row of the outreach CSV in Igor's mailbox (never sends).

Each draft: To = the row's Email, Subject + plain-text body from the sheet, labelled
"UQP newsletter outreach". Idempotent: a draft whose (to, subject) already exists among
the mailbox's drafts is skipped, so re-running after an edit only adds what is missing.

Run: .venv/bin/python reports/uqp_newsletter_outreach_src/create_gmail_drafts.py ~/Downloads/uqp_newsletter_outreach_2026-10-21.csv
"""
from __future__ import annotations

import base64
import csv
import sys
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

LABEL = "UQP newsletter outreach"


def build_draft_message(to_addr: str, subject: str, body: str) -> dict:
    """Gmail API message resource for a plain-text draft. Pure, tested."""
    msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = to_addr
    msg["Subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    return {"raw": raw}


def rows_to_draft(rows: list[dict], existing: set[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    """Split CSV rows into (to create, skipped as already drafted). Pure, tested."""
    todo, skipped = [], []
    for r in rows:
        key = (r["Email"].strip().lower(), r["Subject"].strip())
        if not r["Email"].strip() or "@" not in r["Email"]:
            skipped.append(r)
        elif key in existing:
            skipped.append(r)
        else:
            todo.append(r)
    return todo, skipped


def gmail_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from ga4_client import TOKEN_FILE
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def ensure_label(svc) -> str:
    labels = svc.users().labels().list(userId="me").execute()["labels"]
    for lab in labels:
        if lab["name"] == LABEL:
            return lab["id"]
    created = svc.users().labels().create(userId="me", body={
        "name": LABEL, "labelListVisibility": "labelShow", "messageListVisibility": "show"}).execute()
    return created["id"]


def existing_drafts(svc) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    page = None
    while True:
        res = svc.users().drafts().list(userId="me", maxResults=100, pageToken=page).execute()
        for d in res.get("drafts", []):
            m = svc.users().drafts().get(userId="me", id=d["id"], format="metadata",
                                         metadataHeaders=["To", "Subject"]).execute()["message"]
            h = {x["name"].lower(): x["value"] for x in m.get("payload", {}).get("headers", [])}
            out.add((h.get("to", "").strip().lower(), h.get("subject", "").strip()))
        page = res.get("nextPageToken")
        if not page:
            return out


def main() -> None:
    path = Path(sys.argv[1]).expanduser()
    rows = list(csv.DictReader(path.open()))
    svc = gmail_service()
    me = svc.users().getProfile(userId="me").execute()["emailAddress"]
    label_id = ensure_label(svc)
    todo, skipped = rows_to_draft(rows, existing_drafts(svc))
    print(f"mailbox {me}: {len(todo)} drafts to create, {len(skipped)} skipped")
    for r in todo:
        d = svc.users().drafts().create(userId="me", body={
            "message": build_draft_message(r["Email"].strip(), r["Subject"].strip(), r["Email draft"])}).execute()
        svc.users().messages().modify(userId="me", id=d["message"]["id"],
                                      body={"addLabelIds": [label_id]}).execute()
        print(f"  draft {d['id']}  tier {r['Tier']}  {r['University']}  -> {r['Email']}")


if __name__ == "__main__":
    main()
