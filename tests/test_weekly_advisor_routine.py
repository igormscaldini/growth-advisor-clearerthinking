"""Routine mode of weekly_advisor.py: the brief written for the Claude Code routine, the
letter/memory files it hands back, and the send step that turns them into the email."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import weekly_advisor as wa


def _inputs(**over):
    base = {
        "history": [{"start": "2026-08-28", "end": "2026-09-03", "revenue_total": 1234.5, "errors": {}},
                    {"start": "2026-08-21", "end": "2026-08-27", "revenue_total": 1000.0, "errors": {}}],
        "goals": {"mrr_usd": {"value": 2500, "target": 5000}},
        "flags": ["GA4 users looks broken"],
        "goals_text": "# Goals\nHit $120k.",
        "memory_text": "Igor hates em dashes.",
        "knowledge_text": "Audience: US self-insight seekers.",
        "conversations_text": "Session digest: fixed the beehiiv retry.",
        "inbox_text": "Josh asked about the dashboard repo.",
        "memory_ok": True,
        "errors": {},
    }
    base.update(over)
    return base


def test_letter_prompt_includes_every_input_section():
    i = _inputs()
    text = wa.letter_prompt(i["history"], i["goals"], i["flags"], i["goals_text"], i["memory_text"],
                            i["knowledge_text"], i["conversations_text"], i["inbox_text"])
    for needle in ("GOALS.md:", "Hit $120k.", "GA4 users looks broken", "Igor hates em dashes.",
                   "US self-insight seekers", "fixed the beehiiv retry", "Josh asked about",
                   '"revenue_total": 1234.5', '"mrr_usd"'):
        assert needle in text


def test_build_brief_carries_prompts_and_send_inputs():
    brief = wa.build_brief(_inputs(errors={"beehiiv": "429"}))
    assert brief["version"] == wa.BRIEF_VERSION
    assert brief["week"] == {"start": "2026-08-28", "end": "2026-09-03"}
    assert brief["letter_system"] == wa.LETTER_SYSTEM
    assert "fixed the beehiiv retry" in brief["letter_user"]
    assert brief["consolidate_system"] == wa.CONSOLIDATE_SYSTEM
    assert "Igor hates em dashes." in brief["consolidate_user"]
    assert brief["errors"] == {"beehiiv": "429"}
    assert brief["history"][0]["start"] == "2026-08-28"
    assert brief["memory_ok"] is True


def test_build_brief_skips_consolidation_without_memory_or_digests():
    assert wa.build_brief(_inputs(memory_ok=False))["consolidate_user"] is None
    assert wa.build_brief(_inputs(conversations_text="   "))["consolidate_user"] is None
    assert wa.build_brief(_inputs(history=[]))["week"] is None


def test_brief_round_trip_and_validation(tmp_path):
    path = tmp_path / "out" / "brief.json"
    brief = wa.build_brief(_inputs())
    wa.save_brief(brief, path)  # creates the parent directory
    loaded = wa.load_brief(path)
    assert loaded["letter_user"] == brief["letter_user"]
    assert loaded["history"] == brief["history"]

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"version": 999, "history": []}))
    with pytest.raises(ValueError):
        wa.load_brief(bad)
    bad.write_text(json.dumps([1, 2, 3]))
    with pytest.raises(ValueError):
        wa.load_brief(bad)


def test_apply_memory_updates_filters_and_coerces(monkeypatch):
    calls = []

    def fake_append(entry, category="context", when=None):
        calls.append((entry, category))
        return f"- {entry}" if entry else ""

    monkeypatch.setattr(wa.mem, "append_durable_memory", fake_append)
    added = wa.apply_memory_updates([
        {"entry": "Prefers Haiku for digests.", "category": "preference"},
        {"entry": "Weird category.", "category": "banana"},   # coerced to context
        {"entry": ""},                                          # empty: skipped by the store
        "not an object",                                        # skipped
        {"category": "correction"},                             # no entry -> "" -> skipped
    ])
    assert added == ["- Prefers Haiku for digests.", "- Weird category."]
    assert calls[0] == ("Prefers Haiku for digests.", "preference")
    assert calls[1] == ("Weird category.", "context")


def test_load_memory_updates(tmp_path):
    assert wa.load_memory_updates(None) == []
    assert wa.load_memory_updates(tmp_path / "missing.json") == []
    empty = tmp_path / "empty.json"
    empty.write_text("  \n")
    assert wa.load_memory_updates(empty) == []
    prose = tmp_path / "prose.json"
    prose.write_text('Here you go:\n[{"entry": "x", "category": "context"}]\nDone.')
    assert wa.load_memory_updates(prose) == [{"entry": "x", "category": "context"}]


def test_parse_args_routine_flags():
    with pytest.raises(SystemExit):
        wa.parse_args(["--send-letter", "letter.md"])           # needs --brief
    with pytest.raises(SystemExit):
        wa.parse_args(["--memory-updates", "m.json"])           # needs --send-letter
    args = wa.parse_args(["--send-letter", "l.md", "--brief", "b.json", "--memory-updates", "m.json"])
    assert (args.send_letter, args.brief, args.memory_updates) == ("l.md", "b.json", "m.json")
    assert wa.parse_args(["--brief", "b.json"]).send_letter is None


def test_send_letter_mode_dry_run_uses_letter_and_brief_errors(tmp_path, capsys):
    brief_path = tmp_path / "brief.json"
    wa.save_brief(wa.build_brief(_inputs(errors={"beehiiv": "429 Too Many Requests"})), brief_path)
    letter = tmp_path / "letter.md"
    letter.write_text("Revenue held at $1,234 this week.\n\n1. Ship the checkout fix.\n")
    args = SimpleNamespace(brief=str(brief_path), send_letter=str(letter), memory_updates=None,
                           dry_run=True, skip_consolidate=False)
    assert wa.send_letter_mode(args) == 0
    out = capsys.readouterr().out
    assert "Subject: Weekly Growth Report, week of 2026-08-28 ⚠️ PARTIAL" in out
    assert "Revenue held at $1,234 this week." in out
    assert "beehiiv: 429 Too Many Requests" in out


def test_send_letter_mode_empty_letter_is_flagged(tmp_path, capsys):
    brief_path = tmp_path / "brief.json"
    wa.save_brief(wa.build_brief(_inputs()), brief_path)
    letter = tmp_path / "letter.md"
    letter.write_text("\n")
    args = SimpleNamespace(brief=str(brief_path), send_letter=str(letter), memory_updates=None,
                           dry_run=True, skip_consolidate=True)
    assert wa.send_letter_mode(args) == 0
    out = capsys.readouterr().out
    assert "PARTIAL" in out
    assert "the routine wrote no letter" in out
    assert "the write-up failed to generate" in out
