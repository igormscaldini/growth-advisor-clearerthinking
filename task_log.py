"""The task bot's record: one private Google Sheet (tab "Tasks", one row per emailed instruction)
plus the "Contacts" tab Igor edits himself (people the bot may draft emails to).

The sheet is the single store. It holds customer names and addresses, so it lives in Igor's
Google account and never in this PUBLIC repository; the password-protected page
(frontend/app/tasks) only reads it. Its id is the TASK_LOG_SHEET_ID secret.

    python task_log.py --create      # one-time: make the sheet and print its id
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")   # so the sheet id is found whoever imports this first

SHEET_ENV = "TASK_LOG_SHEET_ID"
TASKS_TAB = "Tasks"
CONTACTS_TAB = "Contacts"
# The page maps cells by these header names (frontend/lib/tasks.ts), so order may change freely
# but a rename must be made in both places.
COLUMNS = ["Task", "Received (UTC)", "Status", "Instruction", "About", "Actions", "Summary", "Drafts",
           "Updated (UTC)", "Thread", "Message ID", "Draft data", "Understood"]
CONTACT_COLUMNS = ["Name", "Email", "Send from", "Notes"]
KEY_COLUMN = "Message ID"

RUNNING, DONE, DRAFTS_WAITING, NEEDS_YOU, FAILED = "Running", "Done", "Drafts waiting", "Needs you", "Failed"
# Confirm-first (2026-11-20): a plan waits for Igor's yes; "no" cancels it; a correction replaces it.
AWAITING, CANCELLED, REPLACED, EXPIRED = "Awaiting your OK", "Cancelled", "Replaced", "Expired"
STALE_RUNNING_MINUTES = 30
CELL_LIMIT = 4000   # keeps one runaway text from bloating the sheet (a cell allows 50,000)


def sheet_id() -> str:
    return (os.getenv(SHEET_ENV) or "").strip()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _service():
    from sheets_client import get_client

    return get_client()


# --- pure helpers (unit-tested) ---------------------------------------------------------------
def column_letter(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA."""
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def rows_to_records(values: list[list]) -> list[dict]:
    """Sheet values (header row first) -> dicts keyed by header, each with its 1-based `_row`."""
    if not values:
        return []
    header = [str(h).strip() for h in values[0]]
    out = []
    for i, row in enumerate(values[1:], start=2):
        if not any(str(c).strip() for c in row):
            continue
        rec = {h: (str(row[j]) if j < len(row) else "") for j, h in enumerate(header) if h}
        rec["_row"] = i
        out.append(rec)
    return out


def record_to_row(record: dict, header: list[str]) -> list[str]:
    return [str(record.get(h, "") or "")[:CELL_LIMIT] for h in header]


def next_task_number(records: list[dict]) -> int:
    numbers = [int(r["Task"]) for r in records if str(r.get("Task", "")).strip().isdigit()]
    return max(numbers, default=0) + 1


