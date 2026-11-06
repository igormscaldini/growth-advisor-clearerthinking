"""Tests for reports/ohi_open_rate_drop_2026-11-06_src/analysis.py.

Hand-worked cases first, then two synthetic data sets shaped like the real data.json: one where the open rate
falls only because the audience gets wider (null: nothing Gmail-specific) and one where Gmail alone halves
(positive), then integrity checks on the committed data file.
"""
import importlib.util
import json
import random
from datetime import date, timedelta
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "reports" / "ohi_open_rate_drop_2026-11-06_src"
spec = importlib.util.spec_from_file_location("ohi_drop", SRC / "analysis.py")
od = importlib.util.module_from_spec(spec)
spec.loader.exec_module(od)


def prov(delivered, opens, clicks=0):
    return {"sent": delivered, "delivered": delivered, "opens": opens, "clicks": clicks}


def send(day, gmail, yahoo, hotmail, other=(0, 0), outlook=(0, 0), aol=(0, 0), icloud=(0, 0), recipients=None, kind="ohi"):
    """A send in data.json's shape. Each provider is (delivered, opens[, clicks]); `other` is every remaining domain."""
    parts = [gmail, yahoo, hotmail, outlook, aol, icloud, other]
    delivered, opens = sum(p[0] for p in parts), sum(p[1] for p in parts)
    return {"post_id": f"post_{day}", "date": day, "kind": kind, "title": "One Helpful Idea: x", "subject": "One Helpful Idea: x",
            "from_domain": "ohi", "recipients": recipients or delivered, "delivered": delivered, "opens": opens * 2, "unique_opens": opens,
            "unique_verified_clicks": 0, "unsubscribes": 0, "spam_reports": 0, "html_kb": 50.0, "pixel_24h": 0,
            "providers": {"gmail.com": prov(*gmail), "yahoo.com": prov(*yahoo), "hotmail.com": prov(*hotmail),
                          "outlook.com": prov(*outlook), "aol.com": prov(*aol), "icloud.com": prov(*icloud)}}


# ------------------------------------------------------------------ hand-worked cases
def test_rate_and_audience():
    assert od.rate(1, 4) == 0.25
    assert od.rate(5, 0) is None
    assert od.audience(394_999) == "filtered"
    assert od.audience(395_000) == "whole"


def test_control_totals_pools_the_four_providers_and_skips_icloud():
    s = send("2026-01-06", gmail=(800, 160), yahoo=(60, 30, 3), hotmail=(40, 20, 1), outlook=(10, 5), aol=(10, 5), icloud=(50, 49))
    assert od.control_totals(s["providers"]) == {"delivered": 120, "opens": 60, "clicks": 4}


def test_metrics_by_hand():
    # Gmail 160/800 = 20%. Control (60+40) delivered, (30+20) opens = 50%. Ratio 0.4. Yahoo alone 50% -> same 0.4.
    # Clicks: Gmail 8/800 = 1%, control 4/100 = 4% -> click ratio 0.25.
    s = send("2026-01-06", gmail=(800, 160, 8), yahoo=(60, 30, 3), hotmail=(40, 20, 1), other=(100, 30))
    m = od.metrics(s)
    assert m["delivered"] == 1000 and m["unique_opens"] == 240
    assert m["open_rate"] == pytest.approx(0.24)
    assert m["gmail_rate"] == pytest.approx(0.20)
    assert m["control_rate"] == pytest.approx(0.50)
    assert m["ratio"] == pytest.approx(0.40)
    assert m["yahoo_ratio"] == pytest.approx(0.40)
    assert m["click_ratio"] == pytest.approx(0.25)
    assert m["gmail_clicks_per_10k"] == pytest.approx(100)
    assert m["gmail_share"] == pytest.approx(0.8)
    assert m["audience"] == "filtered"


def test_best_split_by_hand():
    r = od.best_split([1, 1, 1, 0, 0])
    assert r["k"] == 3 and r["mean_before"] == 1 and r["mean_after"] == 0 and r["sse"] == 0
    # one outlier early must not beat a real level shift later
    r = od.best_split([0.6, 0.5, 0.6, 0.6, 0.3, 0.3, 0.3])
    assert r["k"] == 4
    assert r["mean_before"] == pytest.approx(0.575) and r["mean_after"] == pytest.approx(0.3)
    with pytest.raises(ValueError):
        od.best_split([0.5])


