from datetime import datetime, timezone

import pytest

import accountability_pairs as ap


def row(email, optin="1", gender="Woman", project="", started="2026-11-20 10:00:00"):
    return {"signupEmail": email, "accountabilityOptIn": optin, "partnerGenderAnswer": gender,
            "projectToWorkOn": project, "Time Started (UTC)": started}


def ppl(**kw):
    """email -> person, from gender letters: ppl(a="W", b="M:my thesis")"""
    out = {}
    for e, spec in kw.items():
        g, _, proj = spec.partition(":")
        out[e] = {"email": e, "gender": "Woman" if g == "W" else "Man", "project": proj}
    return out


def test_latest_row_decides_and_later_no_removes_earlier_yes():
    rows = [row("a@x.com", "1", started="2026-11-18 10:00:00"), row("a@x.com", "0", gender="", started="2026-11-19"),
            row("b@x.com", "0", gender="", started="2026-11-18"), row("b@x.com", "1", "Man", started="2026-11-24")]
    out = ap.eligible_people(rows, set())
    assert list(out) == ["b@x.com"] and out["b@x.com"]["gender"] == "Man"


def test_uses_raw_gender_answer_and_keeps_newest_nonempty_project():
    rows = [row("a@x.com", project="old idea", started="2026-11-18"), row("A@x.com ", project="", started="2026-11-24")]
    out = ap.eligible_people(rows, set())
    assert out["a@x.com"]["project"] == "old idea" and out["a@x.com"]["gender"] == "Woman"


def test_drops_unfinished_rows_excluded_tests_and_declined_gender():
    rows = [row("u@x.com", optin=""), row("ex@x.com"), row("igormscaldini+qa@gmail.com"),
            row("n@x.com", gender="I'd rather not be paired after all"), row("ok@x.com")]
    assert list(ap.eligible_people(rows, {"ex@x.com"})) == ["ok@x.com"]


def test_keep_pairs_keeps_intact_pairs_and_frees_orphans():
    people = ppl(a="W", b="W", c="W", e="M", f="M")  # d left; e,f new
    reviewed = [{"emails": ["A", "b", ""]}, {"emails": ["c", "d", ""]}]
    kept, left = ap.keep_pairs(reviewed, people)
    assert [p["emails"] for p in kept] == [["a", "b"]] and sorted(left) == ["c", "e", "f"]


def test_keep_pairs_drops_mixed_gender_rows():
    kept, left = ap.keep_pairs([{"emails": ["a", "b"]}], ppl(a="W", b="M"))
    assert kept == [] and sorted(left) == ["a", "b"]


def test_fallback_pairs_by_shared_words_and_makes_trio_for_odd_one():
    people = ppl(a="W:finish my phd thesis", b="W:write a novel", c="W:phd thesis draft", d="W:novel writing",
                 e="W:", k1="W:", k2="W:")
    kept = [{"emails": ["k1", "k2"], "why": ""}]
    new = ap.fallback_pairs(["a", "b", "c", "d", "e"], people, kept)
    groups = sorted(sorted(p["emails"]) for p in kept + new)
    assert ["a", "c"] in groups and ["b", "d"] in groups and ["e", "k1", "k2"] in groups
    ap.validate_plan(kept + new, people)


def test_validate_plan_catches_every_rule():
    people = ppl(a="W", b="W", c="M", d="M")
    ap.validate_plan([{"emails": ["a", "b"]}, {"emails": ["c", "d"]}], people)
    bad = [([{"emails": ["a", "c"]}, {"emails": ["b", "d"]}], "mixes"),
           ([{"emails": ["a", "b"]}], "left out"),
           ([{"emails": ["a", "b"]}, {"emails": ["c", "d"]}, {"emails": ["a", "b"]}], "two groups"),
           ([{"emails": ["a", "b"]}, {"emails": ["c", "d", "z"]}], "not an eligible"),
           ([{"emails": ["a"]}, {"emails": ["b"]}], "group of 1")]
    for plan, msg in bad:
        with pytest.raises(ValueError, match=msg):
            ap.validate_plan(plan, people)
    with pytest.raises(ValueError, match="meet again"):
        ap.validate_plan([{"emails": ["a", "b"]}, {"emails": ["c", "d"]}], people, {frozenset(("a", "b"))})


TEMPLATE = "﻿Subject: Meet your accountability partner \n\n\nHi there,\n\n\nThis email introduces the two of you. " \
           "You're both on it.\n\n\n* Ask before advising.\n* Keep it short.\n" + "x" * 200 + "\n"


def test_parse_template_subject_bullets_and_blank_lines():
    subject, body = ap.parse_template(TEMPLATE)
    assert subject == "Meet your accountability partner"
    assert "• Ask before advising." in body and "\n\n\n" not in body and body.startswith("Hi there,")


def test_parse_template_rejects_missing_subject():
    with pytest.raises(ValueError):
        ap.parse_template("Hi there,\n" + "x" * 300)


def test_body_for_three_people():
    _, body = ap.parse_template(TEMPLATE)
    assert ap.body_for(body, 2) == body
    three = ap.body_for(body, 3)
    assert "introduces the three of you" in three and "You're all on it" in three


def test_message_goes_only_to_the_pair_from_the_alias():
    msg = ap.build_message("S", "B", ["a@x.com", "b@y.com"], "Dec 1")
    assert msg["To"] == "a@x.com, b@y.com" and msg["From"] == "Igor Scaldini <igor@clearerthinking.org>"
    assert msg["Cc"] is None and msg["Bcc"] is None


def test_send_waits_for_9am_et_on_dec_1():
    assert not ap.send_due("Dec 1", datetime(2026, 12, 1, 13, 59, tzinfo=timezone.utc))
    assert ap.send_due("Dec 1", datetime(2026, 12, 1, 14, 0, tzinfo=timezone.utc))


def test_plan_rows_safety_checks():
    head = ap.SEND_HEADERS
    ok = [head, [1, "Women", "a@x.com", "b@x.com", "", "", "", "", "", "", "", "TRUE", ""]]
    assert [r["emails"] for _, r in ap.plan_rows(ok)] == [["a@x.com", "b@x.com"]]
    with pytest.raises(ValueError, match="two rows"):
        ap.plan_rows(ok + [[2, "Women", "a@x.com", "c@x.com", "", "", "", "", "", "", "", "TRUE", ""]])
    with pytest.raises(ValueError, match="two addresses"):
        ap.plan_rows([head, [1, "Women", "a@x.com", "", "", "", "", "", "", "", "", "TRUE", ""]])
    with pytest.raises(ValueError, match="columns"):
        ap.plan_rows([["Pair", "Person A"], [1, "a@x.com"]])
