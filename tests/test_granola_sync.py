"""Granola meeting notes: the Mac-side sync (granola_sync.py), the encrypted store and loader
(advisor_memory), the letter's staleness check (weekly_advisor) and the bots' tool (advisor_reply)."""
import json
import subprocess
from datetime import date, datetime, timedelta, timezone

import pytest

import advisor_memory as am
import granola_sync as gs


@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setenv(am.KEY_ENV, am.generate_key())
    monkeypatch.setattr(am, "MEETINGS_DIR", tmp_path / "meetings")
    monkeypatch.setattr(am, "MEETINGS_SYNC_FILE", tmp_path / "meetings" / "last_sync.txt")
    return tmp_path / "meetings"


def meeting(mid="m-1", when="2026-11-23T11:00:00-03:00", title="Travis <> Igor <> Josh", summary="Agreed X.",
            notes="", people=("Travis <travis@example.org>",)):
    return {"id": mid, "title": title, "meeting_at": when, "participants": list(people),
            "summary": summary, "private_notes": notes}


# --- pure helpers ----------------------------------------------------------------------------
def test_file_key_is_stable_hex_and_distinct():
    k = gs.file_key("6f1c2d3e-aaaa-bbbb-cccc-000000000000")
    assert k == gs.file_key("6f1c2d3e-aaaa-bbbb-cccc-000000000000")
    assert len(k) == 8 and all(c in "0123456789abcdef" for c in k)
    assert gs.file_key("not_abc") != gs.file_key("not_abd")
    assert am.DIGEST_NAME_RE.match(f"2026-11-23_{gs.file_key('not_abc')}.md.enc")


@pytest.mark.parametrize("raw,expected", [
    ("2026-11-23T11:00:00-03:00", date(2026, 11, 23)),   # the meeting's own (local) date
    ("2026-11-23T23:30:00Z", date(2026, 11, 23)),
    ("2026-11-23", date(2026, 11, 23)),
    ("", None), ("tomorrow", None),
])
def test_meeting_day(raw, expected):
    assert gs.meeting_day(raw) == expected


def test_render_with_and_without_private_notes():
    text = gs.render(meeting(notes="Ask Josh about the repo."))
    assert text.startswith("### Meeting: Travis <> Igor <> Josh (2026-11-23 11:00)")
    assert "Participants: Travis <travis@example.org>" in text
    assert "Granola summary:\nAgreed X." in text
    assert "Igor's own notes:\nAsk Josh about the repo." in text
    bare = gs.render({"id": "x", "meeting_at": "2026-11-23"})
    assert "(untitled)" in bare and "(not listed)" in bare and "(no AI summary)" in bare
    assert "own notes" not in bare


def test_tools_called_reads_stream_json():
    lines = [
        json.dumps({"type": "system", "tools": ["x"]}),
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "hi"},
            {"type": "tool_use", "name": "mcp__claude_ai_Granola__search_meetings", "input": {}}]}}),
        "not json",
        json.dumps({"type": "result", "result": "[]"}),
    ]
    assert gs.tools_called(lines) == {"mcp__claude_ai_Granola__search_meetings"}
    assert gs.tools_called([]) == set()


# --- fetch: the guard against a model that answers without calling Granola -------------------
def _fake_run(stdout):
    def run(*a, **k):
        return subprocess.CompletedProcess(a, 0, stdout=stdout, stderr="")
    return run


def _result_line(text):
    return json.dumps({"type": "result", "is_error": False, "result": text, "num_turns": 3})


def test_fetch_rejects_reply_without_tool_call(monkeypatch):
    monkeypatch.setattr(gs.mem, "find_claude_binary", lambda: "claude")
    monkeypatch.setattr(gs.subprocess, "run", _fake_run(_result_line("[]")))
    with pytest.raises(am.AdvisorConfigError):
        gs.fetch_meetings(date(2026, 11, 21), date(2026, 11, 23))


def test_fetch_parses_meetings_after_tool_call(monkeypatch):
    call = json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": gs.GRANOLA_TOOLS[0], "input": {}}]}})
    payload = json.dumps([meeting()])
    monkeypatch.setattr(gs.mem, "find_claude_binary", lambda: "claude")
    monkeypatch.setattr(gs.subprocess, "run", _fake_run(f"{call}\n{_result_line('Here: ' + payload)}\n"))
    assert gs.fetch_meetings(date(2026, 11, 21), date(2026, 11, 23)) == [meeting()]
    monkeypatch.setattr(gs.subprocess, "run", _fake_run(f"{call}\n{_result_line('sorry, no')}\n"))
    with pytest.raises(RuntimeError):
        gs.fetch_meetings(date(2026, 11, 21), date(2026, 11, 23))