def test_counterfactual_by_hand():
    # 1000 delivered, 240 unique opens, of which Gmail 160 on 800 delivered (20%); control opens at 50%.
    # Had Gmail kept 0.6 x control = 30%, it would have opened 240: 80 more. Total 320 -> 32%.
    m = od.metrics(send("2026-10-20", gmail=(800, 160), yahoo=(60, 30), hotmail=(40, 20), other=(100, 30)))
    c = od.counterfactual_open_rate(m, 0.6)
    assert c["cf_gmail_rate"] == pytest.approx(0.30)
    assert c["cf_gmail_opens"] == pytest.approx(240)
    assert c["missing_gmail_opens"] == pytest.approx(80)
    assert c["cf_open_rate"] == pytest.approx(0.32)


def test_counterfactual_at_the_observed_ratio_changes_nothing():
    m = od.metrics(send("2026-10-20", gmail=(800, 160), yahoo=(60, 30), hotmail=(40, 20), other=(100, 30)))
    c = od.counterfactual_open_rate(m, m["ratio"])
    assert c["missing_gmail_opens"] == pytest.approx(0)
    assert c["cf_open_rate"] == pytest.approx(m["open_rate"])


def test_domain_months_by_hand():
    rows = [{"date": "2026-09-01", "from_domain": "ohi", "delivered": 100_000, "unique_opens": 30_000},
            {"date": "2026-09-14", "from_domain": "ohi", "delivered": 100_000, "unique_opens": 10_000},   # 10% -> low-open
            {"date": "2026-09-20", "from_domain": "ohi", "delivered": 10_000, "unique_opens": 500},       # 5% but under 40k -> not counted
            {"date": "2026-09-02", "from_domain": "ct", "delivered": 50_000, "unique_opens": 25_000},
            {"date": "2025-11-30", "from_domain": "ohi", "delivered": 50_000, "unique_opens": 25_000}]     # before the window
    out = {(r["month"], r["from_domain"]): r for r in od.domain_months(rows)}
    assert set(out) == {("2026-09", "ohi"), ("2026-09", "ct")}
    o = out[("2026-09", "ohi")]
    assert (o["sends"], o["delivered"], o["low_open_sends"], o["low_open_delivered"]) == (3, 210_000, 1, 100_000)
    assert o["open_rate"] == pytest.approx(40_500 / 210_000)


def test_nearest_picks_the_closest_date():
    pool = [{"date": "2026-02-03"}, {"date": "2026-03-10"}]
    assert od.nearest({"date": "2026-02-10"}, pool)["date"] == "2026-02-03"
    assert od.nearest({"date": "2026-03-03"}, pool)["date"] == "2026-03-10"


# ------------------------------------------------------------------ synthetic data shaped like the real file
def synthetic(gmail_rate_fn, engaged_rate=0.60, seed=7):
    """26 weekly filtered sends, Jan-Oct 2026. Each send goes to an engaged core (control opens at `engaged_rate`)
    plus a growing block of disengaged readers who open at 5% on every provider, so the headline rate falls by
    dilution alone. gmail_rate_fn(i, control_rate) sets Gmail's rate for send i."""
    rng = random.Random(seed)
    sends, d0 = [], date(2026, 1, 6)
    for i in range(26):
        core, extra = 220_000, (0 if i < 17 else 150_000)         # the audience is widened from send 17 on
        day = (d0 + timedelta(days=11 * i)).isoformat()
        noise = 1 + rng.uniform(-0.02, 0.02)
        control_rate = (core * engaged_rate + extra * 0.05) / (core + extra) * noise
        gmail_rate = gmail_rate_fn(i, control_rate)
        n = core + extra
        g, y, h, o = round(n * 0.82), round(n * 0.03), round(n * 0.03), round(n * 0.12)
        sends.append(send(day, gmail=(g, round(g * gmail_rate)), yahoo=(y, round(y * control_rate)), hotmail=(h, round(h * control_rate)),
                          other=(o, round(o * control_rate * 0.8)), recipients=n))
        if i in (4, 9, 14):      # like the real series: now and then a send to the whole list (Gmail at 0.9 x control there)
            n, c = 410_000, 0.28
            g, y, h, o = round(n * 0.80), round(n * 0.04), round(n * 0.04), round(n * 0.12)
            sends.append(send((d0 + timedelta(days=11 * i + 5)).isoformat(), gmail=(g, round(g * 0.9 * c)), yahoo=(y, round(y * c)),
                              hotmail=(h, round(h * c)), other=(o, round(o * c)), recipients=n))
    return {"pulled": "test", "sends": sends, "all_sends": [{k: s[k] for k in ("date", "from_domain", "delivered", "unique_opens")} for s in sends]}


