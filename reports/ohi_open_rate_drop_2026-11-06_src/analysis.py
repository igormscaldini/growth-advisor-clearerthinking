"""Why did the One Helpful Idea (OHI) open rate fall in 2026?  data.json -> datapoints.json

    python analysis.py

Method in one paragraph. Every send is split by mailbox provider. Gmail is compared with a control group of
providers (Yahoo, Hotmail, Outlook, AOL) INSIDE THE SAME SEND, so anything that hits all readers alike (the topic,
the subject line, the send time, a wider or narrower audience) moves both and leaves the Gmail/control ratio
alone. A fall in that ratio is therefore something Gmail-specific. iCloud is left out of the control group
because Apple's Mail Privacy Protection flips its open rate between about 8% and 89% from one send to the next.

All rates are unique opens / delivered. Tests: tests/test_ohi_open_rate_drop.py.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean, median

HERE = Path(__file__).resolve().parent
CONTROL = ("yahoo.com", "hotmail.com", "outlook.com", "aol.com")
# In 2026 every OHI send was either filtered to engaged readers (218k-376k recipients) or sent to nearly the whole
# list (400k-464k). The control group's open rate confirms the split is clean: 25-31% vs 46-67%, nothing between.
WHOLE_LIST_MIN = 395_000
NARROW_MAX = 250_000      # the engaged audience before it was widened in September (218k-250k)
LOW_OPEN_RATE = 0.15      # a "low-open" send: under 15% unique opens ...
LOW_OPEN_MIN_DELIVERED = 40_000   # ... on at least 40k delivered
GMAIL_CLIP_KB = 102


def rate(n: float, d: float) -> float | None:
    return n / d if d else None


def audience(recipients: int) -> str:
    return "whole" if recipients >= WHOLE_LIST_MIN else "filtered"


def control_totals(providers: dict, names: tuple = CONTROL) -> dict:
    return {k: sum(providers[n][k] for n in names) for k in ("delivered", "opens", "clicks")}


def metrics(send: dict) -> dict:
    """Per-send rates. `ratio` = Gmail open rate / control open rate; `click_ratio` likewise for clicks."""
    p, g, c = send["providers"], send["providers"]["gmail.com"], control_totals(send["providers"])
    gmail_rate, control_rate = rate(g["opens"], g["delivered"]), rate(c["opens"], c["delivered"])
    gmail_click, control_click = rate(g["clicks"], g["delivered"]), rate(c["clicks"], c["delivered"])
    yahoo_rate = rate(p["yahoo.com"]["opens"], p["yahoo.com"]["delivered"])
    return {
        "date": send["date"], "post_id": send["post_id"], "kind": send["kind"], "subject": send["subject"], "title": send["title"],
        "from_domain": send["from_domain"], "recipients": send["recipients"], "delivered": send["delivered"],
        "unique_opens": send["unique_opens"], "audience": audience(send["recipients"]),
        "open_rate": rate(send["unique_opens"], send["delivered"]),
        "gmail_delivered": g["delivered"], "gmail_opens": g["opens"], "gmail_rate": gmail_rate,
        "control_delivered": c["delivered"], "control_rate": control_rate,
        "ratio": gmail_rate / control_rate if control_rate else None,
        "yahoo_ratio": gmail_rate / yahoo_rate if yahoo_rate else None,
        "gmail_clicks_per_10k": 1e4 * gmail_click, "control_clicks_per_10k": 1e4 * control_click,
        "click_ratio": gmail_click / control_click if control_click else None,
        "icloud_rate": rate(p["icloud.com"]["opens"], p["icloud.com"]["delivered"]),
        "gmail_share": rate(g["delivered"], send["delivered"]),
        "html_kb": send.get("html_kb"), "pixel_24h": send.get("pixel_24h"), "opens": send["opens"],
        "unsubscribes": send["unsubscribes"], "spam_reports": send["spam_reports"], "segment": send.get("segment", ""),
    }


def best_split(values: list[float]) -> dict:
    """Single change point: the split of an ordered series into [0:k] and [k:] with the least squared error
    around the two means. Returns k (index of the first value AFTER the break) and both means."""
    if len(values) < 2:
        raise ValueError("need at least two values")
    best = None
    for k in range(1, len(values)):
        a, b = values[:k], values[k:]
        ma, mb = mean(a), mean(b)
        sse = sum((x - ma) ** 2 for x in a) + sum((x - mb) ** 2 for x in b)
        if best is None or sse < best["sse"]:
            best = {"k": k, "mean_before": ma, "mean_after": mb, "sse": sse}
    return best


def counterfactual_open_rate(m: dict, baseline_ratio: float) -> dict:
    """Open rate the send would have had if Gmail had kept `baseline_ratio` to the control group's rate
    in that same send. Everything except Gmail's opens is left as observed."""
    cf_gmail_rate = baseline_ratio * m["control_rate"]
    cf_gmail_opens = cf_gmail_rate * m["gmail_delivered"]
    cf_unique = m["unique_opens"] - m["gmail_opens"] + cf_gmail_opens
    return {"cf_gmail_rate": cf_gmail_rate, "cf_gmail_opens": cf_gmail_opens, "missing_gmail_opens": cf_gmail_opens - m["gmail_opens"],
            "cf_open_rate": cf_unique / m["delivered"]}


