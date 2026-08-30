import weekly_advisor as wa


def _week(start, **vals):
    d = {"start": start, "end": start, "errors": {}}
    d.update(vals)
    return d


def test_ratio():
    assert wa._ratio(50, 200) == 0.25
    assert wa._ratio(5, 0) is None
    assert wa._ratio(None, 10) is None


def test_flag_data_anomalies_hand_cases():
    history = [
        _week("2026-08-24", tools_finished=0, ga4_users=None, revenue_total=5000, new_subscribers=900, emails_sent=None),
        _week("2026-08-17", tools_finished=1000, ga4_users=40000, revenue_total=1000, new_subscribers=1000, emails_sent=None),
        _week("2026-08-10", tools_finished=1100, ga4_users=42000, revenue_total=1200, new_subscribers=800, emails_sent=None),
        _week("2026-08-03", tools_finished=900, ga4_users=39000, revenue_total=900, new_subscribers=950, emails_sent=None),
    ]
    flags = wa.flag_data_anomalies(history)
    text = "\n".join(flags)
    # tools finished: 0 vs prior median 1000 -> data problem flag
    assert "tools finished" in text and "exactly 0" in text and "1,000" in text
    # GA4 users missing vs prior median 40,000 -> missing flag
    assert "GA4 users is missing" in text and "40,000" in text
    # revenue 5000 vs prior median 1000 -> spike flag (5x > 3x)
    assert "total revenue is 5,000, more than 3x the prior median of 1,000" in text
    # new subscribers 900 vs median 950 -> no flag; emails_sent all None -> no flag
    assert "newsletter" not in text and "emails sent" not in text
    assert len(flags) == 3


def test_flag_data_anomalies_needs_track_record():
    assert wa.flag_data_anomalies([]) == []
    assert wa.flag_data_anomalies([_week("a", tools_finished=0), _week("b", tools_finished=500)]) == []


def test_compute_goal_progress():
    out = wa.compute_goal_progress({
        "gross_revenue_ytd_usd": 60_000, "active_subscribers": 25, "mrr_usd": None,
        "personality_test_google_position": 3.4, "avg_unique_opens_per_campaign": 86_000,
    })
    assert out["gross_revenue_ytd_usd"] == {"current": 60_000, "target": 120_000, "progress_pct": 50.0}
    assert out["active_subscribers"]["progress_pct"] == 25.0
    assert out["mrr_usd"] == {"current": None, "target": 5_000, "progress_pct": None}
    assert out["personality_test_google_position"] == {"current": 3.4, "target": 1, "positions_from_target": 2.4}
    assert out["avg_unique_opens_per_campaign"]["progress_pct"] == 86.0


def test_parse_json_array():
    assert wa.parse_json_array('Here you go:\n[{"entry": "a", "category": "context"}]\nDone.') == [{"entry": "a", "category": "context"}]
    assert wa.parse_json_array("[]") == []
    assert wa.parse_json_array("no json here") == []
    assert wa.parse_json_array("[not valid") == []
    assert wa.parse_json_array('{"entry": "object not array"}') == []


def test_build_email_shape():
    history = [_week("2026-08-24")]
    subject, body = wa.build_email(history, "Solid week.\n\n1. Do X.", {})
    assert subject == "Weekly Growth Report, week of 2026-08-24"
    assert body.startswith("Hi Igor,\n\nSolid week.")
    assert wa.DASHBOARD_URL in body and "Reply to this email" in body
    assert "didn't come through" not in body

    subject, body = wa.build_email(history, "", {"ga4": "boom", "mystery": "x"})
    assert "PARTIAL" in subject
    assert "write-up failed to generate" in body
    assert "ga4: boom" in body and wa.FIX_INSTRUCTIONS["ga4"] in body
    assert "mystery: x" in body


def test_collect_errors_merges_and_drops_empty():
    history = [_week("w", errors={"ga4": "expired"})]
    out = wa.collect_errors(history, {"goals_mrr_usd": "bad"}, {"narrative": None, "consolidation": ""})
    assert out == {"ga4": "expired", "goals_mrr_usd": "bad"}
