"""The Bash bridge between a headless Claude Code session and a script's Python tools.

A bot (advisor_reply.py, task_bot.py) gives the session one tool, Bash, allow-listed to a single
command prefix: `<python> <script> --tool <name> '<json arguments>'`. That command runs one Python
function and prints its JSON result, so the model can use the function without the Anthropic API
tool loop. This module holds the parts every such bot shares: how the command is spelled, how the
catalogue is described in the prompt, and how one call is dispatched.
"""
from __future__ import annotations

import json
import os
import sys


def python_cmd(root) -> str:
    """The interpreter the model invokes --tool mode with, from the repo root. The venv's
    `.venv/bin/python` is made relative (no spaces even though the repo path has them, so the
    Bash allow-list prefix matches what the model types); an interpreter elsewhere (GitHub
    Actions) is used by its absolute path; a path with spaces falls back to `python`."""
    exe = os.path.abspath(sys.executable)
    root = os.path.abspath(str(root))
    if exe.startswith(root + os.sep):
        return os.path.relpath(exe, root)
    return exe if " " not in exe else "python"


def command_prefix(python: str, script: str) -> str:
    return f"{python} {script} --tool"


def allowed_tools(prefix: str) -> list[str]:
    """The --allowedTools value that lets the session run this one command and nothing else."""
    return [f"Bash({prefix}:*)"]


def tools_prompt(tools: list[dict], prefix: str, intro: str = "Data tools.") -> str:
    """The tool catalogue for the system prompt: each tool is one shell command that prints JSON."""
    lines = [
        f"{intro} Each one is a shell command, run from the repository root with the Bash tool, "
        "that prints a JSON result. Call it exactly as:",
        f"  {prefix} <tool_name> '<JSON object of arguments>'",
        "(single-quote the JSON; pass '{}' when there are no arguments). Never run any other command. "
        "Tools:",
    ]
    for t in tools:
        props = (t.get("input_schema") or {}).get("properties") or {}
        args = "; ".join(f"{k}: {v.get('type', 'string')}, {v.get('description', '')}".rstrip(", ")
                         for k, v in props.items()) or "none"
        lines.append(f"- {t['name']}: {t['description']} Arguments: {args}")
    return "\n".join(lines)


def run_tool(tool_fns: dict, name: str, args_json: str) -> dict:
    """--tool mode: run one tool and return its result. Problems come back as {"error": ...}
    so the model can read them instead of a stack trace."""
    fn = tool_fns.get(name)
    if fn is None:
        return {"error": f"unknown tool {name!r}; available: {', '.join(tool_fns)}"}
    try:
        args = json.loads(args_json or "{}")
    except json.JSONDecodeError as e:
        return {"error": f"JSONDecodeError in arguments: {e}"}
    if not isinstance(args, dict):
        return {"error": "arguments must be a JSON object"}
    try:
        return fn(**args)
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}
