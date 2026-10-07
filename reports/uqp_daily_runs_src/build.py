"""Daily runs of GT program 37281 "Unanswered Questions Of Psychology - Survey" over the last 14 days.

A run = one person opening the program (GT's export excludes test runs, includes unfinished ones).
Writes reports/uqp_daily_runs_<date>.html. Counts only, no names or emails (the repo is public).
Run: .venv/bin/python reports/uqp_daily_runs_src/build.py
"""
import io
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
PROGRAM_ID = 37281
DAYS = 14
QUESTION_COLS = ("(ozwgip)", "(h808ylh)")  # the question field in the old and new program versions


def fetch_runs() -> pd.DataFrame:
    load_dotenv(ROOT / ".env")
    auth = (os.environ["GUIDED_TRACK_USERNAME"], os.environ["GUIDED_TRACK_PASSWORD"])
    r = requests.get(f"https://www.guidedtrack.com/programs/{PROGRAM_ID}/exports?export_format=csv",
                     auth=auth, timeout=120)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))


def daily_counts(runs: pd.DataFrame, end: date, days: int = DAYS) -> list:
    qcols = [c for c in runs.columns if c.endswith(QUESTION_COLS)]
    answered = runs[qcols].apply(lambda col: col.astype(str).str.strip().ne("") & col.notna()).any(axis=1)
    test = runs[qcols].apply(lambda col: col.astype(str).str.strip().str.lower().eq("test")).any(axis=1)
    runs = runs[~test]
    day = pd.to_datetime(runs["Time Started (UTC)"]).dt.date
    out = []
    for i in range(days - 1, -1, -1):
        d = end - timedelta(days=i)
        m = day == d
        out.append({"date": d.isoformat(), "runs": int(m.sum()),
                    "finished": int(runs.loc[m, "Time Finished (UTC)"].notna().sum()),
                    "submitted": int((m & answered[~test]).sum())})
    return out


def render(data: list, stamp: str) -> str:
    total = sum(d["runs"] for d in data)
    subs = sum(d["submitted"] for d in data)
    tpl = (Path(__file__).parent / "template.html").read_text()
    return (tpl.replace("__DATA__", json.dumps(data)).replace("__STAMP__", stamp)
               .replace("__TOTAL__", str(total)).replace("__SUBS__", str(subs))
               .replace("__RANGE__", f"{data[0]['date']} to {data[-1]['date']}"))


if __name__ == "__main__":
    now = datetime.now()
    data = daily_counts(fetch_runs(), end=datetime.utcnow().date())
    out = ROOT / "reports" / f"uqp_daily_runs_{now:%Y-%m-%d}.html"
    out.write_text(render(data, now.strftime("%Y-%m-%d %I:%M%p").lower()))
    print(out)
    for d in data:
        print(d)
