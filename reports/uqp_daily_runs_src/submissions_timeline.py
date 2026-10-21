"""Submissions over time for GT program 37281 "Unanswered Questions Of Psychology - Survey".

A submission = a non-test run whose question field is filled (one question per run). A responder is
identified by the lower-cased email the run recorded; the output holds counts only, never names or
emails (the repo is public). Writes reports/uqp_submissions_timeline_<date>.html.
Run: .venv/bin/python reports/uqp_daily_runs_src/submissions_timeline.py
"""
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from build import ROOT, fetch_runs  # noqa: E402

QUESTION_COLS = ("(ozwgip)", "(h808ylh)")            # question field, old and new program versions
EMAIL_COLS = ("(itxzlya)", "email", "(1i0bb4v)", "(z7p2re0)")  # email field, newest first
OUTREACH_DATE = date(2026, 9, 28)                    # Spencer's outreach email to academics
TARGET = 40                                          # submissions needed or the prize is cancelled


def _last(series: pd.Series) -> pd.Series:
    """GT joins re-answers of one field with ' | '; keep the final answer."""
    return series.astype("string").str.split(" | ", regex=False).str[-1].str.strip()


def _first_filled(runs: pd.DataFrame, suffixes) -> pd.Series:
    out = pd.Series(pd.NA, index=runs.index, dtype="string")
    for s in suffixes:
        for c in [c for c in runs.columns if c.endswith(s)]:
            out = out.fillna(_last(runs[c]))
    return out


def submissions(runs: pd.DataFrame) -> pd.DataFrame:
    """Real submissions: columns `day` (date) and `responder` (lower-cased email, may be NA)."""
    q = _first_filled(runs, QUESTION_COLS)
    keep = q.notna() & q.ne("") & q.str.lower().ne("test")
    sub = runs.loc[keep]
    return pd.DataFrame({
        "day": pd.to_datetime(sub["Time Started (UTC)"]).dt.date.values,
        "responder": _first_filled(sub, EMAIL_COLS).str.lower().values,
    }).sort_values("day", kind="stable").reset_index(drop=True)


def timeline(sub: pd.DataFrame, start: date, end: date) -> list:
    """One row per calendar day from start to end with daily and cumulative counts."""
    seen, out, cum_s, cum_r = set(), [], 0, 0
    by_day = {d: g for d, g in sub.groupby("day")}
    for i in range((end - start).days + 1):
        d = start + timedelta(days=i)
        g = by_day.get(d)
        n = 0 if g is None else len(g)
        new_r = 0
        if g is not None:
            for r in g["responder"]:
                key = r if pd.notna(r) else f"__anon_{len(seen)}"
                if key not in seen:
                    seen.add(key)
                    new_r += 1
        cum_s += n
        cum_r += new_r
        out.append({"date": d.isoformat(), "submissions": n, "new_responders": new_r,
                    "cum_submissions": cum_s, "cum_responders": cum_r})
    return out


def render(data: list, stamp: str, outreach: date = OUTREACH_DATE, target: int = TARGET) -> str:
    tpl = (Path(__file__).parent / "timeline_template.html").read_text()
    last = data[-1]
    first_day = next((d["date"] for d in data if d["submissions"]), data[0]["date"])
    last_day = next((d["date"] for d in reversed(data) if d["submissions"]), data[-1]["date"])
    return (tpl.replace("__DATA__", json.dumps(data))
               .replace("__STAMP__", stamp)
               .replace("__OUTREACH__", outreach.isoformat())
               .replace("__TARGET__", str(target))
               .replace("__SUBS__", str(last["cum_submissions"]))
               .replace("__RESP__", str(last["cum_responders"]))
               .replace("__FIRST__", first_day).replace("__LAST__", last_day))


if __name__ == "__main__":
    now = datetime.now()
    sub = submissions(fetch_runs())
    data = timeline(sub, start=sub["day"].min(), end=datetime.utcnow().date())
    out = ROOT / "reports" / f"uqp_submissions_timeline_{now:%Y-%m-%d}.html"
    out.write_text(render(data, now.strftime("%Y-%m-%d %I:%M%p").lower()))
    print(out)
    print(f"submissions={data[-1]['cum_submissions']} responders={data[-1]['cum_responders']}")
