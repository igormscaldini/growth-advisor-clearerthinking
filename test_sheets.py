"""Sanity-check report: confirm Sheets access works end-to-end."""
import os

from dotenv import load_dotenv

from sheets_client import get_client

load_dotenv()

SHEET_ID = os.getenv("SHEETS_NEWSLETTER_FEEDBACK_ID")


def main() -> None:
    if not SHEET_ID:
        raise SystemExit("SHEETS_NEWSLETTER_FEEDBACK_ID not set in .env")

    svc = get_client()

    meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    title = meta["properties"]["title"]
    tabs = [s["properties"]["title"] for s in meta["sheets"]]

    print(f"Title:  {title}")
    print(f"Tabs:   {tabs}\n")

    # Read header + first 3 data rows from the first tab
    first_tab = tabs[0]
    rows = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"'{first_tab}'!A1:F4",
    ).execute().get("values", [])

    print(f"First {len(rows)} rows of '{first_tab}' (cols A:F):")
    for i, row in enumerate(rows):
        print(f"  {i+1}: {row}")

    print("\nSheets connection OK.")


if __name__ == "__main__":
    main()