def test_null_dataset_dilution_only_finds_nothing_gmail_specific():
    # Gmail always opens at 0.62 x the control rate: the headline falls a lot, but nothing is Gmail-specific.
    dp = od.build(synthetic(lambda i, control: 0.62 * control))
    assert sum(m["audience"] == "whole" for m in dp["ohi"]) == 3 and dp["split_whole"] is not None
    first, last = dp["ohi"][0], dp["ohi"][-1]
    # By hand: core only = 0.82*0.372 + 0.06*0.60 + 0.12*0.48 = 39.9%; widened (control 37.7%) = 25.1%. A 14.8-point fall.
    assert first["open_rate"] == pytest.approx(0.399, abs=0.01) and last["open_rate"] == pytest.approx(0.251, abs=0.01)
    assert abs(dp["split"]["mean_before"] - dp["split"]["mean_after"]) < 0.01  # yet the ratio has no break
    assert dp["counterfactual"]["baseline_ratio"] == pytest.approx(0.62, abs=0.005)
    assert dp["counterfactual"]["october_cf"] == pytest.approx(dp["counterfactual"]["october_actual"], abs=0.005)
    assert abs(dp["counterfactual"]["october_missing_gmail_opens"]) < 1500     # under 1% of ~300k Gmail delivered


def test_positive_dataset_gmail_halves_and_the_analysis_recovers_it():
    # Same dilution, plus Gmail's ratio halves (0.62 -> 0.31) from send 20 on.
    dp = od.build(synthetic(lambda i, control: (0.62 if i < 20 else 0.31) * control))
    s = dp["split"]
    assert s["n_before"] == 20 and s["n_after"] == 6
    assert s["mean_before"] == pytest.approx(0.62, abs=0.005) and s["mean_after"] == pytest.approx(0.31, abs=0.005)
    assert dp["split_yahoo_only"]["mean_after"] == pytest.approx(0.31, abs=0.01)
    # The counterfactual must restore exactly what was removed: Gmail back at 0.62 x control.
    filtered = [m for m in dp["ohi"] if m["audience"] == "filtered"]
    for c, m in zip(dp["counterfactual"]["per_send"], filtered[20:]):
        assert c["cf_gmail_rate"] == pytest.approx(0.62 * m["control_rate"], rel=0.01)
        assert c["missing_gmail_opens"] == pytest.approx(0.31 * m["control_rate"] * m["gmail_delivered"], rel=0.03)
    assert dp["counterfactual"]["october_cf"] > dp["counterfactual"]["october_actual"] + 0.04


# ------------------------------------------------------------------ the committed data file
@pytest.fixture(scope="module")
def real():
    return json.load(open(SRC / "data.json"))


def test_real_data_is_internally_consistent(real):
    assert len(real["sends"]) == 52 and sum(s["kind"] == "ohi" for s in real["sends"]) == 40
    for s in real["sends"]:
        p = s["providers"]
        for row in p.values():
            assert row["opens"] <= row["delivered"] <= row["sent"]
        # the six providers are a subset of the send, so they can never exceed its totals
        assert sum(r["delivered"] for r in p.values()) <= s["delivered"]
        assert sum(r["opens"] for r in p.values()) <= s["unique_opens"]
        assert 0.69 <= p["gmail.com"]["delivered"] / s["delivered"] <= 0.90


def test_real_data_headline_findings(real):
    dp = od.build(real)
    assert (dp["split"]["last_before"], dp["split"]["first_after"]) == ("2026-08-05", "2026-08-18")
    assert dp["split"]["min_before"] > dp["split"]["max_after"]            # the two periods do not overlap at all
    assert (dp["split_yahoo_only"]["last_before"], dp["split_yahoo_only"]["first_after"]) == ("2026-08-05", "2026-08-18")
    assert dp["periods"]["january"]["open_rate"] == pytest.approx(0.453, abs=0.002)
    assert dp["periods"]["october"]["open_rate"] == pytest.approx(0.213, abs=0.002)
    # audience rule is clean: control opens at 25-32% on whole-list sends and above 45% on filtered ones
    for m in dp["ohi"]:
        assert (m["control_rate"] < 0.32) == (m["audience"] == "whole")


def test_build_copes_with_no_whole_list_sends():
    data = synthetic(lambda i, control: 0.62 * control)
    data["sends"] = [s for s in data["sends"] if s["recipients"] < od.WHOLE_LIST_MIN]
    dp = od.build(data)
    assert dp["split_whole"] is None and dp["whole_vs_filtered"] == []


def test_mean_known_skips_missing_values():
    assert od.mean_known([0.2, None, 0.4]) == pytest.approx(0.3)
    assert od.mean_known([None]) is None
    # a send whose control group never clicked has no click ratio, and build() must still run (the synthetic sets have no clicks)
    m = od.metrics(send("2026-01-06", gmail=(800, 160, 8), yahoo=(60, 30), hotmail=(40, 20)))
    assert m["click_ratio"] is None
