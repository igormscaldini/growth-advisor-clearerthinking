"""Daily Positly Reddit finder (Mon-Fri): two curated posts + reply drafts, emailed.

Every weekday this looks for up to TWO Reddit posts and emails them with draft replies:

  A. RECRUITMENT — someone actively looking for study participants / survey respondents
     (a potential Positly lead). Subs like r/SampleSize, r/SurveyExchange.
  B. DISCUSSION — a *researcher-POV* discussion about using online platforms/panels to
     recruit participants (Prolific/MTurk/CloudResearch/online panels, "where do you recruit",
     etc.). Explicitly NOT the earner/"which app pays best" point of view.

For each post found, Claude drafts a short, natural, genuinely-helpful reply (mentioning
Positly only where it honestly fits). If NEITHER category yields a qualifying post, nothing
is sent that day. These are DRAFTS to review — nothing is auto-posted.

Transport: Gmail API, with SMTP fallback (SMTP is the reliable path locally) — same helper
as the CT advisors. Reddit: redditwarp, read-only, NO OAuth app required — this works from a
residential IP only, so this job runs LOCALLY (Reddit blocks datacenter IPs, and self-service
API apps closed under Reddit's Responsible Builder Policy).

Run:           .venv/bin/python positly_reddit_recruiter.py --dry-run   # print, don't send
               .venv/bin/python positly_reddit_recruiter.py             # send for real
Scheduled:     ~/Library/LaunchAgents/com.positly.reddit-finder.plist (Mon-Fri 09:00 local)
"""
from __future__ import annotations

import argparse
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent


def _materialize_ci_secrets() -> None:
    """On CI the OAuth JSON blobs arrive as env vars; write them where the clients expect.

    email_transport's Gmail-API path reads ga4_client.TOKEN_FILE, so the shared Google token
    must exist on disk for the reliable (cloud-IP-friendly) send path to work.
    """
    blobs = {
        "OAUTH_CLIENT_JSON": ROOT / "secrets" / "oauth-client.json",
        "GOOGLE_TOKEN_JSON": ROOT / "secrets" / "ga4-token.json",
    }
    for env_var, target in blobs.items():
        blob = os.environ.get(env_var, "").strip()
        if not blob:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(blob)


load_dotenv()
_materialize_ci_secrets()

import email_transport  # noqa: E402

ADVISOR_MODEL = os.getenv("ADVISOR_MODEL") or os.getenv("ANTHROPIC_MODEL") or "claude-opus-4-8"
EMAIL_FROM_LABEL = "Positly Reddit Finder"
EMAIL_TO = os.getenv("POSITLY_REDDIT_EMAIL_TO") or os.getenv("ADVISOR_EMAIL_TO") or email_transport.EMAIL_FROM

# --- category config ------------------------------------------------------------------------
# A. Recruitment: people seeking participants. These subs are recruitment-by-default.
RECRUIT_SUBS = os.getenv("POSITLY_RECRUIT_SUBS", "SampleSize+SurveyExchange")
RECRUIT_LOOKBACK_DAYS = int(os.getenv("POSITLY_RECRUIT_LOOKBACK_DAYS", "2"))

# B. Discussion: researchers discussing how/where to recruit online.
DISCUSSION_SUBS = os.getenv(
    "POSITLY_DISCUSSION_SUBS",
    "AskAcademia+AcademicPsychology+UXResearch+AskSocialScience+labrats+research+PhD",
)
DISCUSSION_LOOKBACK_DAYS = int(os.getenv("POSITLY_DISCUSSION_LOOKBACK_DAYS", "7"))
DISCUSSION_CANDIDATES = int(os.getenv("POSITLY_DISCUSSION_CANDIDATES", "3"))

SCAN_LIMIT = int(os.getenv("POSITLY_REDDIT_SCAN_LIMIT", "150"))
SKIP_PREFIXES = ("[results]", "[meta]", "[mod", "[announcement]")

# Discussion must be about recruiting participants online...
DISCUSS_TERMS = (
    "recruit", "recruiting", "recruitment", "participant", "respondent", "prolific",
    "mturk", "mechanical turk", "cloudresearch", "cloud research", "online panel",
    "participant pool", "sona", "where to find participant", "platform to recruit",
    "survey panel", "sample provider",
)
# ...and NOT from the "which app pays me best" earner point of view.
EARNER_TERMS = (
    "make money", "earn money", "earning", "payout", "cash out", "how much do you make",
    "how much can i make", "is it worth it", "side hustle", "get paid", "best paying",
    "beer money", "extra cash", "made this week", "my earnings",
)

FIX_INSTRUCTIONS = {
    "reddit": "redditwarp read failed. This must run from a residential IP (Reddit blocks "
              "datacenter IPs); confirm the Mac has network access and that redditwarp+httpx are "
              "installed in the venv. No OAuth app / credentials are needed for read-only pulls.",
    "narrative": "Claude API call failed — check ANTHROPIC_API_KEY and account credits, and that "
                 f"the model id '{ADVISOR_MODEL}' is available (override with ADVISOR_MODEL).",
    "transport": email_transport.TRANSPORT_FIX,
}


