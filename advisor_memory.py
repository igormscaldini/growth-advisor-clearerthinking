"""Encrypted-at-rest memory for the Clearer Thinking growth advisor.

This repo is PUBLIC on GitHub (deliberately: the every-5-minutes reply poller would exhaust
the free Actions minutes of a private repo). Everything the advisor remembers is therefore
stored encrypted under advisor_memory/ and only decrypted at runtime with ADVISOR_MEMORY_KEY
(.env locally, a GitHub Actions secret on CI). Losing the key makes the memory unreadable,
so keep a copy of it somewhere safe.

Layout:
  advisor_memory/conversations/<YYYY-MM-DD>_<session8>.md.enc
      one digest per Claude Code session, written by advisor_conversations.py. The date is
      the session's last activity day; re-digesting a session replaces its file.
  advisor_memory/durable.md.enc
      standing facts, preferences and corrections. Appended by advisor_reply.py's
      remember_this tool and by weekly_advisor.py's end-of-week consolidation.

Shared by weekly_advisor.py, advisor_reply.py and advisor_conversations.py.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
MEMORY_DIR = ROOT / "advisor_memory"
CONVERSATIONS_DIR = MEMORY_DIR / "conversations"
DURABLE_FILE = MEMORY_DIR / "durable.md.enc"
KEY_ENV = "ADVISOR_MEMORY_KEY"
DIGEST_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_([0-9a-f]{8})\.md\.enc$")

# One source of truth for which Claude model the advisor uses (all three scripts import it).
DEFAULT_MODEL = "claude-opus-5"

DURABLE_HEADER = (
    "# Advisor durable memory\n\n"
    "Standing facts, preferences and corrections Igor has given, one entry per heading. "
    "Read as context by the weekly letter and the reply handler.\n"
)


def advisor_model() -> str:
    return os.getenv("ADVISOR_MODEL") or os.getenv("ANTHROPIC_MODEL") or DEFAULT_MODEL


class MemoryKeyMissing(RuntimeError):
    """ADVISOR_MEMORY_KEY is not configured, so nothing can be encrypted or decrypted."""


# --- encryption ---------------------------------------------------------------
def generate_key() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


def _fernet():
    from cryptography.fernet import Fernet

    key = os.getenv(KEY_ENV, "").strip()
    if not key:
        raise MemoryKeyMissing(
            f"{KEY_ENV} is not set. Locally it lives in .env; on CI it must be the GitHub secret "
            f"{KEY_ENV} (both should hold the same Fernet key)."
        )
    return Fernet(key.encode())


def encrypt_text(text: str) -> bytes:
    return _fernet().encrypt(text.encode("utf-8"))


def decrypt_text(blob: bytes) -> str:
    return _fernet().decrypt(blob).decode("utf-8")


def write_encrypted(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encrypt_text(text))


def read_encrypted(path: Path) -> str:
    return decrypt_text(path.read_bytes())


# --- conversation digests -----------------------------------------------------
def digest_path(session_id: str, day: date) -> Path:
    return CONVERSATIONS_DIR / f"{day.isoformat()}_{session_id[:8]}.md.enc"


def remove_other_digests(session_id: str, keep: Path) -> list[Path]:
    """A session re-digested on a later day gets a new filename; drop the stale copies."""
    removed = []
    if not CONVERSATIONS_DIR.exists():
        return removed
    for p in CONVERSATIONS_DIR.glob(f"*_{session_id[:8]}.md.enc"):
        if p != keep:
            p.unlink()
            removed.append(p)
    return removed


def list_conversation_digests(since: date | None = None, until: date | None = None) -> list[dict]:
    """Digest files (metadata only, not decrypted) sorted oldest first."""
    out = []
    if not CONVERSATIONS_DIR.exists():
        return out
    for p in CONVERSATIONS_DIR.iterdir():
        m = DIGEST_NAME_RE.match(p.name)
        if not m:
            continue
        d = date.fromisoformat(m.group(1))
        if since and d < since:
            continue
        if until and d > until:
            continue
        out.append({"path": p, "date": d, "session": m.group(2)})
    out.sort(key=lambda r: (r["date"], r["session"]))
    return out


def load_recent_conversations(days: int = 7, ref: date | None = None, max_chars: int = 80_000) -> str:
    """Decrypted digests of the sessions active in the `days` days ending at `ref` (default
    today), oldest first, as one text block. If they don't fit in max_chars the OLDEST are
    dropped and a note says so. Returns "" when there are none.
    """
    ref = ref or date.today()
    since = ref - timedelta(days=days - 1)
    rows = list_conversation_digests(since=since, until=ref)
    blocks = []
    for r in rows:
        text = read_encrypted(r["path"])
        blocks.append(f"### Session on {r['date'].isoformat()} (id {r['session']})\n{text.strip()}\n")
    dropped = 0
    while blocks and sum(len(b) for b in blocks) > max_chars:
        blocks.pop(0)
        dropped += 1
    if dropped:
        blocks.insert(0, f"({dropped} older session digest(s) omitted to fit the size limit.)\n")
    return "\n".join(blocks)


# --- durable memory -------------------------------------------------------------
def load_durable_memory(max_chars: int = 6000) -> str:
    """Most-recent durable entries, capped so the prompt can't grow without bound."""
    if not DURABLE_FILE.exists():
        return ""
    text = read_encrypted(DURABLE_FILE)
    return text[-max_chars:] if len(text) > max_chars else text