def is_stale_running(record: dict, now: datetime, minutes: int = STALE_RUNNING_MINUTES) -> bool:
    """A row left on "Running" by a run that died before it could report."""
    if record.get("Status") != RUNNING:
        return False
    try:
        updated = datetime.strptime(record.get("Updated (UTC)", ""), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return (now - updated).total_seconds() > minutes * 60


def is_expired_plan(record: dict, now: datetime, days: int) -> bool:
    """A plan Igor never answered: by then a "yes" no longer counts (task_bot.PLAN_TTL_DAYS)."""
    if record.get("Status") != AWAITING:
        return False
    try:
        updated = datetime.strptime(record.get("Updated (UTC)", ""), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return (now - updated).total_seconds() > days * 86400


def missing_columns(header: list[str]) -> list[str]:
    return [c for c in COLUMNS if c not in header]


def parse_draft_data(record: dict) -> list[dict]:
    try:
        data = json.loads(record.get("Draft data") or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def contacts_from_rows(values: list[list]) -> list[dict]:
    out = []
    for rec in rows_to_records(values):
        email = rec.get("Email", "").strip().lower()
        if "@" not in email:
            continue
        out.append({"name": rec.get("Name", "").strip(), "email": email,
                    "send_from": rec.get("Send from", "").strip().lower(),
                    "notes": rec.get("Notes", "").strip()})
    return out


# --- Sheets I/O ---------------------------------------------------------------------------------
class TaskLog:
    """Reads and writes the Tasks tab. Values are written RAW, never USER_ENTERED: the text comes
    from forwarded emails, and a cell starting with "=" must stay text, not become a formula."""

    def __init__(self, spreadsheet_id: str | None = None, service=None):
        self.id = spreadsheet_id or sheet_id()
        if not self.id:
            raise RuntimeError(f"{SHEET_ENV} is not set (create the sheet with `python task_log.py --create`)")
        self.svc = service or _service()

    def _values(self):
        return self.svc.spreadsheets().values()

    def records(self) -> list[dict]:
        resp = self._values().get(spreadsheetId=self.id, range=f"{TASKS_TAB}!A:Z").execute()
        return rows_to_records(resp.get("values", []))

    def header(self) -> list[str]:
        resp = self._values().get(spreadsheetId=self.id, range=f"{TASKS_TAB}!1:1").execute()
        return [str(h).strip() for h in (resp.get("values") or [COLUMNS])[0]]

    def upsert(self, record: dict) -> dict:
        """Insert or update the row whose Message ID matches. A new row gets the next task
        number. Only the columns present in `record` are changed on an update."""
        header = self.header()
        existing = next((r for r in self.records() if r.get(KEY_COLUMN) == record[KEY_COLUMN]), None)
        merged = {**(existing or {}), **record, "Updated (UTC)": utc_now()}
        if existing:
            row = existing["_row"]
            last = column_letter(len(header) - 1)
            self._values().update(
                spreadsheetId=self.id, range=f"{TASKS_TAB}!A{row}:{last}{row}", valueInputOption="RAW",
                body={"values": [record_to_row(merged, header)]}).execute()
        else:
            merged["Task"] = str(next_task_number(self.records()))
            self._values().append(
                spreadsheetId=self.id, range=f"{TASKS_TAB}!A:A", valueInputOption="RAW",
                insertDataOption="INSERT_ROWS", body={"values": [record_to_row(merged, header)]}).execute()
        return merged

    def ensure_columns(self) -> None:
        """Add any COLUMNS the sheet's header lacks, at the right end (a sheet made before a column
        existed keeps working; upsert only writes columns that are in the header)."""
        header = self.header()
        extra = missing_columns(header)
        if extra:
            start = column_letter(len(header))
            self._values().update(spreadsheetId=self.id, range=f"{TASKS_TAB}!{start}1", valueInputOption="RAW",
                                  body={"values": [extra]}).execute()

    def contacts(self) -> list[dict]:
        resp = self._values().get(spreadsheetId=self.id, range=f"{CONTACTS_TAB}!A:D").execute()
        return contacts_from_rows(resp.get("values", []))


def create_sheet(title: str = "Claude tasks") -> str:
    """One-time setup: a new spreadsheet with the two tabs and their header rows. Returns its id."""
    svc = _service()
    created = svc.spreadsheets().create(body={
        "properties": {"title": title},
        "sheets": [
            {"properties": {"title": TASKS_TAB, "gridProperties": {"frozenRowCount": 1}}},
            {"properties": {"title": CONTACTS_TAB, "gridProperties": {"frozenRowCount": 1}}},
        ],
    }).execute()
    sid = created["spreadsheetId"]
    svc.spreadsheets().values().batchUpdate(spreadsheetId=sid, body={
        "valueInputOption": "RAW",
        "data": [
            {"range": f"{TASKS_TAB}!A1", "values": [COLUMNS]},
            {"range": f"{CONTACTS_TAB}!A1", "values": [CONTACT_COLUMNS]},
        ],
    }).execute()
    return sid


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--create", action="store_true", help="create the sheet and print its id")
    if ap.parse_args().create:
        new_id = create_sheet()
        print(f"Created. Set {SHEET_ENV}={new_id} in .env, as a GitHub secret and in Vercel.")
        print(f"https://docs.google.com/spreadsheets/d/{new_id}")
