# Growth Advisor - Clearer Thinking

Igor's "super advisor" for his growth work at Clearer Thinking: a data layer over GA4, Stripe,
beehiiv, Search Console and Google Ads; a Next.js dashboard; and an AI advisor that emails a
weekly letter, answers replies, and remembers every conversation. Read GOALS.md before any
discussion of goals, targets or priorities: hitting those goals is Igor's 2026 priority.

## Layout
- `data_layer.py`: every metric function (GA4, Stripe, beehiiv, GSC, Ads). Streamlit cache
  decorators are harmless outside Streamlit. `_beehiiv_get` wraps beehiiv calls with
  timeout + retry; route new beehiiv endpoints through it.
- `fetch_snapshot.py` -> `frontend/public/snapshot.json` (GitHub Actions cron every 30 min,
  25-minute budget) -> Vercel dashboard at https://growth-advisor-clearerthinking.vercel.app/.
  `frontend/public/beehiiv_new_subs_cache.json` is an incremental cache committed with the
  snapshot; delete it to force a full re-walk (takes ~25 min).
- `weekly_advisor.py`: Friday 11:00 UTC letter (results, the week's work, next week's
  priorities). `advisor_reply.py`: answers Igor's replies with live data tools every 5 min.
  `advisor_inbox.py`: Gmail scan of the week's threads. `advisor_conversations.py`: digests
  Claude Code transcripts. `advisor_memory.py`: the encrypted memory store all of them share.
- `seo_advisor.py`, `stripe_cancellations_report.py`: separate scheduled emails.
- `tests/` (pytest, `pytest.ini`): pure-function tests; run `.venv/bin/python -m pytest -q`.
  CI runs them on every push (`tests.yml`).
- Reference docs: `GOALS.md`, `GA4_EVENTS.md`, `GUIDEDTRACK.md`, `CT_TOOLS.md`, `DEPLOY.md`.

## Advisor memory (advisor_memory/)
- The repo is PUBLIC (kept public so the 5-minute reply cron stays within free Actions minutes),
  so memory is Fernet-encrypted at rest: `conversations/<date>_<session8>.md.enc` (one per Claude
  Code session), `durable.md.enc` (facts, preferences, corrections), `knowledge/*.md.enc`
  (audience research, communication guidelines). Key: `ADVISOR_MEMORY_KEY` in `.env` and as a
  GitHub secret; both must match. `python advisor_memory.py show` prints everything decrypted.
- Session digests are produced by `.claude/on-stop.sh` (Stop + SessionEnd hooks in
  `.claude/settings.local.json`; Claude Code snapshots hooks at startup, so hook edits apply
  from the next session). Catch-up manually with `python advisor_conversations.py --sweep`.
- Never commit plaintext memory, subscriber CSVs (`reports/*.csv` is gitignored) or anything
  with personal data.

## Hooks and git
- `.claude/on-stop.sh` runs auto-commit + push (`auto-push.sh`) on every turn, then the digest in
  the background. Hook commands must be quoted: the path has spaces (this silently broke the
  hook from May to Aug 2026).
- Bot commits from CI (`snapshot: ...`) land on main every 30 min: always
  `git pull --rebase --autostash origin main` before pushing. `advisor_memory.git_commit_and_push`
  does this and waits for `index.lock`.
- Scheduled workflows run only from `main`, so advisor changes must land on `main` to take effect.

## Data gotchas
- beehiiv `created` = date the record entered beehiiv; bulk imports (utm_channel "import",
  ~200k in Aug 2026, ~350k Sep-Oct 2025) are excluded from "new subscribers". Cursor-paginate
  (offset paging caps at 10k). Genuine sign-ups run ~300-500/day.
- GA4 event names do not mean what they say: see `GA4_EVENTS.md`. "Tools finished" = Submitted Email.
- Gmail: SMTP app passwords are blocked from GitHub Actions; send and read through the Gmail API
  with the shared Google token (`secrets/ga4-token.json`, scopes incl. gmail.send/modify).
  To add scopes: edit SCOPES in `auth_ga4.py`, re-run it, then `gh secret set GOOGLE_TOKEN_JSON`.
- Claude model: `advisor_memory.advisor_model()` (ADVISOR_MODEL or ANTHROPIC_MODEL env, default
  claude-opus-5). CI has no override, so it uses the default.

## Working conventions
- Igor's rules: no em dashes anywhere in prose; always ground audience claims in the survey and
  buyer data (see the knowledge base); keep CT+ / paid framing aligned with the mission.
- Reports go to `reports/` (HTML, with a timestamp subtitle); scratch work stays out of the root.
- After substantial work, refresh this file (keep it under ~200 lines).
