"""Turn Claude Code session transcripts into the advisor's encrypted conversation memory.

Every Claude Code session in this project is logged as a JSONL transcript under
~/.claude/projects/<project>/<session-id>.jsonl. This script reads one, strips it down to
what matters (Igor's messages, the assistant's replies, abbreviated tool activity), asks
Claude to write the advisor's notes about it, and stores those notes encrypted in
advisor_memory/conversations/ (see advisor_memory.py), committing and pushing so the Friday
letter (which runs on GitHub Actions) can read them.

How it gets triggered:
  .claude/on-stop.sh calls `advisor_conversations.py --hook` on every Claude Code Stop and
  SessionEnd event, in the background. A session is digested when it has new prompts since
  its last digest and either the session ended, 30+ minutes passed since the last digest, or
  5+ new prompts arrived (so long sessions get refreshed without a Claude call every turn).
  Each run also sweeps the other transcripts and digests any that changed but went idle,
  which catches sessions whose SessionEnd never fired.

Run locally:   .venv/bin/python advisor_conversations.py --sweep            # catch up everything
               .venv/bin/python advisor_conversations.py --session <id> --force --print
               .venv/bin/python advisor_conversations.py --sweep --dry-run  # show what it would do
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

import advisor_memory as mem  # noqa: E402



def project_dir_name(root: Path) -> str:
    """Claude Code names the project transcript folder after the cwd with "/" and " " -> "-"."""
    return re.sub(r"[/ ]", "-", str(root))


TRANSCRIPTS_DIR = Path.home() / ".claude" / "projects" / project_dir_name(ROOT)
STATE_FILE = ROOT / ".claude" / "conversation_digest_state.json"
LOG_PREFIX = "[digest]"

MAX_CHUNK_CHARS = 120_000       # ~30k tokens per Claude call
TOOL_INPUT_CHARS = 200
TOOL_RESULT_CHARS = 300
MIN_TRANSCRIPT_CHARS = 200      # anything shorter isn't worth a note
DEBOUNCE_MINUTES = 30
PROMPTS_TO_FORCE = 5
IDLE_MINUTES = 30               # a transcript untouched this long counts as "session over"

# User-role content that Claude Code injects itself (not something Igor typed).
SKIP_USER_PREFIXES = (
    "<task-notification>", "<system-reminder>", "<command-name>", "<command-message>",
    "<local-command-stdout>", "<user-prompt-submit-hook>", "<ide_selection>",
)

DIGEST_SYSTEM = """You write the memory notes of a senior growth advisor for Clearer Thinking (clearerthinking.org). Igor Scaldini runs growth there and works with Claude Code in this project; you are given the transcript of one of his working sessions: his messages, the assistant's replies, and abbreviated tool activity. Write the notes the advisor will re-read weeks later to remember what happened.

Format: Markdown, at most 600 words, exactly these sections:
# <short descriptive title>
Dates: <first day> to <last day>
## Summary
Two or three sentences on what this session was about.
## What Igor worked on
What he asked for and why, in order.
## Deliverables and decisions
Files, emails, programs, analyses produced; choices made and the reasoning behind them.
## Facts and numbers learned
Concrete figures, dates, names and findings, each with its date. Only what actually appeared in the session; never invent or round creatively.
## Igor's preferences, priorities and goals
Anything he said about what he cares about, how he wants things done, and corrections he gave. Quote his own words when they capture a preference.
## Open threads
Unfinished work, pending decisions, things he said he would do or wants next.