# --- Reddit helpers (redditwarp: no OAuth app, read-only, residential IP only) --------------
def _reddit():
    from redditwarp.SYNC import Client

    return Client()  # userless read-only; no credentials required


def _subs(spec: str) -> list[str]:
    return [s.strip() for s in spec.replace(",", "+").split("+") if s.strip()]


def _as_dict(post) -> dict:
    return {
        "subreddit": post.subreddit.name,
        "title": (post.title or "").strip(),
        "selftext": (getattr(post, "body", "") or "").strip(),  # TextPost.body; LinkPost has none
        "url": post.permalink,                                  # already a full URL
        "created": post.created_at,                             # tz-aware UTC datetime
        "score": int(getattr(post, "score", 0) or 0),
    }


def _pull_new(reddit, sub: str):
    """Yield recent submissions from one subreddit, tolerating a single bad/failed sub."""
    try:
        yield from reddit.p.subreddit.pull.new(sub, amount=SCAN_LIMIT)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] pull failed for r/{sub}: {e}", file=sys.stderr)


def find_recruitment_post(reddit) -> dict | None:
    """Newest post (within lookback) where someone is recruiting participants. None if absent."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=RECRUIT_LOOKBACK_DAYS)
    best: dict | None = None
    for sub in _subs(RECRUIT_SUBS):
        for post in _pull_new(reddit, sub):
            d = _as_dict(post)
            if d["created"] < cutoff or d["title"].lower().startswith(SKIP_PREFIXES):
                continue
            if best is None or d["created"] > best["created"]:
                best = d  # recruitment-by-default subs; newest across them wins
    return best


def find_discussion_candidates(reddit) -> list[dict]:
    """Researcher-POV discussions about online recruitment, best-engaged first (heuristic filter)."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=DISCUSSION_LOOKBACK_DAYS)
    cands: list[dict] = []
    for sub in _subs(DISCUSSION_SUBS):
        for post in _pull_new(reddit, sub):
            d = _as_dict(post)
            if d["created"] < cutoff or d["title"].lower().startswith(SKIP_PREFIXES):
                continue
            blob = f"{d['title'].lower()} {d['selftext'].lower()}"
            if not any(t in blob for t in DISCUSS_TERMS):
                continue
            if any(t in blob for t in EARNER_TERMS):
                continue
            cands.append(d)
    cands.sort(key=lambda x: x["score"], reverse=True)
    return cands[:DISCUSSION_CANDIDATES]


# --- comment drafting (Claude) --------------------------------------------------------------
_POSITLY_CONTEXT = (
    "Positly (positly.com) is a participant-recruitment platform for online research and surveys "
    "that reaches demographically targeted, quality-screened participants, with fraud and "
    "AI-response filtering (QualityGuard). Igor works on Positly."
)


def _claude():
    import anthropic

    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY


def _text(msg) -> str:
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()


def draft_recruitment_reply(post: dict) -> str:
    system = (
        f"{_POSITLY_CONTEXT}\n\n"
        "Igor found a Reddit post where someone is recruiting study participants / seeking survey "
        "respondents. Draft a SHORT reply (2-4 sentences) Igor could leave.\n\n"
        "Rules:\n"
        "  - Open by engaging with the SPECIFICS of their post (topic, population, constraint).\n"
        "  - Mention Positly naturally as one option for reaching the participants they need. No "
        "hype, no marketing clichés, no links.\n"
        "  - Include a brief honest disclosure, e.g. 'full disclosure, I work on Positly'.\n"
        "  - If Positly is NOT a good fit, say so honestly and give a genuinely useful alternative "
        "instead of forcing a mention.\n"
        "  - Sound like a helpful human researcher. Output ONLY the comment text."
    )
    user = f"Subreddit: r/{post['subreddit']}\nTitle: {post['title']}\n\nBody:\n{post['selftext'][:1500] or '(no body text)'}"
    return _text(_claude().messages.create(model=ADVISOR_MODEL, max_tokens=400, system=system,
                                           messages=[{"role": "user", "content": user}]))


