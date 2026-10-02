# Bots and recurring routines

Every job that runs on its own for Igor's Clearer Thinking work: what it does, when it fires, where it runs and how to run or pause it. This folder is the index. The code stays where it already lives (scripts in the repository root, workflows in `.github/workflows/`), because the workflows, tests and scripts import each other by those paths.

Last verified: 2026-10-02 (states and last runs below are from that day).

## At a glance

| Bot | What it does | When (UTC) | Runs on | Since | State on 2026-10-02 |
|---|---|---|---|---|---|
| [Daily site health check](#daily-site-health-check) | Six checks of the CT site; emails only when one does not pass | Daily 10:00 | GitHub Actions | 2026-10-01 | Active. Only run so far (manual, 2026-10-01) reported failed sign-up links on /plus and /coaching |
| [All Articles hub sync](#all-articles-hub-sync) | Keeps the Wix "All Clearer Thinking Articles" post in step with the sitemap | Mondays 12:20 | GitHub Actions | 2026-09-30 | Active. Two manual runs passed; first scheduled run 2026-10-05 |
| [Navigator subscribers sync](#navigator-subscribers-sync) | Upserts CT+ Navigator subscribers from Stripe into a Google Sheet | Every 15 min (nominal) | GitHub Actions | 2026-09-09 | Active, passing |
| [Stripe cancellations email](#stripe-cancellations-email) | Weekly email of CT+ cancellations | Fridays 11:10 | GitHub Actions | 2026-08-30 | Active. Last run 2026-09-25 passed |
| [SEO advisor email](#seo-advisor-email) | SEO expert email from Search Console and Ahrefs | Manual only | GitHub Actions | 2026-08-30 | Schedule removed 2026-09-01. Last run 2026-09-01 |
| [Weekly growth-advisor letter](#weekly-growth-advisor-letter) | Friday letter: results, the week's work, next priorities; Wednesday preflight of its credentials | Fridays 11:00 (preflight Wednesdays 11:00) | GitHub Actions | 2026-06-14 | Broken until the `CLAUDE_CODE_OAUTH_TOKEN` secret is set: no letter was written from 2026-09-04 to 2026-10-02 |
| [Advisor reply handler](#advisor-reply-handler) | Answers Igor's email replies to the letter with live data | Every 5 min (nominal) | GitHub Actions | 2026-06-14 | Active, passing |
| [Dashboard snapshot](#dashboard-snapshot) | Refreshes the data behind the Vercel dashboard | Every 30 min (nominal) | GitHub Actions | 2026-05-26 | Active, passing |
| [Newsletter ratings email](#newsletter-ratings-email) | Monday email with the newsletter ratings | Mondays 15:00 | Vercel cron, separate project | Sep 2026 | Not checked from here |

## Three things that apply to all of them

- **GitHub throttles scheduled workflows on this repository.** A cron written as every 5 or 30 minutes really fires 5 or 6 times a day, and a daily or weekly job lands a few hours late. Tightening the cron does nothing. Anything that needs real freshness uses a webhook or `workflow_dispatch`.
- **Scheduled workflows only run from `main`**, so a change to a bot takes effect once it is on `main`.
- **Secrets never live in this folder or in the code.** The GitHub bots read repository secrets (same names as `.env`); the cloud routines use claude.ai connectors. The repository is public.

## Everyday commands

GitHub Actions bots, from the repository root:

```
gh workflow run <file>.yml                     # run now
gh run list --workflow <file>.yml --limit 5    # recent runs
gh run view <run-id> --log-failed              # why a run failed
gh workflow disable <file>.yml                 # pause (enable to resume)
```

Cloud routines: https://claude.ai/code/routines (run now, pause, edit the prompt, see past runs). They can be paused but not deleted through the API; deleting is done on that page. From Claude Code, ask for the routine by name.

## Claude cloud routines

None are scheduled right now (checked 2026-10-02).

### Weekly growth-advisor letter as a routine (optional)

The Friday letter can also run as a cloud routine instead of through GitHub Actions. It is documented in [ADVISOR_ROUTINE.md](ADVISOR_ROUTINE.md) and is not set up as a routine today; the GitHub workflow below is the live path.

## GitHub Actions bots (this repository)

### Daily site health check

- **Does:** checks GA4 events, the top tools' events, the menu pages, the Sign Up links on /plus and /coaching, the Stripe checkout for each tier, and beehiiv sign-ups. Emails only when a check does not pass, plus a weekly summary on Mondays. A run with a failed check ends as "failure" on purpose.
- **Code:** `site_health_check.py`, workflow `site-health-check.yml`.
- **Try it safely:** `python site_health_check.py --dry-run` (add `--only links,checkout` for a subset).

### All Articles hub sync

- **Does:** compares the sitemap with the live Wix blog post that links every article, republishes only when something changed, and emails either way.
- **Code:** `wix_publish_hub.py --sync`, workflow `wix-hub-sync.yml`. The workflow commits the title cache in `reports/` back to the repository.
- **Try it safely:** `python wix_publish_hub.py --dry-run`.

### Navigator subscribers sync

- **Does:** lists every CT+ Navigator subscriber from Stripe and upserts them into the Google Sheet by subscription ID. Columns to the right of the ones it owns are Igor's and are never touched.
- **Code:** `stripe_navigator_subscribers.py --sheets --no-csv`, workflow `navigator-sheet-sync.yml`.
- **Careful:** `--rebuild` is the destructive path; the workflow never passes it.

### Stripe cancellations email

- **Does:** emails the week's CT+ cancellations every Friday.
- **Code:** `stripe_cancellations_report.py`, workflow `stripe-cancellations-email.yml`.
- **Try it safely:** `python stripe_cancellations_report.py --dry-run`.

### SEO advisor email

- **Does:** an SEO expert email built from Search Console and Ahrefs data. The monthly schedule was removed on 2026-09-01 at Igor's request; it runs only when started by hand.
- **Code:** `seo_advisor.py`, workflow `seo-advisor-email.yml`.
- **Try it safely:** `python seo_advisor.py --dry-run`.

### Weekly growth-advisor letter

- **Does:** gathers GA4, Stripe, beehiiv, Search Console and Ads data plus the advisor's memory, writes the Friday letter with headless Claude Code and emails it through the Gmail API, filed in the inbox as unread.
- **Code:** `weekly_advisor.py`, workflow `weekly-advisor-email.yml`. Needs the `CLAUDE_CODE_OAUTH_TOKEN` secret: run `claude setup-token` in a terminal, then `gh secret set CLAUDE_CODE_OAUTH_TOKEN` and paste the token. `gh secret list` shows whether it exists.
- **Preflight (Wednesdays):** the same workflow runs `python weekly_advisor.py --preflight`, one cheap live call per credential the letter depends on (Claude login, memory key, GA4, Stripe, beehiiv, Search Console, Gmail). It emails only when one fails, with the fix, two days before the letter. Run it by hand with `gh workflow run weekly-advisor-email.yml -f preflight=true`.
- **Where failures show up:** when Claude cannot write the letter, the email still goes out with the subject "NO LETTER, numbers only", the reason and fix at the top and the week's raw numbers below, and the run ends as "failure" so GitHub sends its own alert. A single failed data source only adds "PARTIAL" to the subject and the run stays green.
- **Try it safely:** `python weekly_advisor.py --dry-run` (add `--preflight` for the credential test).

### Advisor reply handler

- **Does:** picks up Igor's replies to the letter and answers them with live data tools; can also save something to the advisor's memory.
- **Code:** `advisor_reply.py`, workflow `advisor-reply.yml`.
- **Try it safely:** `python advisor_reply.py --dry-run`.

### Dashboard snapshot

- **Does:** writes `frontend/public/snapshot.json`, which the dashboard at https://growth-advisor-clearerthinking.vercel.app/ reads, and commits it.
- **Code:** `fetch_snapshot.py`, workflow `fetch-snapshot.yml`. No dry-run flag: running it locally rewrites the snapshot file.

## In another project

### Newsletter ratings email

A Monday 12:00 São Paulo email with the newsletter rating results, sent by a Vercel cron in the separate `ct-newsletter-ratings` project (its README has the details).

## Automatic, but not on a schedule

- **Workshop sign-up route:** the Vercel route `frontend/app/api/workshop-signup` wrote each Career Workshop sign-up to a Google Sheet. Nothing calls it since the workshop (2026-09-30).
- **Claude Code stop hook:** `.claude/on-stop.sh` commits and pushes the working tree after every turn and digests the session into the advisor's encrypted memory.

## Adding a bot

Add a row to the table and a short section here in the same shape (does, code, try it safely). Give every new script a `--dry-run`, and say where failures show up.

## Retired

- **Workshop sign-ups sync** (workflow `workshop-signups-sync.yml`, `workshop_signups_sheet.py`): deleted 2026-10-02, the workshop was over. The code is in git history.
- **Positly Reddit finder** (`positly_reddit_recruiter.py`, launchd job `com.positly.reddit-finder`): deleted 2026-10-02, job unloaded and its plist removed.
- **Positly cloud routines** (Saturday performance report, Monday lead import) and the **hourly email responder**: deleted on claude.ai by Igor, 2026-10-02.
- **Monthly wrap-up draft** (cloud routine, 1st of the month: built the CT+ "Monthly Debrief" as a beehiiv draft and emailed Igor): deleted 2026-10-02 at Igor's request, to be revisited later. Its instructions are kept in [unattended-run.md](../.claude/skills/ct-monthly-wrapup/references/unattended-run.md). In testing, everything worked from the cloud (reading beehiiv, duplicating and editing the draft, sending the email) except reading the podcast, YouTube and clearerthinking.org hosts, which the cloud environment's network allow list blocked.
