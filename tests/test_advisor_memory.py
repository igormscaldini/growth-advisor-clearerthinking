import json
from datetime import date, timedelta

import pytest

import advisor_memory as am


@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setenv(am.KEY_ENV, am.generate_key())
    monkeypatch.setattr(am, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(am, "CONVERSATIONS_DIR", tmp_path / "conversations")
    monkeypatch.setattr(am, "DURABLE_FILE", tmp_path / "durable.md.enc")
    return tmp_path


def test_round_trip(store):
    blob = am.encrypt_text("hello, wörld")
    assert blob != "hello, wörld".encode()
    assert am.decrypt_text(blob) == "hello, wörld"


def test_missing_key_is_explicit(monkeypatch):
    monkeypatch.delenv(am.KEY_ENV, raising=False)
    with pytest.raises(am.MemoryKeyMissing):
        am.encrypt_text("x")


def test_wrong_key_fails(store, monkeypatch):
    blob = am.encrypt_text("secret")
    monkeypatch.setenv(am.KEY_ENV, am.generate_key())
    with pytest.raises(Exception):
        am.decrypt_text(blob)


def test_digest_path_and_replace(store):
    sid = "58351d99-670f-4e0b-92a0-c80e1a81eb0d"
    old = am.digest_path(sid, date(2026, 8, 26))
    new = am.digest_path(sid, date(2026, 8, 30))
    assert old.name == "2026-08-26_58351d99.md.enc"
    am.write_encrypted(old, "v1")
    am.write_encrypted(new, "v2")
    removed = am.remove_other_digests(sid, keep=new)
    assert removed == [old] and not old.exists() and new.exists()


def test_recent_conversations_window_order_and_cap(store):
    ref = date(2026, 8, 30)
    am.write_encrypted(am.digest_path("aaaaaaaa", ref - timedelta(days=8)), "too old")
    am.write_encrypted(am.digest_path("bbbbbbbb", ref - timedelta(days=6)), "six days ago")
    am.write_encrypted(am.digest_path("cccccccc", ref), "today")
    am.write_encrypted(am.digest_path("dddddddd", ref + timedelta(days=1)), "future")
    text = am.load_recent_conversations(days=7, ref=ref)
    assert "too old" not in text and "future" not in text
    assert text.index("six days ago") < text.index("today")
    assert "Session on 2026-08-24 (id bbbbbbbb)" in text
    # Cap drops the OLDEST first and says so.
    capped = am.load_recent_conversations(days=7, ref=ref, max_chars=80)
    assert "today" in capped and "six days ago" not in capped and "omitted" in capped
    assert am.load_recent_conversations(days=1, ref=ref - timedelta(days=30)) == ""


def test_durable_memory_append_and_load(store):
    assert am.load_durable_memory() == ""
    assert am.append_durable_memory("   ") == ""
    line = am.append_durable_memory("Igor cares more about MRR than gross revenue.", "preference", when=date(2026, 8, 30))
    assert line == "\n## 2026-08-30 (preference)\nIgor cares more about MRR than gross revenue.\n"
    am.append_durable_memory("Second fact.", when=date(2026, 8, 31))
    text = am.load_durable_memory()
    assert text.startswith("# Advisor durable memory")
    assert "MRR" in text and "Second fact." in text
    assert am.load_durable_memory(max_chars=15) == text[-15:] and text.endswith("Second fact.\n")


def test_list_digests_ignores_foreign_files(store):
    am.write_encrypted(am.digest_path("abcdef12", date(2026, 8, 1)), "x")
    (am.CONVERSATIONS_DIR / "notes.txt").write_text("nope")
    rows = am.list_conversation_digests()
    assert [r["session"] for r in rows] == ["abcdef12"]


# --- Claude backends -------------------------------------------------------------------
def test_backend_default_and_override(monkeypatch):
    monkeypatch.delenv("ADVISOR_BACKEND", raising=False)
    assert am.advisor_backend() == "claude-code"
    monkeypatch.setenv("ADVISOR_BACKEND", "API")
    assert am.advisor_backend() == "api"
    monkeypatch.setenv("ADVISOR_BACKEND", "openai")
    with pytest.raises(am.AdvisorConfigError):
        am.advisor_backend()


def test_claude_text_dispatches_on_backend(monkeypatch):
    calls = []
    monkeypatch.delenv("ADVISOR_BACKEND", raising=False)
    monkeypatch.setattr(am, "run_claude_code", lambda system, user, **kw: calls.append(("cli", system, user)) or "letter")
    monkeypatch.setattr(am, "_api_text", lambda system, user, max_tokens: calls.append(("api", max_tokens)) or "api letter")
    assert am.claude_text("sys", "usr") == "letter"
    assert calls == [("cli", "sys", "usr")]
    monkeypatch.setenv("ADVISOR_BACKEND", "api")
    assert am.claude_text("sys", "usr", max_tokens=123) == "api letter"
    assert calls[-1] == ("api", 123)


def test_fix_hint_names_the_backend(monkeypatch):
    monkeypatch.delenv("ADVISOR_BACKEND", raising=False)
    monkeypatch.setenv("ADVISOR_MODEL", "claude-opus-5")
    assert "CLAUDE_CODE_OAUTH_TOKEN" in am.claude_fix_hint() and "claude-opus-5" in am.claude_fix_hint()
    monkeypatch.setenv("ADVISOR_BACKEND", "api")
    assert "ANTHROPIC_API_KEY" in am.claude_fix_hint()


def _fake_binary(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)
    return path


def test_find_claude_binary_env_first_then_newest_vscode_bundle(monkeypatch, tmp_path):
    home = tmp_path / "home"
    monkeypatch.setattr(am.Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr(am.shutil, "which", lambda name: None)
    for var in ("CLAUDE_BIN", "CLAUDE_CODE_EXECPATH"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(am.ClaudeCodeMissing):
        am.find_claude_binary()

    ext = home / ".vscode" / "extensions"
    old = _fake_binary(ext / "anthropic.claude-code-2.1.9-darwin-arm64" / "resources" / "native-binary" / "claude")
    new = _fake_binary(ext / "anthropic.claude-code-2.1.100-darwin-arm64" / "resources" / "native-binary" / "claude")
    assert am.find_claude_binary() == str(new)   # numeric, not string, version order (2.1.100 > 2.1.9)
    assert old != new

    explicit = _fake_binary(tmp_path / "bin" / "claude")
    monkeypatch.setenv("CLAUDE_BIN", str(explicit))
    assert am.find_claude_binary() == str(explicit)
    monkeypatch.setenv("CLAUDE_BIN", str(tmp_path / "missing"))   # a bad override falls through
    assert am.find_claude_binary() == str(new)


def test_child_env_drops_session_markers_and_api_keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "tok-x")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "abc")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/cfg")
    monkeypatch.setenv("PATH", "/usr/bin")
    env = am._child_env()
    for gone in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDECODE", "CLAUDE_CODE_SESSION_ID"):
        assert gone not in env
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "oauth"
    assert env["CLAUDE_CONFIG_DIR"] == "/cfg"
    assert env["PATH"] == "/usr/bin"


def test_claude_code_command_shape(monkeypatch):
    monkeypatch.setattr(am, "find_claude_binary", lambda: "/bin/claude")
    monkeypatch.setenv("ADVISOR_MODEL", "claude-opus-5")
    monkeypatch.delenv("ADVISOR_FALLBACK_MODEL", raising=False)
    cmd = am.claude_code_command("SYS")
    assert cmd[0] == "/bin/claude" and "-p" in cmd and "--no-session-persistence" in cmd
    assert cmd[cmd.index("--output-format") + 1] == "json"
    assert cmd[cmd.index("--tools") + 1] == ""
    assert cmd[cmd.index("--setting-sources") + 1] == "" and "--strict-mcp-config" in cmd
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5"
    assert cmd[cmd.index("--system-prompt") + 1] == "SYS"
    assert cmd[cmd.index("--fallback-model") + 1] == "claude-sonnet-5"
    assert "--allowedTools" not in cmd

    monkeypatch.setenv("ADVISOR_FALLBACK_MODEL", "")
    cmd = am.claude_code_command("SYS", tools=["Bash"], allowed_tools=["Bash(python x --tool:*)"])
    assert "--fallback-model" not in cmd
    assert cmd[cmd.index("--tools") + 1] == "Bash"
    assert cmd[cmd.index("--allowedTools") + 1] == "Bash(python x --tool:*)"


def test_parse_claude_code_result():
    ok = json.dumps({"is_error": False, "result": "  Dear Igor  ", "num_turns": 1,
                     "modelUsage": {"claude-opus-5": {}}})
    assert am.parse_claude_code_result(ok) == "Dear Igor"
    with pytest.raises(am.AdvisorConfigError):
        am.parse_claude_code_result(json.dumps({"is_error": True, "result": "Not logged in · Please run /login"}))
    with pytest.raises(RuntimeError, match="overloaded"):
        am.parse_claude_code_result(json.dumps({"is_error": True, "result": "API Error: overloaded"}))
    with pytest.raises(RuntimeError, match="without a JSON result"):
        am.parse_claude_code_result("", "boom: segfault", 1)
    with pytest.raises(RuntimeError, match="refusal"):
        am.parse_claude_code_result(json.dumps({"is_error": False, "result": "", "stop_reason": "refusal"}))


def test_with_retries(monkeypatch):
    monkeypatch.setattr(am.time, "sleep", lambda s: None)
    n = {"calls": 0}

    def flaky():
        n["calls"] += 1
        if n["calls"] < 3:
            raise TimeoutError("slow")
        return "ok"

    assert am.with_retries("t", flaky) == "ok"
    assert n["calls"] == 3

    def not_logged_in():
        raise am.AdvisorConfigError("no login")

    with pytest.raises(am.AdvisorConfigError):   # configuration errors are not retried
        am.with_retries("t", not_logged_in)

    n["calls"] = 0

    def always():
        n["calls"] += 1
        raise ValueError("x")

    with pytest.raises(ValueError):
        am.with_retries("t", always, attempts=2)
    assert n["calls"] == 2
