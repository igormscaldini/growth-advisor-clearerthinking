# Weekly advisor letter as a Claude Code routine

The Friday growth-advisor letter can run as a Claude Code **routine** (a scheduled cloud
session on Igor's Claude subscription) instead of through the Anthropic API. The data
gathering and the email sending stay in `weekly_advisor.py`; the routine's own Claude session
writes the letter and the memory update, so no API credits are used.

Three steps, all run inside the routine session from the repository checkout:

1. `python weekly_advisor.py --brief /tmp/advisor/brief.json`
   Gathers everything (GA4, Stripe, beehiiv, GSC, goals, memory, session digests, inbox) and
   writes one JSON brief. No Claude call, nothing sent. Sources that fail are recorded in
   `errors` inside the brief and end up in the email as usual.
2. The session reads the brief and writes two files (see "Writing the letter" below):
   `/tmp/advisor/letter.md` and `/tmp/advisor/memory_updates.json`.
3. `python weekly_advisor.py --send-letter /tmp/advisor/letter.md --brief /tmp/advisor/brief.json --memory-updates /tmp/advisor/memory_updates.json`
   Appends the memory updates to the encrypted durable memory (commit + push), refreshes the
   dashboard snapshot, composes the email (greeting, letter, source errors, footer) and sends
   it through the Gmail API. Add `--dry-run` to print instead of sending.

## Instructions for the routine session

You are running the weekly Clearer Thinking growth-advisor letter. Work only from the
repository checkout; do not modify code, and do not commit anything yourself (step 3 commits
the memory update and the dashboard snapshot on its own).

1. Install dependencies if needed: `pip install -r requirements.txt` (quiet). Python 3.11+.
2. Run step 1 exactly as written above. It takes several minutes (beehiiv pagination). If it
   exits non-zero, read its stderr, and still try to continue with whatever brief it wrote;
   if there is no brief at all, stop and report the error as your final message.
3. Read `/tmp/advisor/brief.json`. The field `letter_system` is your role and rules, and
   `letter_user` is the material. Follow `letter_system` to the letter: three movements of
   plain prose, 350 to 650 words, no headers, no greeting, no sign-off, never an em dash,
   never an invented number. Write the result to `/tmp/advisor/letter.md` as plain text
   (no Markdown headings, no code fences).
4. If `consolidate_user` is not null, follow `consolidate_system` with it and write the JSON
   array it asks for to `/tmp/advisor/memory_updates.json` (write `[]` when there is nothing
   new). If `consolidate_user` is null, write `[]`.
5. Run step 3 exactly as written above. Its stderr says whether the email was sent.
6. Final message: one line saying whether the email was sent, plus the list of source errors
   from the brief, if any. Never paste the letter, the brief or any memory content into the
   final message.

Never send the letter through any other channel, never run the API path (the script without
`--brief` / `--send-letter`), and never edit or commit files in the repository.

## Cloud environment setup (one time, in the claude.ai environment editor)

Prerequisite: the routine checks the repository out from GitHub, and claude.ai refuses to
save a routine with a repository source until the GitHub account is connected (run
`/web-setup` in Claude Code, or install the Claude GitHub App at
https://claude.ai/code/onboarding?magic=github-app-setup). Creating the routine is a single
API call once that is done; the schedule is Fridays 11:00 UTC, model claude-opus-5, tools
Bash/Read/Write/Edit/Glob/Grep, prompt = the section above.

The routine runs in an Anthropic-hosted cloud environment (Ubuntu, Python 3 with pip). The
script reads the same names as the GitHub Actions secrets, so copy the values from the
repository's GitHub secrets or from the local `.env`:

- Environment variables: `GA4_PROPERTY_ID`, `GSC_SITE_URL`, `STRIPE_SECRET_KEY`,
  `OAUTH_CLIENT_JSON`, `GOOGLE_TOKEN_JSON` (the two JSON blobs, quoted as one line each),
  `BEEHIIV_API_KEY`, `BEEHIIV_PUB_CLEARER_THINKING`, `ADVISOR_MEMORY_KEY`,
  `GOOGLE_ADS_DEVELOPER_TOKEN`, `GOOGLE_ADS_CUSTOMER_ID`, `GOOGLE_ADS_LOGIN_CUSTOMER_ID`
  (the last three only for the dashboard snapshot refresh), optionally `GMAIL_ADDRESS`,
  `ADVISOR_EMAIL_TO`, `SLACK_BOT_TOKEN`, `SLACK_DEFAULT_CHANNEL`.
- Network access: **Custom**, keep "Also include default list of common package managers"
  checked (that list already covers `*.googleapis.com`, GitHub and PyPI), and add:
  `api.stripe.com`, `api.beehiiv.com`, and `slack.com` if the Slack fallback is wanted.
  (Or simply **Full**.)
- Git pushes (memory consolidation, snapshot refresh) go through Claude's GitHub proxy with
  Igor's GitHub connection; if they fail, the email still goes out and lists the failure.

While both the routine and `.github/workflows/weekly-advisor-email.yml` are scheduled for
Fridays 11:00 UTC, two emails arrive. Once the routine has produced one good letter, remove
the `schedule` block from that workflow (keep `workflow_dispatch`).
