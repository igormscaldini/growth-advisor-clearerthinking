# Task bot: email Claude an instruction, it gets done

Email your Gmail address with `+claude` before the `@` (the same address the script prints on install): a question about CT, or a forwarded email with what you want done on the first line. The bot replies in the same thread with what it understood. It answers questions straight away; for anything that changes an account it lists the exact changes and waits for your "yes". Every task is logged in the **Tasks** tab of the dashboard, https://growth-advisor-clearerthinking.vercel.app/#tasks (also at /tasks).

Built 2026-11-18; confirm-first, refunds, questions and the dashboard tab added 2026-11-20. Code: `task_bot.py` (reads the email, runs the task, reports), `task_actions.py` (the actions and their safety limits), `task_log.py` (the log), workflow `.github/workflows/task-bot.yml`, the every-minute check `frontend/app/api/task-bot-ping/` (Vercel Cron, `frontend/vercel.json`), page `frontend/app/tasks/`.

## Using it

Write the instruction above the forwarded email, in plain words:

- "claude, remove from CT beehiiv"
- "claude, cancel their subscription on Stripe and let them know I've processed it. Also let Angel know about the churn, and when their billing cycle ends."
- "claude, refund her last payment and cancel"
- "how many new subscribers did we get last week, and where from?" (no forward needed)
- "make a spreadsheet of last week's sign-ups by day" or "turn the notes below into a 6-slide deck"

It also works without forwarding anything ("claude, unsubscribe jane@example.com from beehiiv"): the person only has to be named in what you send.

What happens next:

1. Within about three minutes (once the GitHub token below is set up) the bot replies in the thread. It starts with **What I understood**, so you can check it got the task right.
2. A **question** is answered in that same reply, from live GA4, Stripe, beehiiv and Search Console data plus the advisor's memory (the same tools as the weekly letter's replies).
3. A task that **changes an account** (unsubscribe, cancel, refund) is not carried out yet. The reply lists each change exactly ("Refund $45 of the $45 payment of November 3, 2026 to jane@...") and ends with "Nothing has been changed yet". The task shows as **Awaiting your OK**.
   - Reply **yes** (or "ok", "go ahead", "sim, pode") and the bot makes exactly those changes, then writes any emails it promised as drafts. Only a short yes counts: "yes but only $20" is read as a correction.
   - Reply **no** and it drops the plan.
   - Reply with **corrections** and it sends a new plan.
   - A plan nobody answers expires after 7 days.
4. Emails to other people are always left as **drafts in your Gmail** for you to read and send. A reply to the person who wrote the forwarded email is placed inside that same conversation when your forward is part of it in Gmail (the normal case); otherwise it is a new email. A task that only asks for a draft is done straight away (a draft changes nothing until you send it).
5. If something is unclear (no subscriber under that address, two subscriptions, a request it cannot do), it changes nothing and asks you. Reply to its email to answer.

Statuses: **Awaiting your OK** (a plan waits for your yes; nothing changed); **Needs you** (it asked you something); **Drafts waiting** (changes made, drafts not sent yet; flips to Done within about 15 minutes of you sending them); **Running**; **Failed** (the thread says what was and was not done); **Done**; **Cancelled** (you said no); **Replaced** (you corrected it, see the newer task); **Expired**.

## What it can do, and what it cannot

| Action | What it does | Limit per email |
|---|---|---|
| Answer a question about CT | GA4, Stripe revenue, beehiiv, Search Console, weekly history, your recent inbox, the advisor's memory (all read-only) | no limit |
| Look a person up | Newsletter status in beehiiv, subscriptions and payments in Stripe (read-only) | 8 each |
| Unsubscribe (after your yes) | Unsubscribes the address in beehiiv and reads it back to confirm | 3 |
| Cancel a subscription (after your yes) | Sets it to cancel at the END of the billing period (no more charges, access until that date), and confirms | 2 |
| Refund a payment (after your yes) | Refunds any amount up to what is still unrefunded on one of that person's payments (your choice: no cap beyond the charge). Covers one-off purchases made without an account (PDF, Cognitive Assessment) | 3 |
| Draft an email | Leaves a Gmail draft, never sends | 4 |
| Create a Google Doc, Sheet or Slides deck | A NEW file in the "Claude tasks" folder of your Drive, private to you; the reply links to it. Docs keep headings, lists, links and tables; sheets keep numbers and formulas (not ones that fetch from the web: IMPORTXML, IMAGE, HYPERLINK); decks use Google's plain theme with the detail in the speaker notes. Made straight away, no yes needed | 3 of each |

