"""The active-subscriber count the dashboard recorded on each day, read back from git history.

    .venv/bin/python reports/subscribers_by_month_2026-11-18_src/fetch_dashboard_history.py

`frontend/public/snapshot.json` is committed several times a day with beehiiv's live active count at that
moment (`snapshots.total_subscribers`). Those commits are the only record of what the list size WAS on a
past day, as opposed to what beehiiv says today about that day, and comparing the two is how analysis.py
looks for deleted subscribers (beehiiv keeps no deletion log). Writes dashboard_active_history.json: the
first snapshot of every UTC day since the dashboard exists (2026-05-26).
"""
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
SNAPSHOT = "frontend/public/snapshot.json"
TOTAL = re.compile(rb'"total_subscribers":\s*(\d+)')
GENERATED = re.compile(rb'"generated_at":\s*"([^"]+)"')


def git(*args) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def first_commit_per_day() -> dict:
    """{utc_day: commit_sha} for the earliest snapshot commit of each UTC day."""
    lines = git("log", "--format=%H %ct", "--", SNAPSHOT).decode().split("\n")
    commits = sorted((int(l.split()[1]), l.split()[0]) for l in lines if l.strip())
    first = {}
    for ts, sha in commits:
        first.setdefault(datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"), sha)
    return first


def read_snapshot(sha: str):
    """(generated_at ISO string, live active count) of the snapshot at that commit, or None."""
    blob = git("show", f"{sha}:{SNAPSHOT}")
    start = max(blob.find(b'"snapshots"'), 0)  # the top-level block holds the count at fetch time
    total, generated = TOTAL.search(blob, start) or TOTAL.search(blob), GENERATED.search(blob)
    if not (total and generated):
        return None
    return generated.group(1).decode(), int(total.group(1))


def main():
    rows = []
    for day, sha in sorted(first_commit_per_day().items()):
        snap = read_snapshot(sha)
        if snap:
            rows.append({"generated_at": snap[0], "active": snap[1]})
    out = {"source": f"git history of {SNAPSHOT}, first snapshot of each UTC day", "snapshots": rows}
    (HERE / "dashboard_active_history.json").write_text(json.dumps(out, indent=0))
    print(f"{len(rows)} days, {rows[0]['generated_at'][:10]} to {rows[-1]['generated_at'][:10]}")


if __name__ == "__main__":
    main()
