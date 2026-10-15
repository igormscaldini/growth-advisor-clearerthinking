"""Build the push-ready copies of the two members-only GuidedTrack programs.

The repo copies in guidedtrack/ are TEMPLATES. This repo is public, so they carry neither the
access key that opens the full-version page nor the member list. This script fills both in and
writes the result to ~/guidedtrack/<program name>, the `gt push` staging folder, never into the
repo (auto-push.sh does `git add -A`).

    .venv/bin/python members_only_programs.py --csv ~/Downloads/subscriptions.csv
    .venv/bin/python members_only_programs.py --stripe        # active subscriptions from Stripe
    .venv/bin/python members_only_programs.py --check         # print counts, write nothing

Then push both (gt pulls nothing, so re-run this after every template edit):

    cd ~/guidedtrack && PATH="$HOME/bin:$PATH" GT_ENV=production ~/bin/gt push -o "Members-Only Content"
    cd ~/guidedtrack && PATH="$HOME/bin:$PATH" GT_ENV=production ~/bin/gt push -o "The Supplement Paradox (Members-Only)"

How the member check works: the newsletter's paywall links carry `&h={{subscriber_email_hash}}`,
beehiiv's MD5 of the subscriber's email. Program 38912 compares it with the hashes of the active
Stripe customers' emails (lowercased) and sends matches straight to the article. A member whose
Stripe email differs from their beehiiv email is not matched and lands on the sign-up page, which
since 2026-10-15 carries an "Already a member? Enter your email" form: the typed address goes to
the same route (POST /api/member-check) and a match opens the article. The web version's paywall
box links to that form directly with &ask=1.

The key: MEMBERS_ONLY_KEY in .env (16 hex chars). Both programs get the same value, so a run
of this script keeps them in sync. Without it in .env a new one is generated and appended.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent
TEMPLATES = REPO / "guidedtrack"
STAGING = Path.home() / "guidedtrack"
ENV_FILE = REPO / ".env"
PROGRAMS = ["Members-Only Content", "The Supplement Paradox (Members-Only)"]
KEY_PLACEHOLDER = "__MEMBERS_ONLY_KEY__"
HASH_BLOCK = re.compile(r"(-- BEGIN MEMBER HASHES\n).*?(-- END MEMBER HASHES)", re.S)


def email_hash(email: str) -> str:
    """beehiiv's subscriber_email_hash: MD5 of the lowercased, trimmed address."""
    return hashlib.md5(email.strip().lower().encode()).hexdigest()


def hashes_from_csv(path: Path) -> list[str]:
    """Active subscriptions in a Stripe 'subscriptions.csv' export (Customer Email, Status)."""
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    emails = {r["Customer Email"] for r in rows if r.get("Status", "active") == "active" and r.get("Customer Email")}
    return sorted({email_hash(e) for e in emails})


def hashes_from_stripe() -> list[str]:
    """Every active subscription's customer email, straight from Stripe."""
    import stripe

    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    emails = set()
    for sub in stripe.Subscription.list(status="active", limit=100, expand=["data.customer"]).auto_paging_iter():
        email = (sub.customer.email or "") if hasattr(sub.customer, "email") else ""
        if email:
            emails.add(email)
    return sorted({email_hash(e) for e in emails})


def gt_collection(values: list[str]) -> str:
    """A GuidedTrack collection literal on one line: >> memberHashes = ["a", "b"]."""
    inner = ", ".join(f'"{v}"' for v in values)
    return f">> memberHashes = [{inner}]"


def fill_template(template: str, key: str, hashes: list[str] | None) -> str:
    """Replace the key placeholder and (when the template has one) the member-hash block."""
    if KEY_PLACEHOLDER not in template:
        raise ValueError("template has no __MEMBERS_ONLY_KEY__ placeholder")
    out = template.replace(KEY_PLACEHOLDER, key)
    if HASH_BLOCK.search(template):
        if hashes is None:
            raise ValueError("template has a member-hash block but no hashes were given")
        out = HASH_BLOCK.sub(lambda m: f"{m.group(1)}{gt_collection(hashes)}\n{m.group(2)}", out)
    return out


def load_key() -> str:
    load_dotenv(ENV_FILE)
    key = os.getenv("MEMBERS_ONLY_KEY")
    if key:
        return key
    key = secrets.token_hex(8)
    with open(ENV_FILE, "a") as f:
        f.write(f"\n# Opens the members-only full-version pages (see members_only_programs.py)\nMEMBERS_ONLY_KEY={key}\n")
    print(f"MEMBERS_ONLY_KEY was missing from .env: generated one and appended it.", file=sys.stderr)
    return key


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", type=Path, help="Stripe subscriptions export")
    src.add_argument("--stripe", action="store_true", help="read active subscriptions from the Stripe API")
    src.add_argument("--check", action="store_true", help="fill with an empty list, print counts, write nothing")
    args = ap.parse_args()

    load_dotenv(ENV_FILE)
    if args.csv:
        hashes = hashes_from_csv(args.csv)
    elif args.stripe:
        hashes = hashes_from_stripe()
    else:
        hashes = []
    key = "0000000000000000" if args.check else load_key()

    STAGING.mkdir(exist_ok=True)
    for name in PROGRAMS:
        template = (TEMPLATES / f"{name}.gt").read_text()
        filled = fill_template(template, key, hashes)
        if args.check:
            print(f"{name}: {len(filled.splitlines())} lines, ok")
            continue
        (STAGING / name).write_text(filled)
        print(f"wrote {STAGING / name}")
    print(f"member hashes: {len(hashes)}")


if __name__ == "__main__":
    main()