def draft_discussion_reply(post: dict) -> str:
    system = (
        f"{_POSITLY_CONTEXT}\n\n"
        "Igor found a Reddit post that may be a RESEARCHER discussing how or where to recruit "
        "participants online (platforms, panels, Prolific/MTurk/CloudResearch, participant pools, "
        "data quality when recruiting online, etc.).\n\n"
        "FIRST decide if this is genuinely a researcher-POV discussion about recruiting participants "
        "online. If it is instead from the EARNER point of view (someone wanting to make money taking "
        "surveys), or not really about online recruitment at all, respond with EXACTLY the single "
        "word: SKIP\n\n"
        "Otherwise, draft a SHORT reply (2-5 sentences) that adds genuine value to the discussion: "
        "share a substantive, balanced perspective on online recruitment (trade-offs of the tools "
        "they mention, data-quality/screening tips), and mention Positly naturally as one option "
        "worth knowing about — not as an ad. Include a brief honest disclosure, e.g. 'disclosure: I "
        "work on Positly'. No hype, no links. Output ONLY the comment text (or SKIP)."
    )
    user = f"Subreddit: r/{post['subreddit']}\nTitle: {post['title']}\n\nBody:\n{post['selftext'][:1800] or '(no body text)'}"
    return _text(_claude().messages.create(model=ADVISOR_MODEL, max_tokens=450, system=system,
                                           messages=[{"role": "user", "content": user}]))


# --- compose + send -------------------------------------------------------------------------
def _fmt_section(label: str, post: dict, draft: str) -> list[str]:
    out = [
        "=" * 70,
        f"{label} — r/{post['subreddit']} · {post['created'].strftime('%Y-%m-%d')}",
        f"  {post['title']}",
        f"  Link: {post['url']}",
        "",
        "  Draft reply:",
    ]
    for line in (draft or "").splitlines() or [""]:
        out.append(f"  {line}")
    out.append("")
    return out


def build_email(recruit: tuple | None, discuss: tuple | None, errors: dict) -> tuple[str, str]:
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    n = sum(x is not None for x in (recruit, discuss))
    flag = " ⚠️ PARTIAL" if errors else ""
    subject = f"Positly on Reddit — {today} ({n} post{'s' if n != 1 else ''}){flag}".strip()

    parts = [
        "Positly — Daily Reddit Finder",
        f"Generated {today}",
        "",
        "Draft replies to review — nothing posted. Several subreddits restrict promotion in "
        "comments (r/SampleSize especially); check each sub's rules and lead with genuine help.",
        "",
    ]
    if recruit:
        parts += _fmt_section("① RECRUITMENT (someone seeking participants)", recruit[0], recruit[1])
    if discuss:
        parts += _fmt_section("② DISCUSSION (researcher POV on online recruitment)", discuss[0], discuss[1])

    if errors:
        parts.append("— ⚠️ ISSUES THIS RUN —")
        for src, msg in errors.items():
            parts.append(f"  • {src}: {msg}")
            if FIX_INSTRUCTIONS.get(src):
                parts.append(f"      Fix: {FIX_INSTRUCTIONS[src]}")
        parts.append("")

    parts.append("— end —")
    return subject, "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print the email instead of sending")
    args = ap.parse_args()

    errors: dict[str, str] = {}
    recruit: tuple | None = None
    discuss: tuple | None = None

    try:
        reddit = _reddit()
    except Exception as e:  # noqa: BLE001
        errors["reddit"] = f"{type(e).__name__}: {e}"
        reddit = None

    if reddit is not None:
        # A. recruitment
        try:
            post = find_recruitment_post(reddit)
            if post:
                recruit = (post, draft_recruitment_reply(post))
        except Exception as e:  # noqa: BLE001
            errors.setdefault("narrative", f"{type(e).__name__}: {e}")
            print(f"[warn] recruitment step failed: {e}", file=sys.stderr)

        # B. discussion — gate each candidate until one is a real researcher-POV discussion
        try:
            for cand in find_discussion_candidates(reddit):
                draft = draft_discussion_reply(cand)
                if draft.strip().upper() != "SKIP" and draft.strip():
                    discuss = (cand, draft)
                    break
        except Exception as e:  # noqa: BLE001
            errors.setdefault("narrative", f"{type(e).__name__}: {e}")
            print(f"[warn] discussion step failed: {e}", file=sys.stderr)

    # Nothing qualifying and no errors worth flagging → send nothing (per spec).
    if recruit is None and discuss is None and not errors:
        print("[positly-reddit] no qualifying posts today — sending nothing.", file=sys.stderr)
        return 0
    # If both empty but reddit itself failed, still notify so the pipeline isn't silently broken.
    if recruit is None and discuss is None and "reddit" not in errors:
        print("[positly-reddit] no qualifying posts (with minor warnings) — sending nothing.", file=sys.stderr)
        return 0

    subject, body = build_email(recruit, discuss, errors)

    if args.dry_run:
        print(f"Subject: {subject}\n")
        print(body)
        return 0

    try:
        email_transport.send_email(subject, body, EMAIL_TO, from_label=EMAIL_FROM_LABEL, header_tag="positly-reddit")
        print(f"[positly-reddit] email sent to {EMAIL_TO}.", file=sys.stderr)
        return 0
    except Exception as e:  # noqa: BLE001
        reason = f"{type(e).__name__}: {e}"
        print(f"[error] email send failed: {reason}", file=sys.stderr)
        traceback.print_exc()
        if email_transport.slack_fallback(reason, "Positly Reddit finder"):
            print("[positly-reddit] notified via Slack fallback.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
