"""Build reports/ads_vs_gsc_personality_test_2026-09-30.html from data/ (run fetch_data.py first)."""
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import analysis as A  # noqa: E402
import simple_check as S  # noqa: E402

START, END = "2025-05-18", "2026-09-27"
OUT = HERE.parent / "ads_vs_gsc_personality_test_2026-09-30.html"


def compute() -> dict:
    ads = pd.read_csv(HERE / "data/ads_daily.csv")
    gsc = pd.read_csv(HERE / "data/gsc_query_device_daily.csv")
    pr = pd.read_csv(HERE / "data/positly_runs_daily.csv")
    terms = pd.read_csv(HERE / "data/ads_search_terms.csv")
    spend = ads[ads.campaign_id == A.UPT_CAMPAIGN_ID].set_index("date")["spend"]
    on = A.on_flag(spend, START, END)
    mob, alld = A.gsc_daily(gsc, ["MOBILE"]), A.gsc_daily(gsc)
    runs = pr.set_index(pd.to_datetime(pr["date"]))["runs"].reindex(on.index, fill_value=0)
    ctl = pd.DataFrame({"runs": runs})
    outcomes = {
        "Mobile organic clicks / day": (mob["clicks"], 1),
        "Mobile organic CTR (%)": (mob["ctr"] * 100, 2),
        "Mobile organic position": (mob["position"], 2),
        "All-device organic position": (alld["position"], 2),
    }
    tests = []
    for name, (y, dp) in outcomes.items():
        base = y[on.reindex(y.index) == 0].mean()
        row = {"outcome": name, "dp": dp, "off_mean": base}
        for lag in (0, 28):
            r = A.shift_null(y, on, controls=ctl, lag=lag)
            row[f"coef{lag}"], row[f"p{lag}"] = r["coef"], r["p_value"]
            row[f"mde{lag}"] = 2 * r["null_sd"]
            row["n_shifts"] = r["n_shifts"]
        row["hac"] = A.regress_on_flag(y, on, control=runs)
        sw = A.switch_effects(y, on, window=14)
        row["switches"] = sw[["switch_date", "direction", "pct"]].to_dict("records")
        tests.append(row)

    periods = A.period_means(mob["clicks"], on)
    periods["position"] = A.period_means(mob["position"], on)["mean"]
    periods["ctr"] = A.period_means(mob["ctr"] * 100, on)["mean"]
    sp = spend.copy()
    sp.index = pd.to_datetime(sp.index)
    periods["spend_day"] = [sp[r.start:r.end].sum() / r.days for r in periods.itertuples()]
    terms["days"] = (pd.to_datetime(terms.period_end) - pd.to_datetime(terms.period_start)).dt.days + 1
    dose = {}
    for (a, days), g in terms.groupby(["period_start", "days"]):
        pt = g[g.category == A.QUERY]
        dose[a] = {"impr_day": pt.impressions.sum() / days, "clicks_day": pt.clicks.sum() / days,
                   "top": g.groupby("category").impressions.sum().drop("", errors="ignore")
                           .sort_values(ascending=False).head(3).index.tolist()}
    wk = pd.DataFrame({"clicks": mob["clicks"], "position": mob["position"],
                       "on": on.reindex(mob.index)}).resample("W-SUN", label="left").mean()
    weekly = [{"week": d.date().isoformat(), "clicks": round(r.clicks, 1), "position": round(r.position, 2),
               "on": round(r.on, 2)} for d, r in wk.iterrows() if not np.isnan(r.clicks)]
    monthly = [{"month": m, "spend": a, "clicks": b, "position": c}
               for m, a, b, c in zip(S.months, S.s, S.c, S.p)]
    simple = {k: {"levels": S.correlation(S.s, y), "changes": S.correlation(S.diff(S.s), S.diff(y))}
              for k, y in (("clicks", S.c), ("position", S.p), ("ctr", S.ctr))}
    return {"tests": tests, "periods": periods.to_dict("records"), "dose": dose, "weekly": weekly,
            "on_periods": A.on_periods(spend, START, END), "monthly": monthly, "simple": simple,
            "positly_wave2_start": "2026-04-16"}


