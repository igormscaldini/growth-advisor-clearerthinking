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

    subject, body = wa.build_email(history, "Solid week.", {"ga4": "boom", "mystery": "x"})
    assert subject == "Weekly Growth Report, week of 2026-08-24 ⚠️ PARTIAL, some sources failed"
    assert body.index("Solid week.") < body.index("didn't come through") < body.index("ga4: boom")
    assert wa.FIX_INSTRUCTIONS["ga4"] in body
    assert "mystery: x" in body
    assert "Total revenue" not in body   # the numbers fallback is only for a missing letter


def test_build_email_without_letter_leads_with_the_fix_and_carries_numbers():
    history = [_week("2026-08-24", end="2026-08-30", revenue_total=1500),
               _week("2026-08-17", revenue_total=1000)]
    goals = wa.compute_goal_progress({"active_subscribers": 25})
    subject, body = wa.build_email(history, "", {"narrative": "RuntimeError: Not logged in"}, goals)
    assert subject == "Weekly Growth Report, week of 2026-08-24 ⚠️ NO LETTER, numbers only"
    assert "PARTIAL" not in subject
    # reason and fix come first, then the numbers, then the footer
    assert (body.index("couldn't write this week's letter") < body.index("narrative: RuntimeError: Not logged in")
            < body.index(wa.FIX_INSTRUCTIONS["narrative"]) < body.index("The week of 2026-08-24 to 2026-08-30:")
            < body.index("Total revenue: $1,500") < body.index("Active subscribers: 25 of 100 (25.0%)")
            < body.index(wa.DASHBOARD_URL))
    assert "didn't come through" not in body


def test_numbers_summary_hand_cases():
    history = [
        _week("2026-09-25", end="2026-10-01", revenue_total=1500.4, new_subscribers=2000, pdf_sales=None),
        _week("2026-09-18", revenue_total=1000, new_subscribers=3000, pdf_sales=4),
        _week("2026-09-11", revenue_total=2000, new_subscribers=1000, pdf_sales=None),
        _week("2026-09-04", revenue_total=3000, new_subscribers=2500, pdf_sales=6),
    ]
    goals = wa.compute_goal_progress({
        "gross_revenue_ytd_usd": 60_000, "active_subscribers": 25, "mrr_usd": None,
        "personality_test_google_position": 3.44, "avg_unique_opens_per_campaign": 86_000,
    })
    lines = wa.numbers_summary(history, goals).split("\n")
    assert lines[0] == "The week of 2026-09-25 to 2026-10-01:"
    # median of 1000, 2000, 3000 = 2000
    assert "  Total revenue: $1,500 (week before $1,000, median of the prior 3 weeks $2,000)" in lines
    # median of 3000, 1000, 2500 = 2500
    assert "  New newsletter subscribers: 2,000 (week before 3,000, median of the prior 3 weeks 2,500)" in lines
    # missing this week; median of the two known prior values 4 and 6 = 5
    assert "  PDF sales: n/a (week before 4, median of the prior 3 weeks 5)" in lines
    # never reported at all
    assert "  GA4 users: n/a (week before n/a, median of the prior 3 weeks n/a)" in lines
    assert len([l for l in lines if "week before" in l]) == len(wa.SUMMARY_ROWS)
    assert "  Total revenue this year: $60,000 of $120,000 (50.0%)" in lines
    assert "  Active subscribers: 25 of 100 (25.0%)" in lines
    assert "  MRR: n/a of $5,000" in lines
    assert "  Average unique opens per campaign: 86,000 of 100,000 (86.0%)" in lines
    assert '  Google position for "personality test": 3.4 (target 1)' in lines
    assert "Data-quality flags:" not in lines   # nothing here is 0, missing-after-data or >3x


def test_numbers_summary_edge_cases():
    assert wa.numbers_summary([]) == ""
    # a single week: no comparison, no goals section when goals are not given
    text = wa.numbers_summary([_week("2026-09-25", revenue_total=10)])
    assert "  Total revenue: $10\n" in text
    assert "week before" not in text and "Goals:" not in text
    # every summary and goal key exists where the letter's data comes from
    assert {key for _, key, _ in wa.GOAL_ROWS} == set(wa.GOAL_TARGETS)
    # an anomaly (revenue 0 against a prior median of 1,000) is repeated under the numbers
    history = [_week("w4", revenue_total=0), _week("w3", revenue_total=1000),
               _week("w2", revenue_total=1000), _week("w1", revenue_total=1000)]
    assert "Data-quality flags:\n  total revenue is exactly 0 this week" in wa.numbers_summary(history)


