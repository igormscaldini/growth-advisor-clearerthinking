"""Reply handler: the Bash bridge between the headless Claude session and the data tools."""
import json

import advisor_reply as ar


def test_tools_prompt_lists_every_tool_and_the_command_form(monkeypatch):
    monkeypatch.setattr(ar, "_python_cmd", lambda: "python")
    text = ar.tools_prompt()
    assert "python advisor_reply.py --tool <tool_name> '<JSON object of arguments>'" in text
    for t in ar.TOOLS:
        assert f"- {t['name']}:" in text
        assert t["description"][:40] in text
    assert "amounts_cents: array" in text
    assert "num_weeks: integer" in text


def test_python_cmd_relative_in_venv_absolute_elsewhere_plain_if_spaces(monkeypatch, tmp_path):
    root = tmp_path / "Growth Advisor - Clearer Thinking"
    monkeypatch.setattr(ar.wa, "ROOT", root)
    monkeypatch.setattr(ar.sys, "executable", str(root / ".venv" / "bin" / "python"))
    assert ar._python_cmd() == ".venv/bin/python"        # the venv symlink is NOT resolved
    assert ar.tool_command_prefix() == ".venv/bin/python advisor_reply.py --tool"
    monkeypatch.setattr(ar.sys, "executable", "/opt/hostedtoolcache/Python/3.11.9/x64/bin/python")
    assert ar._python_cmd() == "/opt/hostedtoolcache/Python/3.11.9/x64/bin/python"
    monkeypatch.setattr(ar.sys, "executable", "/Applications/My Python/bin/python")
    assert ar._python_cmd() == "python"


def test_run_tool_dispatch_and_errors(monkeypatch):
    monkeypatch.setitem(ar.TOOL_FNS, "double", lambda n=0, **_: {"result": 2 * int(n)})
    assert ar.run_tool("double", '{"n": 21}') == {"result": 42}
    assert ar.run_tool("double", "") == {"result": 0}
    assert "unknown tool" in ar.run_tool("nope", "{}")["error"]
    assert "JSON object" in ar.run_tool("double", "[1, 2]")["error"]
    assert "JSONDecodeError" in ar.run_tool("double", "{bad")["error"]

    def boom(**_):
        raise RuntimeError("stripe down")

    monkeypatch.setitem(ar.TOOL_FNS, "boom", boom)
    assert ar.run_tool("boom", "{}") == {"error": "RuntimeError: stripe down"}


def test_answer_question_runs_headless_claude_in_repo_with_tool_allowlist(monkeypatch):
    seen = {}

    def fake_run(system, user, **kw):
        seen.update(kw, system=system, user=user)
        return "  answer  "

    monkeypatch.setattr(ar.mem, "run_claude_code", fake_run)
    monkeypatch.setattr(ar.wa, "load_memory", lambda: "Igor hates em dashes.")
    monkeypatch.setattr(ar.mem, "load_knowledge", lambda **kw: "KB text")
    monkeypatch.setattr(ar.mem, "load_recent_conversations", lambda **kw: "DIGEST text")
    monkeypatch.setattr(ar, "_python_cmd", lambda: "python")
    assert ar.answer_question("How was revenue?") == "  answer  "
    assert seen["user"] == "How was revenue?"
    assert seen["cwd"] == ar.wa.ROOT
    assert seen["tools"] == ["Bash"]
    assert seen["allowed_tools"] == ["Bash(python advisor_reply.py --tool:*)"]
    for needle in ("Igor hates em dashes.", "KB text", "DIGEST text", "- remember_this:", "- stripe_revenue:"):
        assert needle in seen["system"]


def test_main_tool_mode_prints_json_and_honours_dry_run_env(monkeypatch, capsys):
    monkeypatch.setitem(ar.TOOL_FNS, "double", lambda n=0, **_: {"result": 2 * int(n), "dry": ar.DRY_RUN})
    monkeypatch.setattr(ar.sys, "argv", ["advisor_reply.py", "--tool", "double", '{"n": 4}'])
    monkeypatch.setenv(ar.DRY_RUN_ENV, "1")
    assert ar.main() == 0
    assert json.loads(capsys.readouterr().out) == {"result": 8, "dry": True}
    monkeypatch.delenv(ar.DRY_RUN_ENV)
    assert ar.main() == 0
    assert json.loads(capsys.readouterr().out) == {"result": 8, "dry": False}


def test_remember_this_respects_dry_run(monkeypatch):
    calls = []
    monkeypatch.setattr(ar.mem, "append_durable_memory", lambda entry, category="context": calls.append((entry, category)) or "line")
    monkeypatch.setattr(ar, "DRY_RUN", True)
    assert ar._tool_remember_this("x", "context")["dry_run"] is True
    assert calls == []
    monkeypatch.setattr(ar, "DRY_RUN", False)
    assert ar._tool_remember_this("   ", "context")["saved"] is False
    assert ar._tool_remember_this("Igor prefers Mondays", "preference") == {"saved": True}
    assert calls == [("Igor prefers Mondays", "preference")]


def test_durable_bytes_detects_child_process_writes(monkeypatch, tmp_path):
    f = tmp_path / "durable.md.enc"
    monkeypatch.setattr(ar.mem, "DURABLE_FILE", f)
    assert ar._durable_bytes() == b""
    f.write_bytes(b"abc")
    assert ar._durable_bytes() == b"abc"
