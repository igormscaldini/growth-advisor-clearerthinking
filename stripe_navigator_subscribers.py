"""List every Clearer Thinking Plus Navigator subscriber from Stripe.

Navigator has two live prices (there are no archived ones):
  price_1SQvhxAoBs2tgN9p7Hp5KuC0  Clearer Thinking Plus - Navigator                        $99/mo
  price_1TC1fNAoBs2tgN9poVlnyrY7  Clearer Thinking Plus - Navigator (4 Monthly Coaching...) $179/mo

Writes a CSV (Name, Email, Status, Created at, Plan) that can be imported straight into
Airtable, and can push the same rows into an Airtable table via the API.

    python stripe_navigator_subscribers.py                       # CSV only
    python stripe_navigator_subscribers.py --active-only         # drop cancelled subscriptions
    python stripe_navigator_subscribers.py --sheets              # + a new Google Sheet
    python stripe_navigator_subscribers.py --sheets --sheet-id ID   # refresh an existing Sheet
    python stripe_navigator_subscribers.py --airtable --base appXXXXXXXXXXXXXX

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

from stripe_client import get_client

load_dotenv()

NAVIGATOR_PRICES = {
    "price_1SQvhxAoBs2tgN9p7Hp5KuC0": "Navigator ($99/mo)",
    "price_1TC1fNAoBs2tgN9poVlnyrY7": "Navigator + Coaching ($179/mo)",
}
TABLE_NAME = "Navigator Subscribers"
COLUMNS = ["Name", "Email", "Status", "Created at", "Plan"]


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
    }


def fetch_subscribers(active_only: bool = False) -> list[dict]:
    """One row per Navigator subscription, newest first."""
    stripe = get_client()
    customers: dict = {}
    rows: dict[str, dict] = {}

    for price_id, plan in NAVIGATOR_PRICES.items():
        for sub in stripe.Subscription.list(
            price=price_id, status="all", limit=100
        ).auto_paging_iter():
            if active_only and _g(sub, "status") != "active":
                continue
            cust_id = _g(sub, "customer")
            if cust_id not in customers:
                customers[cust_id] = stripe.Customer.retrieve(cust_id)
            rows[_g(sub, "id")] = build_row(sub, customers[cust_id], plan)

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


def push_to_sheets(rows: list[dict], sheet_id: str | None = None,
                   title: str | None = None) -> str:
    """Create (or overwrite) a Google Sheet holding the rows. Returns its URL."""
    from sheets_client import get_client

    svc = get_client()
    title = title or f"Navigator Subscribers ({dt.date.today()})"
    values = [COLUMNS] + [[r[c] for c in COLUMNS] for r in rows]

    if sheet_id:
        svc.spreadsheets().values().clear(
            spreadsheetId=sheet_id, range="A:Z", body={}
        ).execute()
        tab = "Sheet1"
    else:
        created = svc.spreadsheets().create(body={
            "properties": {"title": title},
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
    gid = next(s["properties"]["sheetId"] for s in meta["sheets"]
               if s["properties"]["title"] == tab)
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

    return f"https://docs.google.com/spreadsheets/d/{sheet_id}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--active-only", action="store_true",
                    help="only subscriptions currently active (default: every status)")
    ap.add_argument("--out", default=str(Path.home() / "Downloads" /
                                        f"navigator_subscribers_{dt.date.today()}.csv"))
    ap.add_argument("--sheets", action="store_true", help="also push into a Google Sheet")
    ap.add_argument("--sheet-id", help="existing spreadsheet id to overwrite (default: create one)")
    ap.add_argument("--airtable", action="store_true", help="also push into Airtable")
    ap.add_argument("--base", help="Airtable base id (appXXXXXXXXXXXXXX)")
    ap.add_argument("--table", default=TABLE_NAME)
    args = ap.parse_args()

    rows = fetch_subscribers(active_only=args.active_only)
    path = write_csv(rows, Path(args.out))
    active = sum(1 for r in rows if r["Status"].startswith("Active"))
    print(f"{len(rows)} Navigator subscriptions ({active} active) -> {path}")

    if args.sheets:
        print("Google Sheet:", push_to_sheets(rows, args.sheet_id))

    if args.airtable:
        if not args.base:
            raise SystemExit("--airtable needs --base appXXXXXXXXXXXXXX")
        print("Airtable table:", push_to_airtable(rows, args.base, args.table))


if __name__ == "__main__":
    main()
