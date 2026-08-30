"""Monthly automated SEO-expert email for Clearer Thinking.

Every month this:
  1. Pulls Google Search Console query/page performance (last 28 days vs. prior 28) — query-level
     gains/losses, striking-distance keywords, low-CTR-despite-good-position, and page-level
     click decay. See seo_data.py.
  2. Pulls Ahrefs data via the Ahrefs API v3: Rank Tracker project deltas, a broader organic
     keyword-opportunity scan, and the organic-competitor landscape.
  3. Asks Claude, acting as an SEO expert for Clearer Thinking, to write exactly 10 numbered,
     direct-instruction bullets — grounded in GOALS.md and CT_TOOLS.md — prioritized by
     estimated impact.
  4. Sends it as a plain-text email via the Gmail API (SMTP fallback locally, Slack as last resort).

Robustness follows weekly_advisor.py: every data source is wrapped so one failure can't kill the
run; failed sources are listed in the email with specific fix instructions.

Run locally:   .venv/bin/python seo_advisor.py --dry-run        # print, don't send
               .venv/bin/python seo_advisor.py                  # send for real
On CI:         .github/workflows/seo-advisor-email.yml (1st of month, 11:00 UTC)
"""
from __future__ import annotations

import argparse
import os
import sys
import traceback
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent


def _materialize_ci_secrets() -> None:
    """On CI the OAuth JSON blobs arrive as env vars; write them where the clients expect."""
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
from seo_data import gather_seo_snapshot  # noqa: E402

ADVISOR_MODEL = os.getenv("ADVISOR_MODEL") or os.getenv("ANTHROPIC_MODEL") or "claude-opus-4-8"
EMAIL_FROM_LABEL = "CT SEO Advisor"
EMAIL_TO = os.getenv("ADVISOR_EMAIL_TO") or email_transport.EMAIL_FROM

FIX_INSTRUCTIONS = {
    "gsc_queries": "GSC auth likely expired, or GSC_SITE_URL is wrong. Re-run `python auth_ga4.py` "
                   "locally and update the GOOGLE_TOKEN_JSON GitHub secret / GSC_SITE_URL.",
    "gsc_pages": "Same GSC auth/config issue as gsc_queries — see its fix.",
    "ahrefs_rank_tracker": "Check AHREFS_API_KEY and AHREFS_PROJECT_CLEARERTHINKING in .env / GitHub secrets.",
    "ahrefs_keywords": "Check AHREFS_API_KEY, and confirm the Ahrefs account still has API unit quota.",
    "ahrefs_competitors": "Check AHREFS_API_KEY, and confirm the Ahrefs account still has API unit quota.",
    "narrative": "Claude API call failed — check ANTHROPIC_API_KEY and account credits, "
                 f"and that the model id '{ADVISOR_MODEL}' is available (override with ADVISOR_MODEL).",
    "transport": email_transport.TRANSPORT_FIX,
}


# --- deterministic stats block (Section 1 — always-accurate, no LLM) ------------------------
def _num(v) -> str:
    return f"{v:,}" if isinstance(v, (int, float)) else "n/a"


def _pct(v) -> str:
    return f"{v:+.1f}%" if isinstance(v, (int, float)) else "n/a"


def build_stats(snapshot: dict) -> str:
    L = ["SECTION 1: THE NUMBERS", ""]
    period = snapshot.get("period", {})
    cur_range = " to ".join(period.get("current", ["?", "?"]))
    prev_range = " to ".join(period.get("prior", ["?", "?"]))
    L.append(f"GSC period: {cur_range} (vs. prior {prev_range})")

    qm = snapshot.get("gsc_query_movers") or {}
    totals = qm.get("totals", {})
    L.append(f"  Organic clicks:      {_num(totals.get('cur_clicks'))} ({_pct(totals.get('click_change_pct'))} vs prior)")
    L.append(f"  Organic impressions: {_num(totals.get('cur_impressions'))} ({_pct(totals.get('impression_change_pct'))} vs prior)")
    L.append(f"  Queries gained ≥ 3 positions: {len(qm.get('gains', []))}")
    L.append(f"  Queries lost ≥ 3 positions:   {len(qm.get('losses', []))}")
    L.append(f"  Pages with click decay (≥ 25% drop): {len(snapshot.get('gsc_page_decay') or [])}")

    rt = snapshot.get("ahrefs_rank_tracker") or {}
    if rt:
        L.append(
            f"  Ahrefs Rank Tracker: {rt.get('tracked_keyword_count', 'n/a')} keywords tracked, "
            f"{len(rt.get('movers', []))} moved ≥ 2 positions"
        )

    striking = qm.get("striking_distance", [])
    if striking:
        top = striking[0]
        L.append(
            f"  Biggest striking-distance opportunity: \"{top['query']}\" — position {top['position']}, "
            f"{_num(top['impressions'])} impressions/mo, {top['ctr'] * 100:.2f}% CTR"
        )
    return "\n".join(L)