# --- store -----------------------------------------------------------------------------------
def test_store_writes_encrypted_and_is_idempotent(store):
    changed, skipped = gs.store([meeting(), meeting(mid="m-2", when="2026-11-20T09:00:00-03:00"),
                                 {"id": "", "meeting_at": "2026-11-20"}, {"id": "m-3"}, "junk"])
    assert skipped == 3 and len(changed) == 2
    names = sorted(p.name for p in store.iterdir())
    assert names == sorted([f"2026-11-23_{gs.file_key('m-1')}.md.enc", f"2026-11-20_{gs.file_key('m-2')}.md.enc"])
    raw = (store / names[1]).read_bytes()
    assert b"Agreed X." not in raw                      # encrypted at rest (the repo is public)
    assert gs.store([meeting()])[0] == []                # unchanged note: nothing to commit


def test_store_rewrites_edited_note_and_moves_rescheduled_one(store):
    gs.store([meeting()])
    changed, _ = gs.store([meeting(summary="Agreed Y.")])
    assert len(changed) == 1 and "Agreed Y." in am.read_encrypted(changed[0])
    changed, _ = gs.store([meeting(when="2026-11-24T10:00:00-03:00")])
    assert [p.name[:10] for p in store.glob("*.md.enc")] == ["2026-11-24"]
    assert len(changed) == 2                             # old file removed + new one written


def test_sync_file_due(store):
    now = datetime(2026, 11, 23, 12, tzinfo=timezone.utc)
    assert gs.sync_file_due(now, changed=False)          # never synced
    store.mkdir(parents=True)
    am.MEETINGS_SYNC_FILE.write_text((now - timedelta(hours=2)).isoformat())
    assert not gs.sync_file_due(now, changed=False)
    assert gs.sync_file_due(now, changed=True)
    am.MEETINGS_SYNC_FILE.write_text((now - timedelta(hours=21)).isoformat())
    assert gs.sync_file_due(now, changed=False)


# --- loader ----------------------------------------------------------------------------------
def test_load_meeting_notes_window_query_and_cap(store):
    gs.store([meeting(mid="a", when="2026-11-10T10:00:00Z", title="Old", summary="Overcome pricing."),
              meeting(mid="b", when="2026-11-18T10:00:00Z", title="Mid", summary="Overcome coaches, $15."),
              meeting(mid="c", when="2026-11-23T10:00:00Z", title="New", summary="PMax budget.")])
    ref = date(2026, 11, 23)
    week = am.load_meeting_notes(days=7, ref=ref)        # Nov 17-23: Mid and New, oldest first
    assert "Old" not in week and week.index("Mid") < week.index("New")
    assert "Mid" in am.load_meeting_notes(days=7, ref=ref, query="overcome $15")
    assert "New" not in am.load_meeting_notes(days=7, ref=ref, query="OVERCOME")
    assert am.load_meeting_notes(days=7, ref=ref, query="travis nobody") == ""
    capped = am.load_meeting_notes(days=30, ref=ref, max_chars=len(gs.render(
        meeting(mid="c", when="2026-11-23T10:00:00Z", title="New", summary="PMax budget."))) + 1)
    assert "1 older" not in capped and "2 older meeting note(s) omitted" in capped and "New" in capped


def test_load_meeting_notes_empty_store(store):
    assert am.load_meeting_notes() == ""
    assert am.last_meeting_sync() is None


# --- consumers -------------------------------------------------------------------------------
def test_meetings_sync_problem():
    import weekly_advisor as wa

    now = datetime(2026, 11, 27, 11, tzinfo=timezone.utc)
    assert "never" in wa.meetings_sync_problem(None, now)
    assert wa.meetings_sync_problem(now - timedelta(days=2), now) is None
    assert "2026-11-23" in wa.meetings_sync_problem(now - timedelta(days=4), now)


def test_reply_tool_meeting_notes(store):
    import advisor_reply as ar

    assert "meeting_notes" in ar.READ_ONLY_TOOLS          # so the email task bot gets it too
    gs.store([meeting(when=datetime.now().astimezone().isoformat())])
    out = ar.TOOL_FNS["meeting_notes"](days=3)
    assert "Agreed X." in out["notes"] and out["last_synced"] is None
    out = ar.TOOL_FNS["meeting_notes"](days=3, query="zebra")
    assert out["notes"] == "(no meeting notes in the last 3 days matching 'zebra')"
