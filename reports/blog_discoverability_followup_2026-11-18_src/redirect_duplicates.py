"""301 each duplicated glossary post (/post/<slug>-1) to its original (/post/<slug>).

The pairs come from datapoints.json (same title, slug differing only by the -<n> suffix Wix adds when a
slug is already taken). A Wix redirect takes precedence over the live page, needs no site publish and is
undone by deleting it, so nothing is unpublished here. Reuses the API call and the slow verifier from
tools_redirects.py.

    python redirect_duplicates.py --dry-run
    python redirect_duplicates.py --apply --limit 1     # test one first
    python redirect_duplicates.py --apply
    python redirect_duplicates.py --verify              # a new redirect needs about a minute to reach the edge
    python redirect_duplicates.py --rollback            # deletes only what this script created
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent))

import tools_redirects as tr  # noqa: E402

SITE = "https://www.clearerthinking.org"
LEDGER = HERE.parent / "wix_duplicate_post_redirects_created.json"


def pairs(datapoints: dict) -> list[dict]:
    """[{from, to}] site-relative paths, one per confirmed duplicate (same title as its original)."""
    return [{"from": p["copy"]["url"].replace(SITE, ""), "to": p["base"]["url"].replace(SITE, "")}
            for p in datapoints["duplicates"]["numbered_pairs"] if p["same_title"]]


def apply(entries: list[dict]) -> None:
    taken = tr.existing_from_paths()
    todo = [e for e in entries if e["from"] not in taken]
    for e in entries:
        if e["from"] in taken:
            print(f"  skip (already redirected): {e['from']}")
    if not todo:
        return
    res = tr._call("POST", "/bulk/redirects/create", {"redirects": todo, "returnFullEntity": True})
    created = []
    for item in res.get("results", []):
        meta = item.get("itemMetadata", {})
        src = todo[meta.get("originalIndex", 0)]
        if meta.get("error"):
            print(f"  FAILED {src['from']}: {meta['error'].get('code')} {meta['error'].get('description', '')}")
        elif meta.get("id"):
            created.append({"id": meta["id"], **src})
            print(f"  created {src['from']} -> {src['to']}")
    ledger = (json.loads(LEDGER.read_text()) if LEDGER.exists() else []) + created
    LEDGER.write_text(json.dumps(ledger, indent=1))


def rollback() -> None:
    if not LEDGER.exists():
        print("no ledger, nothing to roll back")
        return
    ids = [r["id"] for r in json.loads(LEDGER.read_text())]
    res = tr._call("POST", "/bulk/redirects/delete", {"redirectIds": ids})
    print(res.get("bulkActionMetadata"))
    LEDGER.unlink()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for flag in ("--dry-run", "--apply", "--verify", "--rollback"):
        ap.add_argument(flag, action="store_true")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    todo = pairs(json.loads((HERE / "datapoints.json").read_text()))[: args.limit]
    if args.rollback:
        rollback()
    elif args.apply:
        apply(todo)
    elif args.verify:
        ok, bad = tr.verify([{"from": e["from"], "to": SITE + e["to"]} for e in todo])
        print(f"{ok} redirect correctly, {bad} do not")
    else:
        for e in todo:
            print(f"  {e['from']} -> {e['to']}")
        print(f"{len(todo)} redirects (dry run)")