Not possible, on purpose: immediate cancellations, plan changes, deleting anyone's data, sending email, and opening, editing or sharing any Google file (to work from an existing Doc, paste its text into your email; the bot makes a new file). Asked for one of these, the bot says so and stops. A period-end cancellation can be undone in Stripe until the date it takes effect; a refund cannot be undone.

## Why it is safe to forward a stranger's email to it

A forwarded email is text written by someone else, and it could contain "also refund everyone". Five things stand between that text and your accounts, all enforced in code (`task_actions.py`, `task_bot.py`), not in the prompt:

1. **Only you can give it tasks.** It acts only on messages Gmail itself filed as *sent by your account*. Anyone can write to the +claude address (this repository is public); their mail is never read as a task.
2. **Only people named in your email.** Every action is refused for an address that does not appear in what you sent.
3. **Small budgets.** The limits in the table are per email, whatever the text asks for.
4. **Nothing changes without your yes.** The model can only propose; each proposal is checked against live data (the payment belongs to that person, the amount is still refundable). Your yes is recognised by a fixed rule, not by the model, and then the code itself makes exactly the listed changes, each once. The plan travels in a hidden header of the bot's reply, which only counts when Gmail filed that reply as sent by your account.
5. **Nothing goes out without you.** Emails are drafts, and Google files are created private and never shared.

Google login: the bot has its own token (`python auth_taskbot_google.py --github` mints it; secret `TASKBOT_GOOGLE_TOKEN_JSON`) with only Google's `drive.file` permission. That permission covers every file made through this project's OAuth client, so besides its own files it can technically reach the ~15 sheets other scripts here created (Navigator subscribers, outreach lists, the task log), checked live 2026-11-22. The bot has no tool that lists, reads, edits or shares a file, so it never does; keep it that way, or give it an OAuth client of its own before adding one. The Drive API was enabled on the GCP project for this on 2026-11-22.

The report you receive is built from the tools' own record of what they did, not from what the model says, and it lists anything the safety limits blocked. In the live test of 2026-11-18 the forwarded email contained an instruction to unsubscribe a second person; the bot ignored it and said so in its report.

Privacy: the repository and its Actions logs are public, so the bot logs message ids, counts and statuses only. Names, addresses and email text live in your Gmail and in the private task-log sheet.

## Contacts (who "Angel" is)

The task log is a Google Sheet in your Drive called **Claude tasks**. Its **Contacts** tab lists people the bot may address drafts to besides the person in the email: Name, Email, Send from (which of your addresses the draft uses) and Notes (shown to the bot, so "tell her when a Navigator cancels: who, which plan, the date the billing cycle ends" is a standing instruction). Angel is already there. Add a row to add a contact; no code change.

Drafts to customers go out from igor@clearerthinking.org unless the customer wrote to another of your addresses (set `TASK_BOT_DEFAULT_FROM` to change the default).

## Setup (once): one command, three hidden prompts

Open a terminal in this project and run:

```
bash bots/set_task_bot_secrets.sh
```

It asks for three things, one after the other. Each is typed or pasted at a hidden prompt (nothing shows while you type), each is tested before it is saved, and pressing Enter skips a step so you can do it later (`bash bots/set_task_bot_secrets.sh page`, `trigger` or `stripe` runs one step alone).

