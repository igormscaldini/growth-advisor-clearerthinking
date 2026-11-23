from workshop_giveaway_draw import eligible_entries


def row(email, started="2026-11-24 17:20:00", nickname="n"):
    return {"email": email, "Time Started (UTC)": started, "nickname": nickname}


def emails(entries):
    return [e["email"] for e in entries]


def test_drops_entries_before_since_and_empty_emails():
    rows = [row("old@x.com", started="2026-08-27 15:30:00"), row(""), row("new@x.com")]
    assert emails(eligible_entries(rows, "2026-11-24", [])) == ["new@x.com"]


def test_dedupes_by_email_case_insensitively():
    rows = [row("A@x.com", nickname="first"), row("a@X.com", nickname="second")]
    out = eligible_entries(rows, "2026-11-24", [])
    assert len(out) == 1 and out[0]["nickname"] == "first"


def test_excludes_previous_winners_and_test_addresses():
    rows = [row("won@x.com"), row("igormscaldini+qa@gmail.com"), row("me+healthcheck@x.com"), row("ok@x.com")]
    assert emails(eligible_entries(rows, "2026-11-24", ["WON@x.com"])) == ["ok@x.com"]


def test_one_entry_stays_in_later_draws_until_it_wins():
    rows = [row("a@x.com"), row("b@x.com"), row("c@x.com")]
    assert emails(eligible_entries(rows, "2026-11-24", ["a@x.com"])) == ["b@x.com", "c@x.com"]
    assert emails(eligible_entries(rows, "2026-11-24", ["a@x.com", "c@x.com"])) == ["b@x.com"]
