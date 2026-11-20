"""Tests for the ct-podcast-quote skill (pure functions only, no network or rendering)."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude/skills/ct-podcast-quote/scripts"))
import ct_podcast_quote as q  # noqa: E402

APPROVED_SPEC = ROOT / "reports/podcast_quote_ep328_2026-11-20_src/spec.json"
# sha256 of the CSS approved by Igor on 2026-11-20 (episode 328 post).
APPROVED_LOOK = "2f27735a9898a3a28bd169816ab2534106b3dae62d92b575eeaeceaaf5284bdc"

PAGE = """Episode 328: Is it intent or impact that matters in our relationships? (with Shawni Turner)
Some description.
SPENCER: Hello there.
SHAWNI: I'm "quoted" here, and it's fine.
Not a turn line.
"""


def test_look_is_unchanged():
    assert hashlib.sha256(q.CSS.encode()).hexdigest() == APPROVED_LOOK, \
        "Quote-post look changed. Revert, or get Igor's OK and re-pin."


def test_parse_episode_single_guest():
    ep = q.parse_episode(PAGE, "u")
    assert ep == {"number": 328, "title": "Is it intent or impact that matters in our relationships?", "url": "u",
                  "speakers": {"SPENCER": "Spencer Greenberg", "SHAWNI": "Shawni Turner"}}


def test_parse_episode_two_guests():
    ep = q.parse_episode("Episode 12: Title here (with Ann Lee and Bo Kim)\n", "u")
    assert ep["speakers"] == {"SPENCER": "Spencer Greenberg", "ANN": "Ann Lee", "BO": "Bo Kim"}


def test_transcript_keeps_only_turns():
    out = q.transcript_lines(PAGE, {"SPENCER": "", "SHAWNI": ""})
    assert out == 'SPENCER: Hello there.\nSHAWNI: I\'m "quoted" here, and it\'s fine.\n'


def test_latest_episode_is_first_link():
    home = '<a href="/about/">x</a><a href="/episode/329/new/">n</a><a href="/episode/328/old/">o</a>'
    assert q.latest_episode_url(home) == q.PODCAST + "/episode/329/new/"


def test_missing_quotes_exact_and_capitalised_cut():
    t = "SPENCER: so you need a model, and it works."
    spec = {"candidates": [{"id": "A", "text": "you need a model"},
                           {"id": "B", "text": "You need a model"},      # capitalised mid-sentence cut: allowed
                           {"id": "C", "text": "you need a good model"}]}
    assert q.missing_quotes(spec, t) == ["C"]


def test_tally_hand_worked():
    votes = [{"vote": "A", "ranking": ["A", "B", "C"]},
             {"vote": "B", "ranking": ["B", "A", "D"]},
             {"vote": "A", "ranking": ["A", "C", "B"]}]
    # A: 3+2+3 = 8, B: 2+3+1 = 6, C: 1+2 = 3, D: 1
    assert q.tally(votes) == [("A", 2, 8), ("B", 1, 6), ("C", 0, 3), ("D", 0, 1)]


def test_approved_spec_tally_and_verbatim():
    spec = json.loads(APPROVED_SPEC.read_text(encoding="utf-8"))
    assert q.tally(spec["votes"])[:2] == [("A", 6, 26), ("B", 4, 23)]
    transcript = APPROVED_SPEC.with_name("transcript.txt")
    if transcript.exists():                     # gitignored, so absent in CI
        assert q.missing_quotes(spec, transcript.read_text(encoding="utf-8")) == []


def test_ballots_are_reproducible_permutations():
    spec = {"candidates": [{"id": c, "speaker": "X Y", "text": c} for c in "ABCDEFGHIJ"]}
    b1, b2 = q.ballots(spec), q.ballots(spec)
    assert b1 == b2 and len(b1) == 10
    assert all(sorted(c["id"] for c in o) == list("ABCDEFGHIJ") for o in b1)
    assert len({"".join(c["id"] for c in o) for o in b1}) > 1


def test_curly_changes_marks_only():
    assert q.curly('I call "this" it\'s') == "I call “this” it’s"


def test_quote_html_highlight_and_escape():
    assert q.quote_html("a < b and c", "b and") == 'a &lt; <span class="hl">b and</span> c'
    with pytest.raises(SystemExit):
        q.quote_html("x x", "x")


def test_quote_style_by_length():
    assert "96px" in q.quote_style("w " * 25)
    assert "84px" in q.quote_style("w " * 30)
    assert "74px" in q.quote_style("w " * 50)


def test_body_has_attribution_in_house_format():
    spec = json.loads(APPROVED_SPEC.read_text(encoding="utf-8"))
    html = q.body(spec)
    assert "<b>Spencer Greenberg</b> on the Clearer Thinking Podcast," in html
    assert "“Episode 328: Is it intent or impact that matters in our relationships?”" in html


def test_chosen_must_be_set():
    with pytest.raises(SystemExit):
        q.chosen({"candidates": [{"id": "A"}], "chosen": ""})