def append_durable_memory(entry: str, category: str = "context", when: date | None = None) -> str:
    """Append one entry and return the exact text added ('' if the entry was empty)."""
    entry = (entry or "").strip()
    if not entry:
        return ""
    when = when or datetime.now(timezone.utc).date()
    line = f"\n## {when.isoformat()} ({category})\n{entry}\n"
    existing = read_encrypted(DURABLE_FILE) if DURABLE_FILE.exists() else DURABLE_HEADER
    write_encrypted(DURABLE_FILE, existing + line)
    return line


# --- knowledge base ---------------------------------------------------------------
KNOWLEDGE_DIR = MEMORY_DIR / "knowledge"


def write_knowledge(name: str, text: str) -> Path:
    """Store a reference document (audience research, brand guidelines...) the advisor
    should always have in front of it. Encrypted like everything else here."""
    path = KNOWLEDGE_DIR / f"{name}.md.enc"
    write_encrypted(path, text)
    return path


def load_knowledge(max_chars: int = 60_000) -> str:
    """Every knowledge document, decrypted, with a heading per file. Documents are cut
    (with a note) rather than dropped if the total exceeds max_chars."""
    if not KNOWLEDGE_DIR.exists():
        return ""
    files = sorted(KNOWLEDGE_DIR.glob("*.md.enc"))
    if not files:
        return ""
    budget = max_chars // len(files)
    blocks = []
    for p in files:
        text = read_encrypted(p).strip()
        if len(text) > budget:
            text = text[:budget] + "\n(... document cut to fit the size limit)"
        blocks.append(f"### {p.name[:-len('.md.enc')]}\n{text}\n")
    return "\n".join(blocks)


# --- Claude ----------------------------------------------------------------------
def claude_text(system: str, user: str, max_tokens: int = 4000) -> str:
    """One streamed Claude call returning the text of the reply. Raises on refusal."""
    import anthropic

    client = anthropic.Anthropic(max_retries=4)
    with client.messages.stream(
        model=advisor_model(),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request (stop_reason=refusal)")
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()


# --- git ----------------------------------------------------------------------------
def _wait_for_index_lock(cwd: Path, seconds: int = 60) -> None:
    lock = cwd / ".git" / "index.lock"
    for _ in range(seconds):
        if not lock.exists():
            return
        time.sleep(1)


def git_commit_and_push(paths: list[Path], message: str, cwd: Path = ROOT) -> str | None:
    """Commit exactly `paths` and push to origin/main. Returns an error string, never raises.

    Handles the realities of this repo: a concurrent git process (waits for index.lock), the
    snapshot cron pushing to main every 30 minutes (rebases first, retries the push once), and
    CI needing a bot identity.
    """
    rel = [str(Path(p).resolve().relative_to(cwd.resolve())) for p in paths]

    def run(*args, check=True):
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                              check=check, timeout=300)

    try:
        _wait_for_index_lock(cwd)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            run("config", "user.name", "ct-growth-advisor[bot]")
            run("config", "user.email", "actions@users.noreply.github.com")
        run("add", "--", *rel)
        if run("diff", "--cached", "--quiet", "--", *rel, check=False).returncode == 0:
            return None  # nothing changed
        run("commit", "-m", message, "--", *rel)
        last_err = ""
        for _ in range(2):
            pull = run("pull", "--rebase", "--autostash", "origin", "main", check=False)
            push = run("push", "origin", "main", check=False)
            if push.returncode == 0:
                return None
            last_err = (pull.stderr + push.stderr)[-500:]
            time.sleep(3)
        return f"push failed: {last_err}"
    except subprocess.CalledProcessError as e:
        return f"git {' '.join(e.cmd[1:3])} failed: {(e.stderr or '')[-500:]}"
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {e}"


if __name__ == "__main__":
    # `python advisor_memory.py` prints a fresh key; `python advisor_memory.py show` dumps memory.
    if len(sys.argv) > 1 and sys.argv[1] == "show":
        print("=== durable ===\n" + load_durable_memory(max_chars=10**9))
        print("\n=== conversations (last 14 days) ===\n" + load_recent_conversations(days=14, max_chars=10**9))
    else:
        print(generate_key())
