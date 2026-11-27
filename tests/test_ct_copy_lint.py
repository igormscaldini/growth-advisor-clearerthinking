"""Tests for the ct-writer skill's copy checker (.claude/skills/ct-writer/scripts/copy_lint.py)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude/skills/ct-writer/scripts"))
import copy_lint as cl  # noqa: E402

# The calibration sample Igor approved on 2026-11-27 ("one lyrical beat"). It is the voice
# the skill aims for, so the checker must find nothing wrong with it.
APPROVED_SAMPLE = """Every plan is a small work of fiction, and we are generous authors. When psychology students predicted how long their theses would take, they said 34 days on average. They took 56.

The error has a name, the planning fallacy, and a cause: we picture the project going well and forget how the last ones went.

So borrow from your own history. Before your next project, ask how long the last three like it took. Use that number, not your gut."""


def ids(text, protected=()):
    return [f.id for f in cl.lint(text, protected=list(protected))]


def test_approved_sample_is_clean():
    assert cl.lint(APPROVED_SAMPLE, protected=[]) == []


def test_plain_factual_copy_is_clean():
    text = "We asked 152 astrologers to match 12 people to their birth charts. The best score was 5 of 12."
    assert ids(text) == []


# ---- house rules -----------------------------------------------------------------------

@pytest.mark.parametrize("text", ["It works — mostly.", "It works – mostly.", "It works -- mostly."])
def test_em_dash_and_its_stand_ins_break_a_rule(text):
    found = cl.lint(text, protected=[])
    assert [(f.id, f.level) for f in found] == [("em-dash", "rule")]


def test_en_dash_in_a_number_range_is_fine():
    assert ids("Aim for 1,500–2,500 words.") == []


def test_brand_name():
    assert ids("ClearerThinking makes tools.") == ["brand-name"]
    assert ids("Find us at ClearerThinking.org today.") == []
    assert ids("Clearer Thinking makes tools.") == []
    assert ids("See https://www.clearerthinking.org/blog and #clearerthinking") == []


def test_modules_and_self_praise_and_proven():
    assert ids("Try our modules.") == ["modules"]
    assert ids("Our groundbreaking research.") == ["self-praise"]
    assert ids("A scientifically proven method.") == ["proven"]
    assert all(f.level == "rule" for f in cl.lint("Our groundbreaking modules are clinically proven.", protected=[]))


def test_protected_names_are_not_flagged():
    text = "Try Life-Changing Questions tonight."
    assert ids(text) == ["self-praise"]
    assert ids(text, protected=["Life-Changing Questions"]) == []
    # masking is case-insensitive and keeps positions, so later findings keep their line
    two_lines = "Try life-changing questions.\nIt works — mostly."
    found = cl.lint(two_lines, protected=["Life-Changing Questions"])
    assert [(f.id, f.line) for f in found] == [("em-dash", 2)]


def test_tool_names_come_from_ct_tools_md(tmp_path):
    md = tmp_path / "CT_TOOLS.md"
    md.write_text("- **[The Ultimate Personality Test](https://x.org/a)** · _2023_\n- **[Unique Traits Test](https://x.org/b)**\n")
    assert cl.tool_names(md) == ["The Ultimate Personality Test", "Unique Traits Test", "Ultimate Personality Test"]
    assert cl.tool_names(tmp_path / "missing.md") == []


# ---- tells: one hit and one near miss per family --------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("Studies show that sleep helps.", "unnamed-evidence"),
    ("Let me delve into it.", "ai-vocabulary"),
    ("Unlock your results.", "marketing-cliche"),
    ("When it comes to sleep, more helps.", "filler"),
    ("Here's the thing: sleep helps.", "signpost"),
    ("The result? Better sleep.", "signpost"),
    ("Ever wondered why you put things off?", "stock-opener"),
    ("Ready to find out your type?", "stock-cta"),
    ("This is not just a quiz.", "not-x-but-y"),
    ("It's not about willpower. It's about design.", "not-x-but-y"),
    ("Whether you're a student or a manager, it helps.", "audience-cover"),
    ("It is truly useful.", "intensifier"),
    ("You should try it.", "prescriptive"),
    ("Don't miss out on this.", "fake-urgency"),
    ("Remember that you're not alone.", "validation"),
    ("Trust the universe on this one.", "woo"),
    ("As Aristotle once said, we are what we do.", "borrowed-authority"),
    ("People in America sleep less.", "america"),
    ("It works!", "exclamation"),
    ("It is clear, practical, and useful.", "triad"),
    ("No fluff. No jargon. Just science.", "fragment-run"),
])
def test_each_tell_is_found(text, expected):
    found = cl.lint(text, protected=[])
    assert expected in [f.id for f in found]
    assert all(f.level == "tell" for f in found)


@pytest.mark.parametrize("text", [
    "Use that number, not your gut.",                      # plain negation is not the contrast tell
    "Navigators get one coaching session a month.",        # Navigator is a CT+ tier, not "navigate"
    "You can try it for ten minutes.",                     # "you can" is the house form
    "Americans sleep less than they did.",                 # only the bare noun is flagged
    "It measures the Big Five traits and your Enneagram type.",
    "One short sentence. Then a longer one that explains what the short one meant.",
    "People in the U.S. sleep less.",
])
def test_near_misses_stay_clean(text):
    assert ids(text) == []


def test_fragment_run_needs_three_short_sentences_in_one_paragraph():
    assert "fragment-run" not in ids("No fluff. No jargon.")
    assert "fragment-run" not in ids("No fluff.\n\nNo jargon.\n\nJust science.")
    assert ids("Short one. Then two. And three. A fourth that is long enough to end the run of fragments.") == ["fragment-run"]


def test_stock_opener_only_at_the_start_of_a_line():
    assert "stock-opener" in ids("Intro line.\n\nImagine a week with no email.")
    assert "stock-opener" not in ids("It is hard to imagine a week with no email.")


# ---- order, lines, exit codes -----------------------------------------------------------

def test_findings_are_in_reading_order_with_line_numbers():
    text = "Line one is fine.\nYou should delve.\n\nOur modules."
    found = cl.lint(text, protected=[])
    assert [(f.line, f.id) for f in found] == [(2, "prescriptive"), (2, "ai-vocabulary"), (4, "modules")]
    assert found[1].text == "delve"


def test_exit_code_is_1_only_when_a_rule_is_broken(tmp_path, capsys):
    tell = tmp_path / "tell.md"
    tell.write_text("It is truly useful.")
    rule = tmp_path / "rule.md"
    rule.write_text("It works — mostly.")
    clean = tmp_path / "clean.md"
    clean.write_text(APPROVED_SAMPLE)
    assert cl.main([str(clean)]) == 0
    assert "Clean" in capsys.readouterr().out
    assert cl.main([str(tell)]) == 0
    assert cl.main([str(rule)]) == 1
    assert cl.main([str(clean), str(rule)]) == 1
    out = capsys.readouterr().out
    assert "em-dash" in out and "1 rule(s) broken, 0 tell(s)" in out


def test_json_output(tmp_path, capsys):
    import json
    f = tmp_path / "d.md"
    f.write_text("Our modules.")
    assert cl.main(["--json", str(f)]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data[str(f)][0]["id"] == "modules" and data[str(f)][0]["level"] == "rule"


def test_triad_ignores_lists_of_names():
    assert ids("Captions for LinkedIn, Instagram and X.") == []
    assert ids("See Buehler, Griffin and Ross for the study.") == []
    assert ids("Clear, practical and useful.") == ["triad"]
