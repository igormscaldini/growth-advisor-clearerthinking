"""Write the Google Doc links into the "Sponsorships Schedule - Clearer Thinking" sheet (column G, "Copy doc"),
one HYPERLINK per partner row. Usage:
    .venv/bin/python reports/sponsor_copy_2026-11-02_src/link_docs_in_sheet.py GWWC=<docId> FarmKind=<docId>
Rows are matched on column A (Partner) exactly; Igor's other columns are never touched."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SHEET_ID = "18iGSicfNJgiXlHGKOqKcC7bMSvR4d6EgMFuY-RVmACE"


def main() -> None:
    from sheets_client import get_client
    docs = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
    svc = get_client()
    meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    tab = meta["sheets"][0]["properties"]["title"]
    # pt_BR, de_DE etc. separate formula arguments with ";" while en_US uses ","
    sep = "," if meta["properties"].get("locale", "en_US").startswith("en") else ";"
    print("locale", meta["properties"].get("locale"), "-> formula separator", repr(sep))
    rows = svc.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=f"'{tab}'!A1:G50").execute().get("values", [])
    header = rows[0] if rows else []
    if len(header) < 7 or header[6] != "Copy doc":
        svc.spreadsheets().values().update(spreadsheetId=SHEET_ID, range=f"'{tab}'!G1", valueInputOption="RAW",
                                           body={"values": [["Copy doc"]]}).execute()
    data = []
    for i, r in enumerate(rows[1:], start=2):
        partner = (r[0] if r else "").strip()
        if partner in docs:
            url = f"https://docs.google.com/document/d/{docs[partner]}/edit"
            data.append({"range": f"'{tab}'!G{i}", "values": [[f'=HYPERLINK("{url}"{sep} "{partner} copy")']]})
    if not data:
        raise SystemExit("no matching partner rows")
    if "--dry-run" in sys.argv:
        print("dry run, would write:", [(d["range"], d["values"][0][0]) for d in data]); return
    svc.spreadsheets().values().batchUpdate(spreadsheetId=SHEET_ID, body={"valueInputOption": "USER_ENTERED", "data": data}).execute()
    print(f"linked {len(data)} rows on tab {tab!r}: " + ", ".join(d["range"] for d in data))


if __name__ == "__main__":
    main()
