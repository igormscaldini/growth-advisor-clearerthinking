"""Career Change Workshop sign-ups (GuidedTrack program 38791) -> Google Sheet.

The live path is the GuidedTrack *service "Sign-up sheet": every sign-up is POSTed to
/api/workshop-signup on the Vercel dashboard (frontend/app/api/workshop-signup/route.ts),
which upserts a row keyed on the email address. This script is the backfill and safety
net: it reads the program's CSV export and appends every real sign-up whose email is not
in the sheet yet (and refreshes name / question / source when they changed).

    python workshop_signups_sheet.py               # sync into $WORKSHOP_SHEET_ID
    python workshop_signups_sheet.py --dry-run     # show what would change
    python workshop_signups_sheet.py --new-sheet   # create the sheet and print its id

Runs in CI from .github/workflows/workshop-signups-sync.yml (schedule + manual).
Column layout is shared with the Vercel route: keep HEADER and the route's HEADER in step.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import warnings

warnings.filterwarnings("ignore")

PROGRAM_ID = 38791
EXPORT_URL = f"https://www.guidedtrack.com/programs/{PROGRAM_ID}/exports?export_format=csv"
SHEET_TAB = "Sign-ups"
HEADER = [
    "Signed up (UTC)",
    "Email",
    "First name",
    "Question for the session",
    "Source",
    "Registrant's local time",
    "Recorded by",
]
# src values used by test / probe runs (see the program's HOW TO USE block) and
# email fragments that mark automated test sign-ups. Excluded from the sheet.
TEST_SOURCES = {"test", "probe", "previewtest2", "screenshot", "e2etest"}
TEST_EMAIL_MARKERS = ("+gtprobe", "+e2e")


def normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def is_test_signup(row: dict) -> bool:
    if (row.get("src") or "").strip().lower() in TEST_SOURCES:
        return True
    email = normalize_email(row.get("signupEmail"))
    return any(marker in email for marker in TEST_EMAIL_MARKERS)


def real_signups(rows: list[dict]) -> dict[str, dict]:
    """Latest completed sign-up per email from the GuidedTrack export rows.

    A sign-up is a run that reached the email step (signupEmail set). Unfinished runs are
    kept too (the email is what matters), ordered by run id so the newest wins.
    """
    out: dict[str, dict] = {}
    for row in sorted(rows, key=lambda r: int(r.get("Run") or 0)):
        email = normalize_email(row.get("signupEmail"))
        if "@" not in email or is_test_signup(row):
            continue
        out[email] = {
            "signed_up_utc": (row.get("Time Finished (UTC)") or row.get("Time Started (UTC)") or "").strip(),
            "email": email,
            "first_name": (row.get("signupFirstName") or "").strip(),
            "question": (row.get("questionForSession") or "").strip(),
            "src": (row.get("src") or "").strip(),
            "local_time": (row.get("signedUpAt") or "").strip(),
        }
    return out


def to_row(rec: dict) -> list[str]:
    return [rec["signed_up_utc"], rec["email"], rec["first_name"], rec["question"], rec["src"], rec["local_time"], "sync"]


def plan_changes(sheet_values: list[list[str]], signups: dict[str, dict]) -> tuple[list[list[str]], dict[int, list[str]]]:
    """Return (rows to append, {1-based sheet row -> replacement row}) to bring the sheet in
    line with the export. Existing rows keep their timestamp and "Recorded by" value; only
    first name / question / source are refreshed when they differ."""
    by_email: dict[str, int] = {}
    for i, row in enumerate(sheet_values[1:], start=2):
        email = normalize_email(row[1] if len(row) > 1 else "")
        if email and email not in by_email:
            by_email[email] = i
    appends: list[list[str]] = []
    updates: dict[int, list[str]] = {}
    for email, rec in signups.items():
        if email not in by_email:
            appends.append(to_row(rec))
            continue
        i = by_email[email]
        current = list(sheet_values[i - 1]) + [""] * (len(HEADER) - len(sheet_values[i - 1]))
        if (current[2], current[3], current[4]) != (rec["first_name"], rec["question"], rec["src"]):
            updates[i] = [current[0], email, rec["first_name"], rec["question"], rec["src"], current[5] or rec["local_time"], current[6] or "sync"]
    return appends, updates


# --- I/O -------------------------------------------------------------------------------

def fetch_export() -> list[dict]:
    import requests

    auth = (os.environ["GUIDED_TRACK_USERNAME"], os.environ["GUIDED_TRACK_PASSWORD"])
    r = requests.get(EXPORT_URL, auth=auth, timeout=120)
    r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.text)))


def create_sheet(svc) -> str:
    created = svc.spreadsheets().create(body={
        "properties": {"title": "Career Workshop Sign-ups"},
        "sheets": [{"properties": {"title": SHEET_TAB, "gridProperties": {"frozenRowCount": 1}}}],
    }).execute()
    sheet_id = created["spreadsheetId"]
    gid = created["sheets"][0]["properties"]["sheetId"]
    svc.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=f"{SHEET_TAB}!A1", valueInputOption="RAW", body={"values": [HEADER]}
    ).execute()
    widths = [150, 240, 120, 420, 110, 210, 100]
    requests_ = [{"repeatCell": {
        "range": {"sheetId": gid, "startRowIndex": 0, "endRowIndex": 1},
        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
        "fields": "userEnteredFormat.textFormat.bold",
    }}]
    for col, w in enumerate(widths):
        requests_.append({"updateDimensionProperties": {
            "range": {"sheetId": gid, "dimension": "COLUMNS", "startIndex": col, "endIndex": col + 1},
            "properties": {"pixelSize": w}, "fields": "pixelSize",
        }})
    svc.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={"requests": requests_}).execute()
    return sheet_id


def sync(sheet_id: str, dry_run: bool = False) -> tuple[int, int]:
    from sheets_client import get_client

    svc = get_client()
    values = svc.spreadsheets().values().get(spreadsheetId=sheet_id, range=f"{SHEET_TAB}!A:G").execute().get("values", [])
    if not values:
        values = [HEADER]
        if not dry_run:
            svc.spreadsheets().values().update(
                spreadsheetId=sheet_id, range=f"{SHEET_TAB}!A1", valueInputOption="RAW", body={"values": [HEADER]}
            ).execute()
    signups = real_signups(fetch_export())
    appends, updates = plan_changes(values, signups)
    print(f"export: {len(signups)} real sign-ups; sheet: {len(values) - 1} rows; "
          f"{len(appends)} to append, {len(updates)} to update{' (dry run)' if dry_run else ''}")
    if dry_run:
        for r in appends:
            print("  + ", r)
        for i, r in updates.items():
            print(f"  ~ row {i}", r)
        return len(appends), len(updates)
    if appends:
        svc.spreadsheets().values().append(
            spreadsheetId=sheet_id, range=f"{SHEET_TAB}!A:G", valueInputOption="RAW",
            insertDataOption="INSERT_ROWS", body={"values": appends},
        ).execute()
    if updates:
        svc.spreadsheets().values().batchUpdate(spreadsheetId=sheet_id, body={
            "valueInputOption": "RAW",
            "data": [{"range": f"{SHEET_TAB}!A{i}:G{i}", "values": [row]} for i, row in updates.items()],
        }).execute()
    return len(appends), len(updates)


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet-id", default=os.getenv("WORKSHOP_SHEET_ID"), help="target spreadsheet (default: $WORKSHOP_SHEET_ID)")
    ap.add_argument("--new-sheet", action="store_true", help="create a new spreadsheet and print its id (no sync)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.new_sheet:
        from sheets_client import get_client

        sheet_id = create_sheet(get_client())
        print(f"created https://docs.google.com/spreadsheets/d/{sheet_id}")
        print(f"WORKSHOP_SHEET_ID={sheet_id}")
        return
    if not args.sheet_id:
        sys.exit("No target: set WORKSHOP_SHEET_ID (or pass --sheet-id), or run --new-sheet to create one.")
    sync(args.sheet_id, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