# --- narrative (Section 2 — the 10 actions, from Claude) ------------------------------------
def build_seo_narrative(snapshot: dict, goals_text: str, tools_text: str) -> str:
    import json

    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    system = (
        "You are a seasoned SEO expert for Clearer Thinking (clearerthinking.org), a publisher of "
        "free interactive self-insight tools that monetizes via a paid subscription, a $9 "
        "personality-test PDF, and a $35/$17.50 cognitive assessment. You are writing the monthly "
        "SEO action list for Igor, who runs growth. You are given GOALS.md (the business's growth "
        "targets, including a specific #1-Google-ranking target), a snapshot of live CT tools/pages, "
        "and structured SEO data (JSON) covering: Google Search Console query and page movers over "
        "the last 28 days vs. the prior 28, striking-distance keywords (position 8-20), keywords "
        "ranking well but with abnormally low click-through rate, page-level click decay, Ahrefs "
        "Rank Tracker position deltas, a broader Ahrefs keyword-opportunity scan, and Ahrefs organic "
        "competitors (their domain rating and keyword overlap with us).\n\n"
        "Output EXACTLY 10 numbered bullets (1-10), each one or two sentences, ordered by estimated "
        "impact (traffic potential × ease of execution). Each bullet MUST:\n"
        "  - Name a specific real keyword and/or a specific real URL taken from the provided data or "
        "tools list (never invent a URL or keyword that isn't in the data).\n"
        "  - State a concrete, literal action Igor can go do today (rewrite this title tag to X, add "
        "an internal link from page A to page B, add an FAQ section covering query Y, investigate why "
        "page Z lost N% of its clicks, add this untapped keyword to the Ahrefs rank tracker project, "
        "publish a comparison page targeting a competitor's overlapping keyword, etc.) — not vague "
        "advice like \"improve SEO\" or \"optimize content.\"\n"
        "  - Include the concrete number that justifies it (impressions, position, CTR, volume, or "
        "% change) so Igor can judge priority at a glance.\n\n"
        "No preamble, no summary paragraph, no markdown formatting (no asterisks, no '#') — just the "
        "10 numbered lines. If a data source is missing or null, work only from what's present rather "
        "than inventing numbers."
    )
    user = (
        f"GOALS.md:\n{goals_text}\n\n"
        f"Live CT tools (for internal-linking / content-gap suggestions), truncated:\n{tools_text}\n\n"
        f"SEO data snapshot, JSON:\n{json.dumps(snapshot, indent=2, default=str)}"
    )
    msg = client.messages.create(
        model=ADVISOR_MODEL,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()


# --- compose + send --------------------------------------------------------------------------
def collect_errors(snapshot: dict, narrative_err: str | None) -> dict[str, str]:
    errs = dict(snapshot.get("errors", {}))
    if narrative_err:
        errs["narrative"] = narrative_err
    return errs


def build_email(snapshot: dict, narrative: str, errors: dict[str, str]) -> tuple[str, str]:
    today = date.today().isoformat()
    flag = "⚠️ PARTIAL — some sources failed" if errors else ""
    subject = f"Monthly SEO Report — {today} {flag}".strip()

    parts = ["Clearer Thinking — Monthly SEO Report", f"Generated {today}", ""]
    parts.append(build_stats(snapshot))
    parts.append("")
    parts.append("SECTION 2: YOUR 10 SEO ACTIONS THIS MONTH")
    if narrative:
        parts.append(narrative)
    else:
        parts.append("(Unavailable this month — see data issues below.)")

    if errors:
        parts.append("")
        parts.append("— ⚠️ DATA ISSUES THIS MONTH —")
        parts.append("Some sources couldn't be reached, so this report may be incomplete:")
        for src, msg in errors.items():
            parts.append(f"  • {src}: {msg}")
            fix = FIX_INSTRUCTIONS.get(src)
            if fix:
                parts.append(f"      Fix: {fix}")

    parts.append("")
    parts.append("— end of report —")
    return subject, "\n".join(parts)


# --- main -------------------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print the email instead of sending")
    args = ap.parse_args()

    print("[seo-advisor] gathering SEO snapshot...", file=sys.stderr)
    snapshot = gather_seo_snapshot()

    goals_text = ""
    gp = ROOT / "GOALS.md"
    if gp.exists():
        goals_text = gp.read_text()[:4000]

    tools_text = ""
    tp = ROOT / "CT_TOOLS.md"
    if tp.exists():
        tools_text = tp.read_text()[:6000]

    narrative, narrative_err = "", None
    try:
        narrative = build_seo_narrative(snapshot, goals_text, tools_text)
    except Exception as e:  # noqa: BLE001
        narrative_err = f"{type(e).__name__}: {e}"
        print(f"[warn] narrative failed: {e}", file=sys.stderr)

    errors = collect_errors(snapshot, narrative_err)
    subject, body = build_email(snapshot, narrative, errors)

    if args.dry_run:
        print(f"Subject: {subject}\n")
        print(body)
        return 0

    try:
        email_transport.send_email(subject, body, EMAIL_TO, from_label=EMAIL_FROM_LABEL, header_tag="seo-report")
        print("[seo-advisor] email sent.", file=sys.stderr)
        return 0
    except Exception as e:  # noqa: BLE001
        reason = f"{type(e).__name__}: {e}"
        print(f"[error] email send failed: {reason}", file=sys.stderr)
        traceback.print_exc()
        if email_transport.slack_fallback(reason, "Monthly SEO report"):
            print("[seo-advisor] notified via Slack fallback.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