Rules: plain and specific, no filler. Never use em dashes. Do not reproduce email addresses or other personal data of third parties (write "a list of 518 subscriber emails", not the emails). If a section has nothing, write "Nothing notable."."""

PARTIAL_NOTE = ("This transcript is long, so you are seeing part {i} of {n}. Write the notes for this "
                "part only, in the same format; they will be merged with the other parts afterwards.")
MERGE_SYSTEM = DIGEST_SYSTEM + ("\n\nYou are given partial notes for consecutive parts of ONE session. "
                                "Merge them into a single set of notes in the exact format above, "
                                "removing repetition and keeping every concrete fact.")


def log(msg: str) -> None:
    print(f"{LOG_PREFIX} {datetime.now().strftime('%H:%M:%S')} {msg}", file=sys.stderr, flush=True)


# --- transcript parsing ---------------------------------------------------------
def _trunc(s: str, n: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 3] + "..."


def _result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def extract_turns(path: Path) -> list[dict]:
    """The conversation as a list of {role, ts, text, prompt} dicts, in order.

    Keeps Igor's messages, assistant text, one-line summaries of tool calls, and truncated
    tool results. Drops thinking blocks, Claude-injected user content, meta records and
    subagent (sidechain) chatter. `prompt` marks user turns that contain something Igor typed.
    """
    turns: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            rtype = rec.get("type")
            if rtype not in ("user", "assistant") or rec.get("isMeta") or rec.get("isSidechain"):
                continue
            content = (rec.get("message") or {}).get("content")
            parts: list[str] = []
            is_prompt = False
            if isinstance(content, str):
                if rtype == "user" and content.lstrip().startswith(SKIP_USER_PREFIXES):
                    continue
                parts.append(content)
                is_prompt = rtype == "user"
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    bt = block.get("type")
                    if bt == "text":
                        text = block.get("text", "")
                        if rtype == "user" and text.lstrip().startswith(SKIP_USER_PREFIXES):
                            continue
                        parts.append(text)
                        is_prompt = is_prompt or rtype == "user"
                    elif bt == "tool_use":
                        inp = json.dumps(block.get("input", {}), default=str, ensure_ascii=False)
                        parts.append(f"[tool {block.get('name')}: {_trunc(inp, TOOL_INPUT_CHARS)}]")
                    elif bt == "tool_result":
                        parts.append(f"[tool result: {_trunc(_result_text(block.get('content')), TOOL_RESULT_CHARS)}]")
                    elif bt == "document":
                        parts.append("[attached document]")
                        is_prompt = is_prompt or rtype == "user"
                    elif bt == "image":
                        parts.append("[attached image]")
                    # thinking blocks are intentionally skipped
            text = "\n".join(p for p in parts if p and p.strip()).strip()
            if not text:
                continue
            turns.append({"role": rtype, "ts": rec.get("timestamp", ""), "text": text, "prompt": is_prompt})
    return turns


def count_prompts(turns: list[dict]) -> int:
    return sum(1 for t in turns if t["prompt"])


def session_title(path: Path) -> str:
    """Claude Code's own title for the session, if it wrote one."""
    title = ""
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if '"ai-title"' not in line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") == "ai-title" and rec.get("aiTitle"):
                title = rec["aiTitle"]  # keep the latest
    return title


def _day(ts: str) -> str:
    return ts[:10] if ts else ""


def render_turns(turns: list[dict]) -> list[str]:
    out = []
    for t in turns:
        who = "IGOR" if t["role"] == "user" and t["prompt"] else ("TOOL OUTPUT" if t["role"] == "user" else "ASSISTANT")
        stamp = t["ts"][:16].replace("T", " ") if t["ts"] else ""
        out.append(f"### {who} {stamp}\n{t['text']}")
    return out


def chunk_strings(items: list[str], max_chars: int) -> list[str]:
    """Group consecutive strings into chunks whose summed length stays within max_chars
    (a single oversized string becomes its own chunk)."""
    chunks: list[list[str]] = []
    cur: list[str] = []
    cur_len = 0
    for s in items:
        if cur and cur_len + len(s) > max_chars:
            chunks.append(cur)
            cur, cur_len = [], 0
        cur.append(s)
        cur_len += len(s)
    if cur:
        chunks.append(cur)
    return ["\n\n".join(c) for c in chunks]


# --- Claude -----------------------------------------------------------------------
def _claude(system: str, user: str, max_tokens: int = 4000) -> str:
    return mem.claude_text(system, user, max_tokens)


def digest_turns(turns: list[dict], title: str, session_id: str) -> str:
    rendered = render_turns(turns)
    days = sorted({_day(t["ts"]) for t in turns if t["ts"]})
    header = (f"Session id: {session_id[:8]}\nClaude Code title: {title or '(none)'}\n"
              f"Days active: {days[0] if days else '?'} to {days[-1] if days else '?'}\n\n")
    chunks = chunk_strings(rendered, MAX_CHUNK_CHARS)
    if len(chunks) == 1:
        return _claude(DIGEST_SYSTEM, header + "TRANSCRIPT:\n\n" + chunks[0])
    partials = []
    for i, chunk in enumerate(chunks, 1):
        log(f"  summarizing part {i}/{len(chunks)} ({len(chunk):,} chars)")
        note = PARTIAL_NOTE.format(i=i, n=len(chunks))
        partials.append(_claude(DIGEST_SYSTEM, header + note + "\n\nTRANSCRIPT PART:\n\n" + chunk))
    joined = "\n\n".join(f"--- PART {i} ---\n{p}" for i, p in enumerate(partials, 1))
    return _claude(MERGE_SYSTEM, header + "PARTIAL NOTES:\n\n" + joined)


# --- state + decisions ------------------------------------------------------------
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=1, sort_keys=True))


def should_digest(entry: dict | None, n_prompts: int, reason: str, now: datetime) -> bool:
    """reason: 'stop' (turn ended), 'session_end', 'sweep', or 'force'."""
    if reason == "force":
        return n_prompts > 0
    if n_prompts < 1:
        return False
    done = (entry or {}).get("prompts", 0)
    if n_prompts <= done:
        return False  # nothing new since the last digest
    if reason == "session_end":
        return True
    last = (entry or {}).get("digested_at")
    if not last:
        return True
    elapsed = now - datetime.fromisoformat(last)
    return elapsed >= timedelta(minutes=DEBOUNCE_MINUTES) or (n_prompts - done) >= PROMPTS_TO_FORCE


