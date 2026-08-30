"""Airtable client for the CT Programs base.

The base is at https://airtable.com/appjydbIYKPlfcwSd/shrilWbuUgB0EL3ZL/tblW9XDHQrCpcmyEh
and lists every Clearer Thinking tool/program with status, URL, category, etc.

Auth: a Personal Access Token (PAT) is stored in the env var `AIRTABLE_CT_PROGRAMS_BASE_ID`
(misnamed — it's actually the PAT, not a base ID). The base ID and table ID are constants below.
"""
from __future__ import annotations

import os
from typing import Iterator

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_ID = "appjydbIYKPlfcwSd"
TABLE_ID = "tblW9XDHQrCpcmyEh"
_PAT_ENV = "AIRTABLE_CT_PROGRAMS_BASE_ID"  # historical name; value is a PAT


def _pat() -> str:
    pat = os.getenv(_PAT_ENV)
    if not pat:
        raise RuntimeError(f"Missing env var {_PAT_ENV}")
    return pat


def list_tools(fields: list[str] | None = None) -> Iterator[dict]:
    """Yield every record from the CT Programs table, paginated."""
    headers = {"Authorization": f"Bearer {_pat()}"}
    params: dict = {"pageSize": 100}
    if fields:
        params["fields[]"] = fields
    offset = None
    while True:
        if offset:
            params["offset"] = offset
        r = requests.get(
            f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}",
            headers=headers, params=params, timeout=30,
        )
        r.raise_for_status()
        d = r.json()
        for rec in d.get("records", []):
            yield rec
        offset = d.get("offset")
        if not offset:
            break


def launched_tools() -> list[dict]:
    """Return only tools with Status == 'Launched' AND Live on Website == 'Launched'."""
    return [
        r for r in list_tools()
        if r["fields"].get("Status") == "Launched"
        and r["fields"].get("Live on Website") == "Launched"
    ]
