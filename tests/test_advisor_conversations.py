import json
from datetime import datetime, timedelta, timezone

import advisor_conversations as ac


def _rec(rtype, content, ts="2026-08-26T12:00:00.000Z", **extra):
    d = {"type": rtype, "timestamp": ts, "message": {"role": rtype, "content": content}}
    d.update(extra)
    return d


def _write(tmp_path, records):
    p = tmp_path / "58351d99-670f-4e0b-92a0-c80e1a81eb0d.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records) + "\nnot json\n")
    return p


def test_extract_turns_keeps_only_what_matters(tmp_path):
    p = _write(tmp_path, [
        {"type": "ai-title", "aiTitle": "Export workshop data", "sessionId": "x"},
        _rec("user", [{"type": "text", "text": "Export the workshop signups"}]),
        _rec("assistant", [
            {"type": "thinking", "thinking": "private reasoning"},
            {"type": "text", "text": "Sure, pulling it now."},
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "curl export"}},
        ], ts="2026-08-26T12:01:00.000Z"),
        _rec("user", [{"type": "tool_result", "tool_use_id": "t1", "content": "x" * 1000}]),
        _rec("user", "<task-notification>done</task-notification>"),
        _rec("user", [{"type": "text", "text": "ignored meta"}], isMeta=True),
        _rec("assistant", [{"type": "text", "text": "subagent chatter"}], isSidechain=True),
        _rec("user", [{"type": "text", "text": "<system-reminder>hidden</system-reminder>"},
                      {"type": "text", "text": "Thanks, list them."}], ts="2026-08-27T09:00:00.000Z"),
        _rec("assistant", [{"type": "text", "text": "518 emails."}], ts="2026-08-27T09:00:05.000Z"),
    ])
    turns = ac.extract_turns(p)
    assert [t["role"] for t in turns] == ["user", "assistant", "user", "user", "assistant"]
    assert turns[0] == {"role": "user", "ts": "2026-08-26T12:00:00.000Z", "text": "Export the workshop signups", "prompt": True}
    assert "private reasoning" not in turns[1]["text"]
    assert "Sure, pulling it now." in turns[1]["text"] and "[tool Bash: " in turns[1]["text"]
    assert turns[2]["text"].startswith("[tool result: xxx") and len(turns[2]["text"]) <= ac.TOOL_RESULT_CHARS + 20
    assert turns[2]["prompt"] is False
    assert turns[3]["text"] == "Thanks, list them." and turns[3]["prompt"] is True
    assert ac.count_prompts(turns) == 2
    assert ac.session_title(p) == "Export workshop data"
    rendered = ac.render_turns(turns)
    assert rendered[0].startswith("### IGOR 2026-08-26 12:00\n")
    assert rendered[2].startswith("### TOOL OUTPUT")
    assert rendered[1].startswith("### ASSISTANT")


def test_chunk_strings():
    assert ac.chunk_strings(["a" * 100] * 5, 250) == ["a" * 100 + "\n\n" + "a" * 100] * 2 + ["a" * 100]
    assert ac.chunk_strings(["b" * 500], 100) == ["b" * 500]  # oversized item stays whole
    assert ac.chunk_strings([], 100) == []


def test_should_digest_rules():
    now = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
    recent = {"prompts": 3, "digested_at": (now - timedelta(minutes=10)).isoformat()}
    stale = {"prompts": 3, "digested_at": (now - timedelta(minutes=31)).isoformat()}
    assert ac.should_digest(None, 3, "stop", now) is True          # never digested
    assert ac.should_digest(None, 0, "stop", now) is False         # nothing typed
    assert ac.should_digest(recent, 3, "session_end", now) is False  # nothing new
    assert ac.should_digest(recent, 4, "stop", now) is False       # within debounce
    assert ac.should_digest(recent, 4, "session_end", now) is True  # session ended
    assert ac.should_digest(recent, 8, "stop", now) is True        # 5 new prompts
    assert ac.should_digest(stale, 4, "stop", now) is True         # debounce elapsed
    assert ac.should_digest(recent, 3, "force", now) is True       # force ignores state
    assert ac.should_digest(None, 0, "force", now) is False


def test_project_dir_name_matches_claude_code_convention():
    from pathlib import Path
    root = Path("/Users/igorscaldini/Documents/Claude/Growth Advisor - Clearer Thinking")
    assert ac.project_dir_name(root) == "-Users-igorscaldini-Documents-Claude-Growth-Advisor---Clearer-Thinking"
    assert ac.TRANSCRIPTS_DIR.parent.name == "projects"


# --- sweep lock and dry run ------------------------------------------------------------
def test_sweep_lock_is_exclusive_and_recovers_from_dead_owner(monkeypatch, tmp_path):
    lock = tmp_path / "digest.lock"
    monkeypatch.setattr(ac, "LOCK_FILE", lock)
    assert ac.acquire_sweep_lock() is True
    assert lock.read_text() == str(ac.os.getpid())
    assert ac.acquire_sweep_lock() is False          # held by a live process (us)
    ac.release_sweep_lock()
    assert not lock.exists()

    lock.write_text("999999999")                     # a dead owner: taken over
    monkeypatch.setattr(ac, "_pid_alive", lambda pid: False)
    assert ac.acquire_sweep_lock() is True
    ac.release_sweep_lock()

    lock.write_text("garbage")                       # unreadable owner: taken over
    assert ac.acquire_sweep_lock() is True
    ac.release_sweep_lock()

    lock.write_text(str(ac.os.getpid()))             # someone else's lock is never released by us
    monkeypatch.setattr(ac, "_pid_alive", lambda pid: True)
    lock.write_text("4242")
    ac.release_sweep_lock()
    assert lock.exists()


def test_sweep_skips_when_another_sweep_holds_the_lock(monkeypatch, tmp_path):
    lock = tmp_path / "digest.lock"
    lock.write_text("4242")
    monkeypatch.setattr(ac, "LOCK_FILE", lock)
    monkeypatch.setattr(ac, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(ac, "TRANSCRIPTS_DIR", tmp_path)
    _write(tmp_path, [_rec("user", [{"type": "text", "text": "hello " * 100}])])
    calls = []
    monkeypatch.setattr(ac, "process_session", lambda *a, **k: calls.append(a))
    ac.sweep("sweep", dry_run=True, push=False, only_idle=False)
    assert calls == []
    lock.unlink()
    ac.sweep("sweep", dry_run=True, push=False, only_idle=False)
    assert len(calls) == 1
    assert not lock.exists()                          # released afterwards


def test_dry_run_lists_without_calling_claude(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ac, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(ac, "_claude", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Claude was called")))
    path = _write(tmp_path, [
        {"type": "ai-title", "aiTitle": "Big session", "sessionId": "x"},
        _rec("user", [{"type": "text", "text": "Please export the workshop signups " * 20}]),
        _rec("assistant", [{"type": "text", "text": "Done, here is the export. " * 20}], ts="2026-08-26T12:01:00.000Z"),
    ])
    assert ac.process_session(path, "sweep", dry_run=True, push=False) is None
    assert "would digest 58351d99" in capsys.readouterr().err
    assert not (tmp_path / "state.json").exists()