def fmt(x, dp=1, sign=False):
    return f"{x:+.{dp}f}" if sign else f"{x:.{dp}f}"


def short(iso: str) -> str:
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %-d, %Y")


def render(d: dict) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d %I:%M%p").lower()
    per_rows = ""
    for r in d["periods"]:
        keys = [k for k in d["dose"] if k <= r["start"]]
        dz = d["dose"][max(keys)] if r["on"] and keys else None
        per_rows += (f"<tr><td style='white-space:nowrap'>{short(r['start'])} to {short(r['end'])}</td><td>{'<b>ON</b>' if r['on'] else 'off'}</td>"
                     f"<td class=n>{r['days']}</td><td class=n>${r['spend_day']:.0f}</td>"
                     f"<td class=n>{'%.0f' % dz['impr_day'] if dz else ''}</td>"
                     f"<td class=n>{'%.0f' % dz['clicks_day'] if dz else ''}</td>"
                     f"<td class=n>{r['mean']:.1f}</td><td class=n>{r['ctr']:.2f}%</td><td class=n>{r['position']:.2f}</td></tr>")
    test_rows = ""
    for t in d["tests"]:
        dp = t["dp"]
        sw = " ".join(f"<span class=chip>{s['switch_date'][:7]} {s['direction']}: {s['pct']:+.0f}%</span>" for s in t["switches"])
        test_rows += (f"<tr><td>{t['outcome']}</td><td class=n>{fmt(t['off_mean'], dp)}</td>"
                      f"<td class=n>{fmt(t['coef0'], dp, True)}</td><td class=n>{t['p0']:.2f}</td>"
                      f"<td class=n>&plusmn;{fmt(t['mde0'], dp)}</td>"
                      f"<td class=n>{fmt(t['coef28'], dp, True)}</td><td class=n>{t['p28']:.2f}</td>"
                      f"<td>{sw}</td></tr>")
    mo_rows = "".join(f"<tr><td>{m['month']}</td><td class=n>${m['spend']:,.0f}</td><td class=n>{m['clicks']:,.0f}</td>"
                      f"<td class=n>{m['position']:.2f}</td></tr>" for m in d["monthly"])
    s = d["simple"]
    t0 = d["tests"][0]
    html = TEMPLATE
    for k, v in {
        "{{STAMP}}": stamp, "{{DATA}}": json.dumps({"weekly": d["weekly"], "on": d["on_periods"],
                                                   "positly": d["positly_wave2_start"]}),
        "{{PER_ROWS}}": per_rows, "{{TEST_ROWS}}": test_rows, "{{MO_ROWS}}": mo_rows,
        "{{CLICK_COEF}}": fmt(t0["coef0"], 1, True), "{{CLICK_P}}": f"{t0['p0']:.2f}",
        "{{CLICK_MDE}}": fmt(t0["mde0"], 0), "{{CLICK_BASE}}": fmt(t0["off_mean"], 0),
        "{{CLICK_P_PCT}}": f"{t0['p0'] * 100:.0f}%", "{{N_SHIFTS}}": str(t0["n_shifts"]),
        "{{CTR_HAC_P}}": f"{d['tests'][1]['hac']['p_value']:.2f}",
        "{{POS_P}}": f"{d['tests'][2]['p0']:.2f}", "{{CTR_P}}": f"{d['tests'][1]['p0']:.2f}",
        "{{R_CLICK_L}}": f"{s['clicks']['levels']:+.2f}", "{{R_CLICK_C}}": f"{s['clicks']['changes']:+.2f}",
        "{{R_POS_L}}": f"{s['position']['levels']:+.2f}", "{{R_POS_C}}": f"{s['position']['changes']:+.2f}",
        "{{N_MONTHS}}": str(len(d["monthly"])),
    }.items():
        html = html.replace(k, v)
    return html


TEMPLATE = (HERE / "template.html").read_text() if (HERE / "template.html").exists() else ""

if __name__ == "__main__":
    data = compute()
    (HERE / "datapoints.json").write_text(json.dumps(data, indent=1, default=float))
    OUT.write_text(render(data))
    print("wrote", OUT)
