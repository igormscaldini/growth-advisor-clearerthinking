# Bots and recurring routines

Every job that runs on its own for Igor's Clearer Thinking and Positly work: what it does, when it fires, where it runs and how to run or pause it. This folder is the index. The code stays where it already lives (scripts in the repository root, workflows in `.github/workflows/`), because the workflows, tests and scripts import each other by those paths.

Last verified: 2026-10-02 (states and last runs below are from that day).

## At a glance

| Bot | What it does | When (UTC) | Runs on | Since | State on 2026-10-02 |
|---|---|---|---|---|---|
| [Monthly wrap-up draft](#monthly-wrap-up-draft) | Builds the CT+ "Monthly Debrief" as a beehiiv draft, emails Igor to review it | 1st of month, 12:00 | Claude cloud routine | 2026-10-02 | Enabled. First scheduled run 2026-11-01. Podcast and YouTube hosts still blocked in the cloud environment |
| [Daily site health check](#daily-site-health-check) | Six checks of the CT site; emails only when one does not pass | Daily 10:00 | GitHub Actions | 2026-10-01 | Active. Only run so far (manual, 2026-10-01) reported failed sign-up links on /plus and /coaching |
| [All Articles hub sync](#all-articles-hub-sync) | Keeps the Wix "All Clearer Thinking Articles" post in step with the sitemap | Mondays 12:20 | GitHub Actions | 2026-09-30 | Active. Two manual runs passed; first scheduled run 2026-10-05 |
| [Workshop sign-ups sync](#workshop-sign-ups-sync) | Backfills Career Workshop sign-ups into a Google Sheet | Every 6 h | GitHub Actions | 2026-09-16 | Active and passing, but the workshop was held 2026-09-30: candidate to retire |
| [Navigator subscribers sync](#navigator-subscribers-sync) | Upserts CT+ Navigator subscribers from Stripe into a Google Sheet | Every 15 min (nominal) | GitHub Actions | 2026-09-09 | Active, passing |
| [Stripe cancellations email](#stripe-cancellations-email) | Weekly email of CT+ cancellations | Fridays 11:10 | GitHub Actions | 2026-08-30 | Active. Last run 2026-09-25 passed |
| [SEO advisor email](#seo-advisor-email) | SEO expert email from Search Console and Ahrefs | Manual only | GitHub Actions | 2026-08-30 | Schedule removed 2026-09-01. Last run 2026-09-01 |
| [Weekly growth-advisor letter](#weekly-growth-advisor-letter) | Friday letter: results, the week's work, next priorities | Fridays 11:00 | GitHub Actions | 2026-06-14 | Active. Last run 2026-09-25 passed |
| [Advisor reply handler](#advisor-reply-handler) | Answers Igor's email replies to the letter with live data | Every 5 min (nominal) | GitHub Actions | 2026-06-14 | Active, passing |
| [Dashboard snapshot](#dashboard-snapshot) | Refreshes the data behind the Vercel dashboard | Every 30 min (nominal) | GitHub Actions | 2026-05-26 | Active, passing |
| [Positly Reddit finder](#positly-reddit-finder) | Finds up to two Reddit posts a day and emails reply drafts | Mon to Fri 09:00 local | This Mac (launchd) | 2026-08-30 | Loaded, but its last run exited with code 127 |
| [Positly Saturday report](#positly-cloud-routines) | Emails the week's outbound campaign numbers | Saturdays 13:00 | Claude cloud routine | 2026-04-21 | Enabled. Last fired 2026-09-26 |
| [Positly Monday lead import](#positly-cloud-routines) | Adds 100 new leads to the outbound campaign | Mondays 13:00 | Claude cloud routine | 2026-04-21 | Enabled. Last fired 2026-09-28 |
| [Hourly email responder](#hourly-email-responder) | Drafts Gmail replies in Igor's voice | Hourly | Claude cloud routine | 2026-07-14 | Disabled. Last fired 2026-07-19 |
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

### Monthly wrap-up draft

- **Does:** on the 1st, crawls the previous month's newsletter articles, tool launches, podcast episodes and videos, writes the "Monthly Debrief" in CT's format, saves it as a **draft** in beehiiv by duplicating the previous edition, and emails Igor that it is ready to review. It never schedules or sends the post.
- **Routine:** `CT monthly wrap-up: beehiiv draft + review email`, https://claude.ai/code/routines/trig_019Siu4sPCwgnPEnPmdc8Lx9, cron `0 12 1 * *` (09:00 São Paulo), connectors beehiiv and Gmail.
- **Instructions:** [unattended-run.md](../.claude/skills/ct-monthly-wrapup/references/unattended-run.md) in the `ct-monthly-wrapup` skill. The routine downloads it and the skill's format files from `main` at the start of every run, so editing those files changes the next run. The routine's own prompt only holds the mode, the recipient and the hard limits.
- **Modes:** the prompt's `MODE:` line is `normal`, `preflight` (checks access, changes nothing) or `test` (full run into a draft titled `[ROUTINE TEST] ...`). Set it back to `normal` after testing.
- **Needs:** the cloud environment's network allow list must include `podcast.clearerthinking.org`, `www.youtube.com`, `www.clearerthinking.org` and `programs.clearerthinking.org`. Until it does, the run builds the draft from the newsletter pieces only and the email says so.
- **If it already ran:** a post titled `Monthly Debrief - {Month}` created in the last 45 days makes the run skip building and just email the link.

### Weekly growth-advisor letter as a routine (optional)

The Friday letter can also run as a cloud routine instead of through GitHub Actions. It is documented in [ADVISOR_ROUTINE.md](ADVISOR_ROUTINE.md) and is not set up as a routine today; the GitHub workflow below is the live path.

### Positly cloud routines

Two routines for the Positly outbound campaign, defined only on claude.ai (no code in this repository):

- **[Positly] Saturday performance report** (`0 13 * * 6`): pulls the last 7 days of campaign analytics from Instantly and emails a report through Resend.
- **[Positly] Monday lead import** (`0 13 * * 1`): pulls 100 leads matching the target profile from Instantly's lead search into the campaign.

Both keep their API keys as plain text inside the routine prompt. Moving them to the environment's variables would be safer.

### Hourly email responder

Reads unread Gmail threads and saves draft replies in Igor's voice; it can only draft, never send. Disabled since July 2026.

## GitHub Actions bots (this repository)

### Daily site health check

- **Does:** checks GA4 events, the top tools' events, the menu pages, the Sign Up links on /plus and /coaching, the Stripe checkout for each tier, and beehiiv sign-ups. Emails only when a check does not pass, plus a weekly summary on Mondays. A run with a failed check ends as "failure" on purpose.
- **Code:** `site_health_check.py`, workflow `site-health-check.yml`.
- **Try it safely:** `python site_health_check.py --dry-run` (add `--only links,checkout` for a subset).

### All Articles hub sync

- **Does:** compares the sitemap with the live Wix blog post that links every article, republishes only when something changed, and emails either way.
- **Code:** `wix_publish_hub.py --sync`, workflow `wix-hub-sync.yml`. The workflow commits the title cache in `reports/` back to the repository.
- **Try it safely:** `python wix_publish_hub.py --dry-run`.

### Workshop sign-ups sync

- **Does:** re-reads the Career Change Workshop program's export and appends any sign-up missing from the sheet. It is the safety net behind the live path (GuidedTrack posts each sign-up to the Vercel route `frontend/app/api/workshop-signup`).
- **Code:** `workshop_signups_sheet.py`, workflow `workshop-signups-sync.yml`.
- **Try it safely:** `python workshop_signups_sheet.py --dry-run`.
- **Note:** the workshop took place on 2026-09-30 and the program is now a recording page, so this has nothing new to catch. Pause it with `gh workflow disable workshop-signups-sync.yml` unless sign-ups are reopened.

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

- **Does:** gathers GA4, Stripe, beehiiv, Search Console and Ads data plus the advisor's memory, writes the Friday letter with headless Claude Code and emails it through the Gmail API.
- **Code:** `weekly_advisor.py`, workflow `weekly-advisor-email.yml`. Needs the `CLAUDE_CODE_OAUTH_TOKEN` secret.
- **Try it safely:** `python weekly_advisor.py --dry-run`.

### Advisor reply handler

- **Does:** picks up Igor's replies to the letter and answers them with live data tools; can also save something to the advisor's memory.
- **Code:** `advisor_reply.py`, workflow `advisor-reply.yml`.
- **Try it safely:** `python advisor_reply.py --dry-run`.

### Dashboard snapshot

- **Does:** writes `frontend/public/snapshot.json`, which the dashboard at https://growth-advisor-clearerthinking.vercel.app/ reads, and commits it.
- **Code:** `fetch_snapshot.py`, workflow `fetch-snapshot.yml`. No dry-run flag: running it locally rewrites the snapshot file.

## On this Mac

### Positly Reddit finder

- **Does:** every weekday looks for up to two Reddit posts (someone recruiting study participants, or researchers discussing recruitment platforms), drafts a reply for each and emails them. Nothing is posted automatically.
- **Code:** `positly_reddit_recruiter.py`, started by `run_positly_reddit.sh` from the launchd job `com.positly.reddit-finder`. It runs locally because Reddit blocks datacenter addresses.
- **Try it safely:** `.venv/bin/python positly_reddit_recruiter.py --dry-run`.
- **State:** on 2026-10-02 launchd reported 15 runs and a last exit code of 127, which usually means a command was not found. The cause is in `~/Library/Logs/positly-reddit-finder.err.log`; it has not been diagnosed.

## In another project

### Newsletter ratings email

A Monday 12:00 São Paulo email with the newsletter rating results, sent by a Vercel cron in the separate `ct-newsletter-ratings` project (its README has the details).

## Automatic, but not on a schedule

- **Workshop sign-up route:** GuidedTrack calls the Vercel route on every sign-up; nothing to schedule.
- **Claude Code stop hook:** `.claude/on-stop.sh` commits and pushes the working tree after every turn and digests the session into the advisor's encrypted memory.

## Adding a bot

Add a row to the table and a short section here in the same shape (does, code, try it safely). Give every new script a `--dry-run`, and say where failures show up.
