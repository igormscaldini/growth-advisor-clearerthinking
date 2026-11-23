"""Draw a winner for one round of the workshop book giveaway (GT "Productivity Workshop - Book Giveaway", 38686).

Usage, live during the workshop:
    .venv/bin/python workshop_giveaway_draw.py --round 1
    .venv/bin/python workshop_giveaway_draw.py --round 1 --redraw   # winner not on the call: pick someone else

Rules: only entries for that round (the `?round=N` link), started on or after --since (default: today, UTC),
one entry per email, nobody who already won a round (one copy per person), no QA/test addresses.
Winners are kept in ~/Downloads (they hold emails, so never in this public repo).
"""
import argparse
import csv
import datetime as dt
import io
import json
import random
from pathlib import Path

PROGRAM_ID = 38686
WINNERS_FILE = Path.home() / "Downloads" / "workshop_giveaway_winners.json"
TEST_EMAIL_MARKERS = ("igormscaldini", "+qa", "+healthcheck")


def is_test_email(email):
    return any(m in email.lower() for m in TEST_EMAIL_MARKERS)


def eligible_entries(rows, round_no, since, excluded_emails):
    """Entries that can win `round_no`: right round, started on/after `since` (YYYY-MM-DD), email given,
    not a test address, not excluded; the first entry per email (case-insensitive) is kept."""
    excluded = {e.strip().lower() for e in excluded_emails}
    seen, out = set(), []
    for r in rows:
        email = (r.get("email") or "").strip()
        key = email.lower()
        if str(r.get("giveawayRound", "")).strip() != str(round_no):
            continue
        if (r.get("Time Started (UTC)") or "")[:10] < since:
            continue
        if not email or is_test_email(email) or key in excluded or key in seen:
            continue
        seen.add(key)
        out.append({"nickname": (r.get("nickname") or "").strip(), "email": email})
    return out


def unlabelled_entries(rows, since):
    """Entries made through a link without ?round= (saved as "none"): a sign the wrong link was shared."""
    return [r for r in rows if r.get("giveawayRound") == "none" and (r.get("Time Started (UTC)") or "")[:10] >= since]


def fetch_rows():
    import requests
    from dotenv import dotenv_values

    env = dotenv_values(Path(__file__).with_name(".env"))
    auth = (env["GUIDED_TRACK_USERNAME"], env["GUIDED_TRACK_PASSWORD"])
    r = requests.get(f"https://www.guidedtrack.com/programs/{PROGRAM_ID}/exports?export_format=csv", auth=auth, timeout=120)
    r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.text)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True, choices=[1, 2, 3])
    ap.add_argument("--since", default=dt.datetime.utcnow().strftime("%Y-%m-%d"))
    ap.add_argument("--redraw", action="store_true", help="pass over this round's current winner and draw again")
    args = ap.parse_args()

    state = json.loads(WINNERS_FILE.read_text()) if WINNERS_FILE.exists() else {"winners": {}, "passed": []}
    key = str(args.round)
    if key in state["winners"] and not args.redraw:
        w = state["winners"][key]
        print(f"Round {key} already has a winner: {w['nickname']} ({w['email']}). Use --redraw to pick again.")
        return
    if args.redraw and key in state["winners"]:
        state["passed"].append(state["winners"].pop(key)["email"])

    rows = fetch_rows()
    excluded = [w["email"] for w in state["winners"].values()] + state["passed"]
    pool = eligible_entries(rows, args.round, args.since, excluded)
    stray = unlabelled_entries(rows, args.since)
    if stray:
        print(f"WARNING: {len(stray)} entries came through a link without ?round= and are not in any draw.")
    if not pool:
        print(f"No eligible entries for round {key} since {args.since}.")
        return
    winner = random.SystemRandom().choice(pool)
    state["winners"][key] = winner
    WINNERS_FILE.write_text(json.dumps(state, indent=2))
    print(f"{len(pool)} eligible entries in round {key}.")
    print(f"\n    WINNER: {winner['nickname'] or '(no nickname)'}\n    email:  {winner['email']}\n")
    print(f"Saved to {WINNERS_FILE}")


if __name__ == "__main__":
    main()