def mean_known(values) -> float | None:
    """Mean of the values that exist (a send with no control-group clicks has no click ratio)."""
    vals = [v for v in values if v is not None]
    return mean(vals) if vals else None


def avg(rows: list[dict], keys: tuple) -> dict:
    out = {k: mean(r[k] for r in rows) for k in keys}
    out["n"] = len(rows)
    out["dates"] = [r["date"] for r in rows]
    return out


def nearest(target: dict, pool: list[dict]) -> dict:
    d0 = date.fromisoformat(target["date"])
    return min(pool, key=lambda r: abs((date.fromisoformat(r["date"]) - d0).days))


def domain_months(all_sends: list[dict], start: str = "2025-12") -> list[dict]:
    acc: dict = defaultdict(lambda: defaultdict(float))
    for s in all_sends:
        month = s["date"][:7]
        if month < start:
            continue
        a = acc[(month, s["from_domain"])]
        a["sends"] += 1
        a["delivered"] += s["delivered"]
        a["unique_opens"] += s["unique_opens"]
        if s["delivered"] >= LOW_OPEN_MIN_DELIVERED and s["unique_opens"] / s["delivered"] < LOW_OPEN_RATE:
            a["low_open_delivered"] += s["delivered"]
            a["low_open_sends"] += 1
    return [{"month": m, "from_domain": d, "sends": int(a["sends"]), "delivered": int(a["delivered"]),
             "open_rate": a["unique_opens"] / a["delivered"], "low_open_delivered": int(a["low_open_delivered"]),
             "low_open_sends": int(a["low_open_sends"])} for (m, d), a in sorted(acc.items())]


