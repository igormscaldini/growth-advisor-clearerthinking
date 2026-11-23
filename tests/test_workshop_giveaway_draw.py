from workshop_giveaway_draw import eligible_entries, unlabelled_entries


def row(email, rnd="1", started="2026-11-24 17:20:00", nickname="n"):
    return {"email": email, "giveawayRound": rnd, "Time Started (UTC)": started, "nickname": nickname}


def emails(entries):
    return [e["email"] for e in entries]


def test_keeps_only_the_requested_round():
    rows = [row("a@x.com", "1"), row("b@x.com", "2"), row("c@x.com", "none")]
    assert emails(eligible_entries(rows, 1, "2026-11-24", [])) == ["a@x.com"]
    assert emails(eligible_entries(rows, 2, "2026-11-24", [])) == ["b@x.com"]


def test_drops_entries_before_since_and_empty_emails():
    rows = [row("old@x.com", started="2026-08-27 15:30:00"), row(""), row("new@x.com")]
    assert emails(eligible_entries(rows, 1, "2026-11-24", [])) == ["new@x.com"]


def test_dedupes_by_email_case_insensitively():
    rows = [row("A@x.com", nickname="first"), row("a@X.com", nickname="second")]
    out = eligible_entries(rows, 1, "2026-11-24", [])
    assert len(out) == 1 and out[0]["nickname"] == "first"


def test_excludes_previous_winners_and_test_addresses():
    rows = [row("won@x.com"), row("igormscaldini+qa@gmail.com"), row("me+healthcheck@x.com"), row("ok@x.com")]
    assert emails(eligible_entries(rows, 1, "2026-11-24", ["WON@x.com"])) == ["ok@x.com"]


def test_unlabelled_entries_are_flagged():
    rows = [row("a@x.com", "none"), row("b@x.com", "none", started="2026-08-27 15:30:00"), row("c@x.com", "1")]
    assert [r["email"] for r in unlabelled_entries(rows, "2026-11-24")] == ["a@x.com"]
