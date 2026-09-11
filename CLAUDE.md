# Growth Advisor - Clearer Thinking

Igor's "super advisor" for his growth work at Clearer Thinking: a data layer over GA4, Stripe,
beehiiv, Search Console and Google Ads; a Next.js dashboard; and an AI advisor that emails a
weekly letter, answers replies, and remembers every conversation. Read GOALS.md before any
discussion of goals, targets or priorities: hitting those goals is Igor's 2026 priority.

## Layout
- `data_layer.py`: every metric function (GA4, Stripe, beehiiv, GSC, Ads). Streamlit cache
  decorators are harmless outside Streamlit. `_beehiiv_get` wraps beehiiv calls with
  timeout + retry; route new beehiiv endpoints through it.
- IMPORTANT: GitHub heavily throttles `schedule` events on this repo. Measured 2026-09-09:
  the `*/5` reply cron and the `*/30` snapshot cron BOTH actually fire only ~5-6 times a day
  (gaps of 2-4.5 h), regardless of the interval written. Tightening a cron expression does
  nothing. For anything needing real freshness use `workflow_dispatch` /
  `repository_dispatch` (not throttled) driven by a webhook or an external scheduler.
- `fetch_snapshot.py` -> `frontend/public/snapshot.json` (GitHub Actions cron nominally every
  30 min but see the throttling note above,
  25-minute budget) -> Vercel dashboard at https://growth-advisor-clearerthinking.vercel.app/.
  `frontend/public/beehiiv_new_subs_cache.json` is an incremental cache committed with the
  snapshot; delete it to force a full re-walk (takes ~25 min).
- `weekly_advisor.py`: Friday 11:00 UTC letter (results, the week's work, next week's
  priorities). Two ways to produce the letter: the API path (default, needs Anthropic credits)
  and routine mode (`--brief` then `--send-letter`, see `ADVISOR_ROUTINE.md`), where a Claude
  Code routine on Igor's subscription writes the letter; the routine can only be saved once
  GitHub is connected to claude.ai. `advisor_reply.py`: answers Igor's replies with live data
  tools every 5 min.
  `advisor_inbox.py`: Gmail scan of the week's threads. `advisor_conversations.py`: digests
  Claude Code transcripts. `advisor_memory.py`: the encrypted memory store all of them share.
- `stripe_navigator_subscribers.py`: Navigator subscribers -> Google Sheet, synced every
  15 min (`navigator-sheet-sync.yml`, sheet id in the `NAVIGATOR_SHEET_ID` secret and
  `.env`). The sheet write is an UPSERT matched on Subscription ID: columns right of the
  owned ones belong to Igor and are never touched. `--rebuild` is the destructive path and
  the cron never passes it. `--sheets` errors without a target rather than creating a stray
  sheet; pass `--new-sheet` to create one deliberately.
- `stripe_cancellations_report.py`: separate scheduled email. `seo_advisor.py`: monthly SEO email,
  schedule removed Sep 2026 at Igor's request (manual `workflow_dispatch` only).
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
- `context_saves/` (written by the global CLAUDE.md `save` command) is gitignored: the repo is public
  and `auto-push.sh` does `git add -A`, so it must never be committed.

## Data gotchas
- beehiiv `created` = date the record entered beehiiv; bulk imports (utm_channel "import",
  ~200k in Aug 2026, ~350k Sep-Oct 2025) are excluded from "new subscribers". Cursor-paginate
  (offset paging caps at 10k). Genuine sign-ups run ~300-500/day.
- GA4 event names do not mean what they say: see `GA4_EVENTS.md`. "Tools finished" = Submitted Email.
- Gmail: SMTP app passwords are blocked from GitHub Actions; send and read through the Gmail API
  with the shared Google token (`secrets/ga4-token.json`, scopes incl. gmail.send/modify).
  To add scopes: edit SCOPES in `auth_ga4.py`, re-run it, then `gh secret set GOOGLE_TOKEN_JSON`.
  `secrets/slides-token.json` is a separate Slides-only token (presentations scope, same OAuth
  client) for editing Igor's Google Slides decks in place via the Slides API `replaceAllText`;
  the Slides API was enabled on the GCP project in Sep 2026. Keep it out of the CI secret.
- CI credentials: `secrets_loader.materialize_ci_secrets()` writes the OAuth blobs GitHub
  Actions passes as env vars to `secrets/`. Five older scripts still carry their own copy of
  this helper; prefer the shared one in new code.
- Claude model: `advisor_memory.advisor_model()` (ADVISOR_MODEL or ANTHROPIC_MODEL env, default
  claude-opus-5). CI has no override, so it uses the default.

## GuidedTrack tooling
- Credentials: `GUIDED_TRACK_USERNAME` / `GUIDED_TRACK_PASSWORD` in `.env` (verified 2026-09-11). The
  `guidedtrack-builder` skill drives `~/bin/gt` (needs `jq`); ALWAYS set `GT_ENV=production` or it
  targets localhost. Creds can be piped on stdin: email, password, then `production` for push
  (pull needs no confirmation line).
- Staging folder is `~/guidedtrack/` (filename = exact program name, no extension); `guidedtrack/*.gt`
  in this repo is a second copy of the same source. Both drift because Igor edits programs in the GT
  web editor after pushing (4 of 5 staged programs were behind live on 2026-09-11), so ALWAYS
  `gt pull` and diff before any push, or the push overwrites live edits.
- Run data: `GET /programs/{id}/exports?export_format=csv` returns all non-test runs incl.
  unfinished ones; `GET /programs/{id}/runs.json?page=N` is 25 per page (`per_page`/`limit` are
  ignored, iterate until empty) and includes test runs.

## Working conventions
- Igor's rules: no em dashes anywhere in prose; always ground audience claims in the survey and
  buyer data (see the knowledge base); keep CT+ / paid framing aligned with the mission.
- Reports go to `reports/` (HTML, with a timestamp subtitle); scratch work stays out of the root.
- After substantial work, refresh this file (keep it under ~200 lines).