def build(data: dict, year: str = "2026") -> dict:
    KEYS = ("open_rate", "gmail_rate", "control_rate", "ratio", "recipients", "unique_opens", "gmail_opens")
    allm = [metrics(s) for s in data["sends"]]
    ohi = [m for m in allm if m["kind"] == "ohi" and m["date"].startswith(year)]
    filt = [m for m in ohi if m["audience"] == "filtered"]
    whole = [m for m in ohi if m["audience"] == "whole"]

    sp = best_split([m["ratio"] for m in filt])
    before, after = filt[:sp["k"]], filt[sp["k"]:]
    wsp = best_split([m["ratio"] for m in whole]) if len(whole) >= 2 else None
    ysp = best_split([m["yahoo_ratio"] for m in filt])     # same test with Yahoo alone as the control
    baseline = median(m["ratio"] for m in before)

    cf = [{"date": m["date"], "open_rate": m["open_rate"], **counterfactual_open_rate(m, baseline)} for m in after]
    october = [m for m in filt if m["date"][5:7] == "10"]
    oct_cf = [c for c in cf if c["date"][5:7] == "10"]
    january = [m for m in filt if m["date"][5:7] == "01"]
    last3_before = before[-3:]
    same_audience_after = [m for m in after if m["recipients"] <= max(b["recipients"] for b in last3_before) * 1.05]

    # Each whole-list send against the nearest send to the narrow engaged audience: what did the extra recipients add?
    narrow = [m for m in filt if m["recipients"] <= NARROW_MAX]
    pairs = []
    for w in whole if narrow else []:
        n = nearest(w, narrow)
        pairs.append({"whole_date": w["date"], "filtered_date": n["date"], "whole_recipients": w["recipients"], "filtered_recipients": n["recipients"],
                      "whole_unique_opens": w["unique_opens"], "filtered_unique_opens": n["unique_opens"],
                      "extra_unique_opens": w["unique_opens"] - n["unique_opens"], "extra_gmail_opens": w["gmail_opens"] - n["gmail_opens"]})

    pix = [m for m in ohi if m["pixel_24h"] and m["pixel_24h"] / m["opens"] > 0.2]
    click_before = [m["click_ratio"] for m in before]
    click_after_not_oct = [m["click_ratio"] for m in after if m["date"][5:7] != "10"]

    return {
        "pulled": data.get("pulled"), "control_providers": list(CONTROL), "whole_list_min": WHOLE_LIST_MIN,
        "ohi": ohi, "other": [m for m in allm if m["kind"] != "ohi"],
        "split": {"k": sp["k"], "last_before": before[-1]["date"], "first_after": after[0]["date"], "n_before": len(before), "n_after": len(after),
                  "mean_before": sp["mean_before"], "mean_after": sp["mean_after"],
                  "min_before": min(m["ratio"] for m in before), "max_before": max(m["ratio"] for m in before),
                  "min_after": min(m["ratio"] for m in after), "max_after": max(m["ratio"] for m in after)},
        "split_whole": wsp and {"last_before": whole[wsp["k"] - 1]["date"], "first_after": whole[wsp["k"]]["date"],
                                "mean_before": wsp["mean_before"], "mean_after": wsp["mean_after"],
                                "n_before": wsp["k"], "n_after": len(whole) - wsp["k"]},
        "split_yahoo_only": {"last_before": filt[ysp["k"] - 1]["date"], "first_after": filt[ysp["k"]]["date"],
                             "mean_before": ysp["mean_before"], "mean_after": ysp["mean_after"]},
        "periods": {"january": avg(january, KEYS), "before_break": avg(last3_before, KEYS),
                    "after_break_same_audience": avg(same_audience_after, KEYS), "october": avg(october, KEYS)},
        "counterfactual": {"baseline_ratio": baseline, "per_send": cf,
                           "october_actual": mean(c["open_rate"] for c in oct_cf), "october_cf": mean(c["cf_open_rate"] for c in oct_cf),
                           "october_missing_gmail_opens": mean(c["missing_gmail_opens"] for c in oct_cf)},
        "clicks": {"ratio_before": mean_known(click_before), "ratio_after_aug_sep": mean_known(click_after_not_oct),
                   "ratio_october": mean_known(m["click_ratio"] for m in october),
                   "gmail_per_10k_before": mean_known(m["gmail_clicks_per_10k"] for m in before),
                   "gmail_per_10k_after_aug_sep": mean_known(m["gmail_clicks_per_10k"] for m in after if m["date"][5:7] != "10"),
                   "gmail_per_10k_october": mean_known(m["gmail_clicks_per_10k"] for m in october),
                   "control_per_10k_before": mean_known(m["control_clicks_per_10k"] for m in before),
                   "control_per_10k_october": mean_known(m["control_clicks_per_10k"] for m in october)},
        "whole_vs_filtered": pairs,
        "domain_months": domain_months(data["all_sends"]),
        "pixel": {"n": len(pix), "first": pix[0]["date"] if pix else None,
                  "min_ratio": min(m["pixel_24h"] / m["opens"] for m in pix) if pix else None,
                  "max_ratio": max(m["pixel_24h"] / m["opens"] for m in pix) if pix else None,
                  "before_break": [round(m["pixel_24h"] / m["opens"], 3) for m in pix if m["date"] <= before[-1]["date"]],
                  "after_break": [round(m["pixel_24h"] / m["opens"], 3) for m in pix if m["date"] > before[-1]["date"]]},
        "html": {"min_kb": min(m["html_kb"] for m in ohi), "max_kb": max(m["html_kb"] for m in ohi),
                 "over_clip": [m["date"] for m in ohi if m["html_kb"] > GMAIL_CLIP_KB],
                 "median_before_kb": median(m["html_kb"] for m in before), "median_after_kb": median(m["html_kb"] for m in after)},
    }


def main() -> None:
    dp = build(json.load(open(HERE / "data.json")))
    json.dump(dp, open(HERE / "datapoints.json", "w"), indent=1, ensure_ascii=False)
    s, p, c = dp["split"], dp["periods"], dp["counterfactual"]
    print(f"break between {s['last_before']} and {s['first_after']}: Gmail/control ratio {s['mean_before']:.2f} (n={s['n_before']}, "
          f"{s['min_before']:.2f}-{s['max_before']:.2f}) -> {s['mean_after']:.2f} (n={s['n_after']}, {s['min_after']:.2f}-{s['max_after']:.2f})")
    for k, v in p.items():
        print(f"  {k:26} open {100*v['open_rate']:.1f}%  gmail {100*v['gmail_rate']:.1f}%  control {100*v['control_rate']:.1f}%  "
              f"recipients {v['recipients']:,.0f}  unique opens {v['unique_opens']:,.0f}  {v['dates']}")
    print(f"October: actual {100*c['october_actual']:.1f}% vs {100*c['october_cf']:.1f}% had Gmail kept its usual ratio ({c['baseline_ratio']:.2f}); "
          f"{c['october_missing_gmail_opens']:,.0f} Gmail opens missing per send")


if __name__ == "__main__":
    main()