def test_finish_and_send_exit_code_tracks_the_letter(capsys):
    history = [_week("2026-08-24")]
    assert wa.finish_and_send(history, "Solid week.", {}, dry_run=True) == 0
    assert wa.finish_and_send(history, "Solid week.", {"beehiiv": "429"}, dry_run=True) == 0
    assert wa.finish_and_send(history, "", {"narrative": "boom"}, dry_run=True) == 1
    assert "NO LETTER" in capsys.readouterr().out


def test_send_or_alert_files_the_email_in_the_inbox(monkeypatch):
    calls = []
    monkeypatch.setattr(wa.email_transport, "send_email", lambda *a, **k: calls.append((a, k)))
    assert wa.send_or_alert("Subj", "Body", "report", "Weekly growth report") is True
    (args, kwargs), = calls
    assert args[:2] == ("Subj", "Body")
    assert kwargs["to_inbox"] is True and kwargs["header_tag"] == "report"

    def down(*a, **k):
        raise RuntimeError("gmail down")

    slack = []
    monkeypatch.setattr(wa.email_transport, "send_email", down)
    monkeypatch.setattr(wa.email_transport, "slack_fallback", lambda *a: slack.append(a) or True)
    assert wa.send_or_alert("Subj", "Body", "report", "Weekly growth report") is False
    assert "gmail down" in slack[0][0] and slack[0][1] == "Weekly growth report"


def test_run_preflight_collects_raises_and_error_results():
    def boom():
        raise ValueError("token expired")

    errors = wa.run_preflight({
        "ga4_audience": lambda: {"users": 10},
        "goals_active_subscribers": lambda: 0,          # a falsy but valid answer is a pass
        "memory": lambda: "",
        "narrative": boom,
        "beehiiv": lambda: {"error": "BEEHIIV_API_KEY rejected (401)"},
    })
    assert errors == {"narrative": "ValueError: token expired", "beehiiv": "BEEHIIV_API_KEY rejected (401)"}
    assert wa.run_preflight({}) == {}


def test_preflight_checks_cover_known_fix_instructions():
    from datetime import date
    assert set(wa.preflight_checks(date(2026, 10, 1))) <= set(wa.FIX_INSTRUCTIONS)


def test_build_preflight_email():
    subject, body = wa.build_preflight_email({"narrative": "Not logged in"})
    assert subject == "Growth advisor preflight: 1 thing to fix before Friday's letter"
    assert "narrative: Not logged in" in body and wa.FIX_INSTRUCTIONS["narrative"] in body
    assert "gh workflow run weekly-advisor-email.yml -f preflight=true" in body
    subject, _ = wa.build_preflight_email({"narrative": "a", "memory": "b"})
    assert subject.startswith("Growth advisor preflight: 2 things to fix")
    # must never look like a reply to the weekly report to the reply poller
    import advisor_reply
    assert advisor_reply.SUBJECT_MATCH not in subject


def test_preflight_mode(monkeypatch, capsys):
    from datetime import date
    ref = date(2026, 10, 1)
    monkeypatch.setattr(wa, "preflight_checks", lambda r: {"narrative": lambda: "OK", "memory": lambda: "m"})
    assert wa.preflight_mode(ref, dry_run=True) == 0
    assert capsys.readouterr().out == ""            # all good: nothing to send

    def boom():
        raise RuntimeError("Claude Code: Not logged in")

    sent = []
    monkeypatch.setattr(wa, "preflight_checks", lambda r: {"narrative": boom})
    monkeypatch.setattr(wa, "send_or_alert", lambda *a: sent.append(a) or True)
    assert wa.preflight_mode(ref, dry_run=True) == 1
    assert "1 thing to fix" in capsys.readouterr().out and sent == []
    assert wa.preflight_mode(ref, dry_run=False) == 1
    assert sent[0][2] == "preflight" and "Not logged in" in sent[0][1]


def test_collect_errors_merges_and_drops_empty():
    history = [_week("w", errors={"ga4": "expired"})]
    out = wa.collect_errors(history, {"goals_mrr_usd": "bad"}, {"narrative": None, "consolidation": ""})
    assert out == {"ga4": "expired", "goals_mrr_usd": "bad"}


def test_manual_revenue_total_matches_dashboard_lines():
    import fetch_snapshot as fs
    expected = round(sum(amt for items in fs.MANUAL_REVENUE.values() for _, amt in items), 2)
    assert wa.manual_revenue_total() == expected
    assert expected > 0
