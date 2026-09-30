"""Create 301 redirects from the auto-generated Wix /tools/<slug> pages to the official tools.

Wix generates a CMS dynamic item page for every row of the "Tools" collection (internal id
`Courses`), which duplicates the real tool hosted on programs.clearerthinking.org (or, for three
tools, on their own subdomain). The wrappers carry ~55 words, compete with the real page, and
account for 58 rows of the not-indexed sheet.

A Wix redirect is a 301, takes effect with no site publish, takes precedence over a page that
still exists at the path, and is reversible by deleting it. So this needs no page deletions.
See https://dev.wix.com/docs/api-reference/business-management/seo/redirects/redirect-v1/introduction

The mapping comes from tools_redirect_map.py (each wrapper links to its own tool), with a handful
of manual entries for pages whose button is rendered by JavaScript.

Usage:
    python tools_redirects.py --dry-run
    python tools_redirects.py --apply --group simple      # slugs with no special characters
    python tools_redirects.py --apply --group special     # slugs containing ? or : or '
    python tools_redirects.py --apply --group special --limit 1   # test one first
    python tools_redirects.py --verify
    python tools_redirects.py --rollback                  # delete only what this script created
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

API = "https://www.wixapis.com/seo-redirects-service/v1"
MAP_FILE = Path.home() / "Downloads" / "wix_tools_redirect_map.json"
# Every redirect this script creates, so --rollback can undo exactly those and nothing else.
LEDGER = Path(__file__).parent / "reports" / "wix_tools_redirects_created.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"}

# Targets for the pages whose "start" button is drawn by JavaScript, so no link appears in the
# HTML. Taken from the All Tools page's own links and each confirmed to return 200.
MANUAL = {
    "explanation-freeze": "https://programs.clearerthinking.org/explanation_freeze.html",
    "cognitive-assessment": "https://programs.clearerthinking.org/cognitive-test-intro.html",
    "society-explained": "https://society.clearerthinking.org/",
    "demystifying-meditation": "https://meditation.clearerthinking.org/",
    "self-help-evidence-pyramid": "https://selfhelppyramid.clearerthinking.org/",
}
# Igor's decision 2026-09-30: this one points at a third-party site (80000hours.org), so it is
# deliberately left alone rather than 301'd off-domain.
EXCLUDE = {"guess-which-experiments-replicate"}
# Already redirected by Igor before this script existed.
ALREADY_DONE = {"the-ultimate-personality-test", "the-common-misconceptions-test",
                "gender-continuum-test"}


def _headers() -> dict:
    key, site = os.getenv("WIX_API_KEY"), os.getenv("WIX_SITE_ID")
    if not key or not site:
        raise RuntimeError("Set WIX_API_KEY and WIX_SITE_ID in .env")
    return {"Authorization": key, "wix-site-id": site, "Content-Type": "application/json"}


def _call(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"{API}{path}", data=json.dumps(body).encode() if body is not None else None,
        headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read().decode("utf-8", "ignore")
        return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} failed: HTTP {e.code}\n"
                           f"{e.read().decode('utf-8', 'ignore')[:1200]}") from e


# --- pure helpers (unit-tested in tests/test_tools_redirects.py) ---------------------------
def is_special(slug: str) -> bool:
    """True when the slug needs percent-encoding, which makes the redirect path risky enough
    to apply separately after a single verified test."""
    return slug != urllib.parse.unquote(slug) or not re.fullmatch(r"[A-Za-z0-9\-_]+", slug)


def slug_of(wix_url: str) -> str:
    """The raw (still percent-encoded) slug, which is what the live URL actually uses."""
    return wix_url.split("/tools/", 1)[1]


def build_redirects(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Returns (simple, special) redirect dicts ready for the API."""
    simple, special = [], []
    for r in rows:
        slug = slug_of(r["wix_url"])
        if slug in EXCLUDE or slug in ALREADY_DONE:
            continue
        target = r.get("target") or MANUAL.get(slug)
        if not target:
            continue
        entry = {"from": f"/tools/{slug}", "to": target}
        (special if is_special(slug) else simple).append(entry)
    return simple, special


# --- operations ---------------------------------------------------------------------------
def load_rows() -> list[dict]:
    if not MAP_FILE.exists():
        raise RuntimeError(f"Missing {MAP_FILE}. Re-run tools_redirect_map.py first.")
    return json.load(open(MAP_FILE))["rows"]


def existing_from_paths() -> set[str]:
    return {r.get("from", "") for r in _call("GET", "/redirects").get("redirects", [])}


