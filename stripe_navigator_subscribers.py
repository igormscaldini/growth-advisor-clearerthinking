"""List every Clearer Thinking Plus Navigator subscriber from Stripe.

Navigator has two live prices (there are no archived ones):
  price_1SQvhxAoBs2tgN9p7Hp5KuC0  Clearer Thinking Plus - Navigator                        $99/mo
  price_1TC1fNAoBs2tgN9poVlnyrY7  Clearer Thinking Plus - Navigator (4 Monthly Coaching...) $179/mo

Writes a CSV (Name, Email, Status, Created at, Plan) that can be imported straight into
Airtable, and can push the same rows into an Airtable table via the API.

    python stripe_navigator_subscribers.py                       # CSV only
    python stripe_navigator_subscribers.py --active-only         # drop cancelled subscriptions
    python stripe_navigator_subscribers.py --sheets              # + a new Google Sheet
    python stripe_navigator_subscribers.py --sheets --sheet-id ID   # sync an existing Sheet
    python stripe_navigator_subscribers.py --sheets --rebuild --sheet-id ID  # overwrite it
    python stripe_navigator_subscribers.py --airtable --base appXXXXXXXXXXXXXX

The Sheet sync is an upsert matched on Subscription ID: it adds new subscriptions at
the top, updates ones whose status changed, and never reads or writes columns to the
right of the ones it owns, so notes you keep alongside the data survive every run.
A "Sync" tab records when it last ran. GitHub Actions runs it every 15 minutes
(.github/workflows/navigator-sheet-sync.yml) with the id in NAVIGATOR_SHEET_ID.

The Airtable push needs a Personal Access Token with the scopes schema.bases:read,
schema.bases:write and data.records:write on the target base, in the env var AIRTABLE_PAT.
(AIRTABLE_CT_PROGRAMS_BASE_ID, despite its name, is a read-only PAT for the CT Programs base
and cannot create tables.)
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from secrets_loader import materialize_ci_secrets

load_dotenv()
# On GitHub Actions the Google credentials arrive as env vars; the Sheets client
# wants them on disk. No-op locally.
materialize_ci_secrets()

from stripe_client import get_client  # noqa: E402

NAVIGATOR_PRICES = {
    "price_1SQvhxAoBs2tgN9p7Hp5KuC0": "Navigator ($99/mo)",
    "price_1TC1fNAoBs2tgN9poVlnyrY7": "Navigator + Coaching ($179/mo)",
}
TABLE_NAME = "Navigator Subscribers"
# Columns the script owns. Anything to the right of these in a synced Google Sheet
# belongs to the human and is never read, written or cleared.
COLUMNS = ["Name", "Email", "Status", "Created at", "Plan", "Subscription ID"]
ID_COLUMN = "Subscription ID"


def _g(obj, key, default=None):
    """Stripe objects raise KeyError instead of returning None for absent keys."""
    try:
        return obj[key]
    except Exception:
        return default


def status_label(status: str, cancel_at_period_end: bool = False) -> str:
    """Stripe's status, made readable. Active-but-winding-down is called out."""
    if status == "active" and cancel_at_period_end:
        return "Active (cancels at period end)"
    return (status or "").replace("_", " ").capitalize()