def transcript_for(session_id: str) -> Path:
    return TRANSCRIPTS_DIR / f"{session_id}.jsonl"


def process_session(path: Path, reason: str, dry_run: bool = False, push: bool = True,
                    print_digest: bool = False) -> Path | None:
    """Digest one transcript if the rules say so. Returns the digest path written (or None)."""
    session_id = path.stem
    state = load_state()
    entry = state.get(session_id)
    turns = extract_turns(path)
    n_prompts = count_prompts(turns)
    now = datetime.now(timezone.utc)
    if not should_digest(entry, n_prompts, reason, now):
        log(f"skip {session_id[:8]}: prompts={n_prompts} done={(entry or {}).get('prompts', 0)} reason={reason}")
        return None
    if sum(len(t["text"]) for t in turns) < MIN_TRANSCRIPT_CHARS:
        log(f"skip {session_id[:8]}: too short")
        return None

    title = session_title(path)
    log(f"digesting {session_id[:8]} '{title}' ({len(turns)} turns, {n_prompts} prompts, reason={reason})")
    text = digest_turns(turns, title, session_id)
    if print_digest or dry_run:
        print(text)
    if dry_run:
        return None

    last_ts = max((t["ts"] for t in turns if t["ts"]), default="")
    day = date.fromisoformat(last_ts[:10]) if last_ts else now.date()
    out = mem.digest_path(session_id, day)
    mem.write_encrypted(out, text)
    removed = mem.remove_other_digests(session_id, keep=out)
    state[session_id] = {"prompts": n_prompts, "digested_at": now.isoformat(), "file": out.name}
    save_state(state)
    log(f"wrote {out.relative_to(ROOT)}" + (f" (replaced {len(removed)})" if removed else ""))

    if push:
        err = mem.git_commit_and_push([out, *removed] if False else [out],
                                      f"advisor memory: digest session {session_id[:8]} ({day.isoformat()})")
        # Deleted stale copies need staging too; a second add covers them when present.
        if removed and not err:
            err = mem.git_commit_and_push(removed, f"advisor memory: drop stale digests for {session_id[:8]}")
        if err:
            log(f"WARNING commit/push failed (digest is saved locally, next run will retry): {err}")
        else:
            log("pushed")
    return out


def sweep(reason: str, dry_run: bool, push: bool, only_idle: bool) -> None:
    if not TRANSCRIPTS_DIR.exists():
        log(f"no transcripts dir at {TRANSCRIPTS_DIR}")
        return
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=IDLE_MINUTES)
    for path in sorted(TRANSCRIPTS_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime):
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if only_idle and mtime > cutoff:
            continue
        try:
            process_session(path, reason, dry_run=dry_run, push=push)
        except Exception as e:  # noqa: BLE001
            log(f"ERROR on {path.name}: {type(e).__name__}: {e}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hook", action="store_true", help="read Claude Code hook JSON from stdin")
    ap.add_argument("--session", help="session id to digest")
    ap.add_argument("--transcript", help="transcript .jsonl path to digest")
    ap.add_argument("--sweep", action="store_true", help="process every transcript in the project")
    ap.add_argument("--force", action="store_true", help="ignore debounce / nothing-new checks")
    ap.add_argument("--dry-run", action="store_true", help="print the digest, write nothing")
    ap.add_argument("--no-push", action="store_true", help="write locally but don't commit/push")
    ap.add_argument("--print", dest="print_digest", action="store_true", help="also print the digest")
    args = ap.parse_args()
    push = not args.no_push

    if args.hook:
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except json.JSONDecodeError:
            payload = {}
        sid = payload.get("session_id", "")
        tpath = Path(payload["transcript_path"]) if payload.get("transcript_path") else (transcript_for(sid) if sid else None)
        event = (payload.get("hook_event_name") or "").lower()
        reason = "session_end" if "end" in event else "stop"
        log(f"hook event={event or '?'} session={sid[:8] or '?'}")
        try:
            if tpath and tpath.exists():
                process_session(tpath, reason, push=push)
            # Catch sessions that ended without a SessionEnd (closed window, crash).
            sweep("sweep", dry_run=False, push=push, only_idle=True)
        except Exception as e:  # noqa: BLE001
            log(f"ERROR: {type(e).__name__}: {e}")
        return 0

    reason = "force" if args.force else "sweep"
    if args.sweep:
        sweep(reason, dry_run=args.dry_run, push=push, only_idle=not args.force)
        return 0
    if args.session or args.transcript:
        tpath = Path(args.transcript) if args.transcript else transcript_for(args.session)
        if not tpath.exists():
            log(f"no transcript at {tpath}")
            return 1
        process_session(tpath, reason, dry_run=args.dry_run, push=push, print_digest=args.print_digest)
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
