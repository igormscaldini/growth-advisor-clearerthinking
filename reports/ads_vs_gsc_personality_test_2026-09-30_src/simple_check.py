"""Independent cross-check (no imports from analysis.py): monthly UPT ad spend vs monthly
organic mobile performance for "personality test", as plain correlations of levels and of
month-over-month changes. Months with partial GSC coverage (May 2025, Sep 2026) are dropped."""
import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean

DATA = Path(__file__).parent / "data"
spend = defaultdict(float)
for r in csv.DictReader(open(DATA / "ads_daily.csv")):
    if r["campaign_id"] == "21002171932":
        spend[r["date"][:7]] += float(r["spend"])
clicks, imps, posw = defaultdict(float), defaultdict(float), defaultdict(float)
for r in csv.DictReader(open(DATA / "gsc_query_device_daily.csv")):
    if r["device"] == "MOBILE":
        m = r["date"][:7]
        clicks[m] += float(r["clicks"])
        imps[m] += float(r["impressions"])
        posw[m] += float(r["position"]) * float(r["impressions"])
months = sorted(m for m in clicks if "2025-06" <= m <= "2026-08")
s = [spend[m] for m in months]
c = [clicks[m] for m in months]
p = [posw[m] / imps[m] for m in months]
ctr = [clicks[m] / imps[m] * 100 for m in months]


def correlation(x, y):
    mx, my = mean(x), mean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    return num / (sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y)) ** 0.5


def diff(x):
    return [b - a for a, b in zip(x, x[1:])]


if __name__ == "__main__":
    for m, a, b, d, e in zip(months, s, c, p, ctr):
        print(f"{m}  spend ${a:7.0f}  mobile clicks {b:6.0f}  pos {d:5.2f}  ctr {e:4.2f}%")
    print(f"n={len(months)} months")
    for name, y in (("clicks", c), ("position", p), ("ctr", ctr)):
        print(f"{name:9s} r(levels)={correlation(s, y):+.2f}  r(changes)={correlation(diff(s), diff(y)):+.2f}")