def build_row(sub, customer, plan: str) -> dict:
    """One CSV/Airtable row from a Stripe subscription plus its customer."""
    return {
        "Name": _g(customer, "name") or "",
        "Email": _g(customer, "email") or "",
        "Status": status_label(_g(sub, "status"), bool(_g(sub, "cancel_at_period_end"))),
        "Created at": dt.datetime.fromtimestamp(
            _g(sub, "created"), dt.timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "Plan": plan,
        ID_COLUMN: _g(sub, "id") or "",
    }


def fetch_subscribers(active_only: bool = False) -> list[dict]:
    """One row per Navigator subscription, newest first."""
    stripe = get_client()
    rows: dict[str, dict] = {}

    for price_id, plan in NAVIGATOR_PRICES.items():
        # Expanding the customer avoids one Customer.retrieve per subscription.
        for sub in stripe.Subscription.list(
            price=price_id, status="all", limit=100, expand=["data.customer"]
        ).auto_paging_iter():
            if active_only and _g(sub, "status") != "active":
                continue
            rows[_g(sub, "id")] = build_row(sub, _g(sub, "customer"), plan)

    return sorted(rows.values(), key=lambda r: r["Created at"], reverse=True)


def write_csv(rows: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return path


def _airtable_headers() -> dict:
    pat = os.getenv("AIRTABLE_PAT", "").strip()
    if not pat:
        raise SystemExit(
            "AIRTABLE_PAT not set. Create a Personal Access Token with schema.bases:read, "
            "schema.bases:write and data.records:write on the target base."
        )
    return {"Authorization": f"Bearer {pat}", "Content-Type": "application/json"}


def push_to_airtable(rows: list[dict], base_id: str, table_name: str = TABLE_NAME) -> str:
    """Create the table if it does not exist, wipe it, then insert every row."""
    headers = _airtable_headers()
    meta = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"

    r = requests.get(meta, headers=headers, timeout=30)
    r.raise_for_status()
    existing = {t["name"]: t["id"] for t in r.json()["tables"]}

    if table_name in existing:
        table_id = existing[table_name]
        # Clear it so re-runs replace rather than duplicate.
        ids = []
        params: dict = {"pageSize": 100, "fields[]": []}
        offset = None
        while True:
            if offset:
                params["offset"] = offset
            rr = requests.get(
                f"https://api.airtable.com/v0/{base_id}/{table_id}",
                headers=headers, params=params, timeout=30,
            )
            rr.raise_for_status()
            d = rr.json()
            ids += [rec["id"] for rec in d.get("records", [])]
            offset = d.get("offset")
            if not offset:
                break
        for i in range(0, len(ids), 10):
            requests.delete(
                f"https://api.airtable.com/v0/{base_id}/{table_id}",
                headers=headers, params=[("records[]", x) for x in ids[i:i + 10]], timeout=30,
            ).raise_for_status()
    else:
        payload = {
            "name": table_name,
            "description": "Clearer Thinking Plus Navigator subscribers, from Stripe.",
            "fields": [
                {"name": "Name", "type": "singleLineText"},
                {"name": "Email", "type": "email"},
                {"name": "Status", "type": "singleLineText"},
                {"name": "Created at", "type": "dateTime",
                 "options": {"timeZone": "utc",
                             "dateFormat": {"name": "iso"},
                             "timeFormat": {"name": "24hour"}}},
                {"name": "Plan", "type": "singleLineText"},
                {"name": ID_COLUMN, "type": "singleLineText"},
            ],
        }
        r = requests.post(meta, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        table_id = r.json()["id"]

    for i in range(0, len(rows), 10):
        batch = [{"fields": row} for row in rows[i:i + 10]]
        rr = requests.post(
            f"https://api.airtable.com/v0/{base_id}/{table_id}",
            headers=headers, json={"records": batch, "typecast": True}, timeout=30,
        )
        rr.raise_for_status()

    return f"https://airtable.com/{base_id}/{table_id}"


def plan_sheet_sync(existing: list[list[str]],
                    rows: list[dict]) -> tuple[list[tuple[int, list]], list[list]]:
    """Work out the minimal edits that bring the sheet in line with Stripe.

    `existing` is the sheet grid including its header row. Returns
    (updates, inserts) where updates is [(1-based sheet row, owned values)] for
    subscriptions already present whose values have drifted, and inserts is the
    owned values for subscriptions not in the sheet yet, newest first so that
    inserting the block at row 2 keeps the sheet in newest-first order.

    Rows are matched on Subscription ID, never on position, so a human can sort,
    filter or annotate the sheet freely. Columns beyond the owned ones are never
    read or written. Raises ValueError if the owned header is not what we expect,
    which is the caller's signal to rebuild rather than guess.
    """
    header = existing[0] if existing else []
    if header[:len(COLUMNS)] != COLUMNS:
        raise ValueError(f"owned header is {header[:len(COLUMNS)]}, expected {COLUMNS}")

    id_index = COLUMNS.index(ID_COLUMN)
    seen: dict[str, tuple[int, list]] = {}
    for row_number, row in enumerate(existing[1:], start=2):
        padded = list(row) + [""] * (len(COLUMNS) - len(row))
        subscription_id = padded[id_index]
        if subscription_id:
            seen[subscription_id] = (row_number, padded[:len(COLUMNS)])

    updates: list[tuple[int, list]] = []
    inserts: list[list] = []
    for row in rows:
        values = [str(row[column]) for column in COLUMNS]
        match = seen.get(row[ID_COLUMN])
        if match is None:
            inserts.append(values)
        elif match[1] != values:
            updates.append((match[0], values))

    return updates, inserts


def _column_letter(index: int) -> str:
    """1 -> A, 26 -> Z, 27 -> AA."""
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _write_sync_status(svc, sheet_id: str, rows: list[dict]) -> None:
    """A small out-of-the-way tab so a stale cron is visible at a glance."""
    meta = svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
    if not any(sh["properties"]["title"] == "Sync" for sh in meta["sheets"]):
        svc.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={"requests": [
            {"addSheet": {"properties": {"title": "Sync"}}}]}).execute()

    active = sum(1 for r in rows if r["Status"].startswith("Active"))
    svc.spreadsheets().values().update(
        spreadsheetId=sheet_id, range="Sync!A1",
        valueInputOption="USER_ENTERED",
        body={"values": [
            ["Last synced (UTC)", dt.datetime.now(dt.timezone.utc)
                                    .strftime("%Y-%m-%d %H:%M:%S")],
            ["Subscriptions", len(rows)],
            ["Active", active],
            ["Source", "stripe_navigator_subscribers.py (GitHub Actions)"],
        ]},
    ).execute()


def rebuild_sheet(rows: list[dict], sheet_id: str | None = None,
                  title: str | None = None) -> str:
    """Write the whole grid from scratch, creating the spreadsheet if needed.

    Destructive by design: only for a first run or a sheet with nothing of the
    user's in it. Routine refreshes go through sync_sheet.
    """
    from sheets_client import get_client

    svc = get_client()
    values = [COLUMNS] + [[r[c] for c in COLUMNS] for r in rows]

    if sheet_id:
        meta = svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
        tab = meta["sheets"][0]["properties"]["title"]
        svc.spreadsheets().values().clear(
            spreadsheetId=sheet_id, range=f"{tab}!A:{_column_letter(len(COLUMNS))}",
            body={},
        ).execute()
    else:
        created = svc.spreadsheets().create(body={
            "properties": {"title": title or "Navigator Subscribers"},
            "sheets": [{"properties": {"title": "Subscribers"}}],
        }).execute()
        sheet_id = created["spreadsheetId"]
        tab = "Subscribers"

    svc.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=f"{tab}!A1",
        valueInputOption="USER_ENTERED", body={"values": values},
    ).execute()

    # Bold header, freeze it, size the columns to the content.
    meta = svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
    gid = next(sh["properties"]["sheetId"] for sh in meta["sheets"]
               if sh["properties"]["title"] == tab)
    svc.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={"requests": [
        {"repeatCell": {
            "range": {"sheetId": gid, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
            "fields": "userEnteredFormat.textFormat.bold"}},
        {"updateSheetProperties": {
            "properties": {"sheetId": gid, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount"}},
        {"autoResizeDimensions": {"dimensions": {
            "sheetId": gid, "dimension": "COLUMNS",
            "startIndex": 0, "endIndex": len(COLUMNS)}}},
    ]}).execute()

    _write_sync_status(svc, sheet_id, rows)
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}"


def sync_sheet(rows: list[dict], sheet_id: str, tab: str | None = None) -> str:
    """Bring an existing sheet in line with Stripe without touching the user's columns."""
    from sheets_client import get_client

    svc = get_client()
    meta = svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
    if tab:
        properties = next(sh["properties"] for sh in meta["sheets"]
                          if sh["properties"]["title"] == tab)
    else:
        # The first tab, rather than a hardcoded name: the sheet this script
        # creates calls its tab "Subscribers", not "Sheet1".
        properties = meta["sheets"][0]["properties"]
    tab, gid = properties["title"], properties["sheetId"]

    # FORMULA keeps any formulas the user wrote intact if they are ever read back.
    existing = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{tab}!A:ZZ", valueRenderOption="FORMULA",
    ).execute().get("values", [])

    try:
        updates, inserts = plan_sheet_sync(existing, rows)
    except ValueError as exc:
        user_columns = max((len(r) for r in existing), default=0) - len(COLUMNS)
        if user_columns > 0:
            raise SystemExit(
                f"Refusing to touch {sheet_id}: {exc}, and the sheet has "
                f"{user_columns} column(s) I do not own. Fix the header by hand, "
                f"or re-run with --rebuild to overwrite (this discards those columns)."
            )
        print(f"Header mismatch ({exc}); nothing of yours in the sheet, rebuilding.")
        return rebuild_sheet(rows, sheet_id)

    last_column = _column_letter(len(COLUMNS))

    if inserts:
        # One block at the top keeps newest-first order. Inserting whole rows lets
        # Sheets carry the user's cells, notes and formulas down with their row.
        svc.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={"requests": [
            {"insertDimension": {
                "range": {"sheetId": gid, "dimension": "ROWS",
                          "startIndex": 1, "endIndex": 1 + len(inserts)},
                "inheritFromBefore": False}}]}).execute()
        svc.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=f"{tab}!A2",
            valueInputOption="USER_ENTERED", body={"values": inserts},
        ).execute()

    if updates:
        # Existing rows shifted down by the block we just inserted.
        offset = len(inserts)
        svc.spreadsheets().values().batchUpdate(spreadsheetId=sheet_id, body={
            "valueInputOption": "USER_ENTERED",
            "data": [{"range": f"{tab}!A{row + offset}:{last_column}{row + offset}",
                      "values": [values]} for row, values in updates],
        }).execute()

    _write_sync_status(svc, sheet_id, rows)
    print(f"{len(inserts)} added, {len(updates)} updated, "
          f"{len(rows) - len(inserts) - len(updates)} unchanged")
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--active-only", action="store_true",
                    help="only subscriptions currently active (default: every status)")
    ap.add_argument("--out", default=str(Path.home() / "Downloads" /
                                        f"navigator_subscribers_{dt.date.today()}.csv"))
    ap.add_argument("--sheets", action="store_true", help="also sync into a Google Sheet")
    ap.add_argument("--sheet-id", default=os.getenv("NAVIGATOR_SHEET_ID"),
                    help="spreadsheet to sync (default: $NAVIGATOR_SHEET_ID, else create one)")
    ap.add_argument("--rebuild", action="store_true",
                    help="overwrite the sheet from scratch instead of upserting "
                         "(discards any columns you added)")
    ap.add_argument("--new-sheet", action="store_true",
                    help="create a brand new spreadsheet instead of syncing an existing one")
    ap.add_argument("--no-csv", action="store_true", help="skip the CSV (for scheduled syncs)")
    ap.add_argument("--airtable", action="store_true", help="also push into Airtable")
    ap.add_argument("--base", help="Airtable base id (appXXXXXXXXXXXXXX)")
    ap.add_argument("--table", default=TABLE_NAME)
    args = ap.parse_args()

    rows = fetch_subscribers(active_only=args.active_only)
    active = sum(1 for r in rows if r["Status"].startswith("Active"))
    summary = f"{len(rows)} Navigator subscriptions ({active} active)"

    if args.no_csv:
        print(summary)
    else:
        print(f"{summary} -> {write_csv(rows, Path(args.out))}")

    if args.sheets:
        if args.new_sheet:
            print("Google Sheet:", rebuild_sheet(rows))
        elif not args.sheet_id:
            # Creating one by accident litters Drive and syncs the wrong sheet
            # forever after, so make it an explicit choice.
            raise SystemExit(
                "--sheets needs a target: pass --sheet-id ID, set NAVIGATOR_SHEET_ID "
                "in .env, or pass --new-sheet to deliberately create a new spreadsheet."
            )
        elif args.rebuild:
            print("Google Sheet:", rebuild_sheet(rows, args.sheet_id))
        else:
            print("Google Sheet:", sync_sheet(rows, args.sheet_id))

    if args.airtable:
        if not args.base:
            raise SystemExit("--airtable needs --base appXXXXXXXXXXXXXX")
        print("Airtable table:", push_to_airtable(rows, args.base, args.table))


if __name__ == "__main__":
    main()