def apply(entries: list[dict]) -> None:
    """Bulk-create, then record the created IDs so rollback can be exact.

    forceReplace is deliberately not set: a `from` path already taken should fail that one row
    rather than silently delete somebody else's redirect.
    """
    if not entries:
        print("nothing to do")
        return
    taken = existing_from_paths()
    skip = [e for e in entries if e["from"] in taken]
    todo = [e for e in entries if e["from"] not in taken]
    for e in skip:
        print(f"  skip (already has a redirect): {e['from']}")
    if not todo:
        print("all of these already have redirects")
        return
    if len(todo) > 100:
        raise RuntimeError(f"{len(todo)} redirects exceeds the 100-per-call limit; batch them")

    res = _call("POST", "/bulk/redirects/create", {"redirects": todo, "returnFullEntity": True})
    meta = res.get("bulkActionMetadata", {})
    print(f"  successes={meta.get('totalSuccesses')} failures={meta.get('totalFailures')} "
          f"undetailed={meta.get('undetailedFailures')}")

    created = []
    for item in res.get("results", []):
        im = item.get("itemMetadata", {})
        idx, err = im.get("originalIndex"), im.get("error")
        src = todo[idx]["from"] if isinstance(idx, int) and idx < len(todo) else "?"
        if err:
            print(f"  FAILED {src}: {err.get('code')} {err.get('description','')}")
        elif im.get("id"):
            created.append({"id": im["id"], **todo[idx]})
    ledger = json.load(open(LEDGER)) if LEDGER.exists() else []
    ledger += created
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=1))
    print(f"  recorded {len(created)} new redirect ids in {LEDGER.name} (total {len(ledger)})")


# Wix 429s a burst of requests, and a 429 is indistinguishable from a broken redirect here, so
# the verifier has to go slowly. A fresh redirect also takes a few seconds to propagate.
VERIFY_DELAY = 2.5


def verify(entries: list[dict]) -> tuple[int, int]:
    """Request each path and confirm a 301 to the intended target."""
    ok = bad = 0
    for n, e in enumerate(entries):
        if n:
            time.sleep(VERIFY_DELAY)
        url = "https://www.clearerthinking.org" + e["from"]
        try:
            req = urllib.request.Request(url, headers=UA, method="HEAD")
            # Do not follow: we want to see the 301 itself.
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *a, **k):
                    return None
            op = urllib.request.build_opener(NoRedirect)
            try:
                r = op.open(req, timeout=60)
                code, loc = r.status, r.headers.get("Location")
            except urllib.error.HTTPError as he:
                code, loc = he.code, he.headers.get("Location")
        except Exception as ex:  # noqa: BLE001
            print(f"  ERROR {e['from']}: {type(ex).__name__}")
            bad += 1
            continue
        if code == 429:  # retry once, slowly, rather than calling it a failure
            time.sleep(15)
            try:
                r = op.open(urllib.request.Request(url, headers=UA, method="HEAD"), timeout=60)
                code, loc = r.status, r.headers.get("Location")
            except urllib.error.HTTPError as he:
                code, loc = he.code, he.headers.get("Location")
        hit = code in (301, 302, 308) and loc and loc.rstrip("/") == e["to"].rstrip("/")
        if hit:
            ok += 1
        else:
            bad += 1
            print(f"  MISMATCH {e['from']}\n     got {code} -> {loc}\n     want 301 -> {e['to']}")
    return ok, bad


def rollback() -> None:
    if not LEDGER.exists():
        print("no ledger, nothing to roll back")
        return
    ledger = json.load(open(LEDGER))
    ids = [r["id"] for r in ledger]
    for i in range(0, len(ids), 500):
        res = _call("POST", "/bulk/redirects/delete", {"redirectIds": ids[i:i + 500]})
        m = res.get("bulkActionMetadata", {})
        print(f"  deleted batch: successes={m.get('totalSuccesses')} failures={m.get('totalFailures')}")
    LEDGER.unlink()
    print(f"removed {len(ids)} redirects and deleted the ledger")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--group", choices=["simple", "special", "all"], default="all")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    if args.rollback:
        rollback()
        return

    simple, special = build_redirects(load_rows())
    chosen = {"simple": simple, "special": special, "all": simple + special}[args.group]
    if args.limit:
        chosen = chosen[:args.limit]

    print(f"{len(simple)} simple + {len(special)} special = {len(simple) + len(special)} redirects "
          f"({len(EXCLUDE)} excluded, {len(ALREADY_DONE)} already done)")
    print(f"acting on {len(chosen)} ({args.group}{f', limit {args.limit}' if args.limit else ''})")

    if args.dry_run or not (args.apply or args.verify):
        for e in chosen[:200]:
            print(f"  {e['from']:58s} -> {e['to']}")
        return
    if args.apply:
        apply(chosen)
    if args.verify:
        ok, bad = verify(chosen)
        print(f"verified: {ok} correct, {bad} wrong")
        if bad:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