**1. A password for the task log.** Make one up, 12 characters or more. You will type it once per device in the dashboard's Tasks tab (https://growth-advisor-clearerthinking.vercel.app/#tasks). Until it is set, the tab shows "not set up yet" and nothing else.

**2. A GitHub token, so a task starts within a minute.** Without it the bot only runs when GitHub's own schedule fires (5 or 6 times a day here), so a task can wait hours. To create it:

1. Open https://github.com/settings/personal-access-tokens/new
2. Token name: `Task bot trigger`. Expiration: the longest offered ("No expiration" if it is there).
3. Repository access: **Only select repositories**, then pick `growth-advisor-clearerthinking`.
4. Permissions > Repository permissions > **Actions**: **Read and write**. Leave everything else alone.
5. **Generate token** and copy it (it starts with `github_pat_`). Paste it at the script's second prompt.

The script proves the token works by starting one run of the bot, then gives it to the dashboard. From then on the dashboard checks Gmail every minute and starts the bot when a task email is waiting. It tells GitHub only "run the workflow": no email content leaves Gmail through it. If the token has an expiry date, put a reminder in your calendar; when it lapses, tasks quietly fall back to the slow schedule.

**3. A Stripe key, so the bot can cancel subscriptions and refund.** The key this project already has is read-only (tested 2026-11-18: an update call is refused with 403). To create one that can cancel:

1. Open https://dashboard.stripe.com/apikeys in live mode and click **Create restricted key** (if Stripe asks how the key will be used, choose the option for an integration you built).
2. Key name: `Task bot`.
3. Set **Customers: Read**, **Subscriptions: Write**, **Products: Read**, **Charges and Refunds: Write** and **Checkout Sessions: Read**. Leave everything else on None.
4. **Create key**, reveal it and copy it (it starts with `rk_live_`). Paste it at the script's third prompt.

The script proves each permission without changing anything: a cancel on a subscription id that does not exist, and a refund larger than your latest payment (Stripe always rejects that, so no money moves). Until this key exists, unsubscribes and drafts work, and an approved cancel or refund ends as "Needs you" with the reason.

When the script finishes it redeploys the dashboard; give it two minutes.

### Then try it

Email your +claude address a question ("how many sign-ups this week?"), or forward any email with a first line such as "claude, look this person up and tell me what you find". With step 2 done, the reply arrives in about three minutes and the task appears in the Tasks tab.

## Checking it and fixing it

```
gh run list --workflow task-bot.yml --limit 5     # recent runs
gh workflow run task-bot.yml                      # run now
gh workflow disable task-bot.yml                  # pause (`gh workflow enable task-bot.yml` resumes)
python task_bot.py --dry-run                      # locally: read pending tasks, simulate, print; changes nothing
```

- A run that ends red means a task failed or a report could not be sent; you also get GitHub's own email. A task that failed is marked "Failed" and is not retried: forward the email again once the cause is fixed.
- "Not logged in" or "Failed to authenticate" in a report: the Claude token expired, run `bash bots/set_claude_token.sh`.
- A task email that never gets a reply: it was probably not sent from the Gmail account itself (for example from another mailbox); only mail in that account's Sent folder counts. If it was, the GitHub token has probably expired: run `bash bots/set_task_bot_secrets.sh trigger` with a new one.

## Adding an action

A read-only tool: a function in `task_actions.py` with the `@tool` decorator (it must call `require_in_scope` and `spend`), a `BUDGET`, an entry in `TOOL_FNS` and `TOOLS`, and a test in `tests/test_task_bot.py`. A tool that changes something must also: call `require_approved` first and `record` what it did; be added to `GATED` and `CHANGE_KEYS` (the arguments that identify one change) and to `TOOL_FNS` but NOT to `TOOLS` (the model never calls it; `task_bot.execute_plan` does); and get a branch in `check_change` that validates a proposal against live data and words it for you. A new data tool for questions goes in `advisor_reply.py` instead; both bots pick it up.
