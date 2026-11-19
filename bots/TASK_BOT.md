# Task bot: email Claude an instruction, it gets done

Forward any email to your Gmail address with `+claude` before the `@` (the same address the script prints on install), and write what you want on the first line. The bot carries it out, replies in the same thread, and logs it at https://growth-advisor-clearerthinking.vercel.app/tasks.

Built 2026-11-18. Code: `task_bot.py` (reads the email, runs the task, reports), `task_actions.py` (the actions and their safety limits), `task_log.py` (the log), workflow `.github/workflows/task-bot.yml`, the every-minute check `frontend/app/api/task-bot-ping/` (Vercel Cron, `frontend/vercel.json`), page `frontend/app/tasks/`.

## Using it

Write the instruction above the forwarded email, in plain words:

- "claude, remove from CT beehiiv"
- "claude, cancel their subscription on Stripe and let them know I've processed it. Also let Angel know about the churn, and when their billing cycle ends."

It also works without forwarding anything ("claude, unsubscribe jane@example.com from beehiiv"): the person only has to be named in what you send.

What happens next:

1. Within about three minutes (once the GitHub token below is set up) the bot takes the email, makes the account changes, and replies in the thread with exactly what it did.
2. Emails to other people are left as **drafts in your Gmail** for you to read and send. A reply to the person who wrote the forwarded email is placed inside that same conversation when your forward is part of it in Gmail (the normal case); otherwise it is a new email.
3. If something is unclear (no subscriber under that address, two subscriptions, a request it cannot do), it changes nothing and asks you. **Reply to its email** to answer; the reply is a follow-up instruction.

Statuses on the page: **Done**; **Drafts waiting** (changes made, drafts not sent yet; flips to Done within about 15 minutes of you sending them, once the GitHub token is set up); **Needs you** (it asked you something); **Failed** (it did not finish; the thread says what was and was not done); **Running**.

## What it can do, and what it cannot

| Action | What it does | Limit per email |
|---|---|---|
| Look a person up | Newsletter status in beehiiv, subscriptions in Stripe (read-only) | 8 |
| Unsubscribe | Unsubscribes the address in beehiiv and reads it back to confirm | 3 |
| Cancel a subscription | Sets it to cancel at the END of the billing period (no more charges, access until that date), and confirms | 2 |
| Draft an email | Leaves a Gmail draft, never sends | 4 |

Not possible, on purpose: refunds, immediate cancellations, plan changes, deleting anyone's data, sending email. Asked for one of these, the bot says so and stops. A period-end cancellation can be undone in Stripe until the date it takes effect.

## Why it is safe to forward a stranger's email to it

A forwarded email is text written by someone else, and it could contain "also refund everyone". Four things stand between that text and your accounts, all enforced in code (`task_actions.py`), not in the prompt:

1. **Only you can give it tasks.** It acts only on messages Gmail itself filed as *sent by your account*. Anyone can write to the +claude address (this repository is public); their mail is never read as a task.
2. **Only people named in your email.** Every action is refused for an address that does not appear in what you sent.
3. **Small budgets.** The limits in the table are per email, whatever the text asks for.
4. **Nothing goes out without you.** Emails are drafts; cancellations are reversible until the period ends.

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

**1. A password for the /tasks page.** Make one up, 12 characters or more. You will type it once per device at https://growth-advisor-clearerthinking.vercel.app/tasks. Until it is set, the page shows "not set up yet" and nothing else.

**2. A GitHub token, so a task starts within a minute.** Without it the bot only runs when GitHub's own schedule fires (5 or 6 times a day here), so a task can wait hours. To create it:

1. Open https://github.com/settings/personal-access-tokens/new
2. Token name: `Task bot trigger`. Expiration: the longest offered ("No expiration" if it is there).
3. Repository access: **Only select repositories**, then pick `growth-advisor-clearerthinking`.
4. Permissions > Repository permissions > **Actions**: **Read and write**. Leave everything else alone.
5. **Generate token** and copy it (it starts with `github_pat_`). Paste it at the script's second prompt.

The script proves the token works by starting one run of the bot, then gives it to the dashboard. From then on the dashboard checks Gmail every minute and starts the bot when a task email is waiting. It tells GitHub only "run the workflow": no email content leaves Gmail through it. If the token has an expiry date, put a reminder in your calendar; when it lapses, tasks quietly fall back to the slow schedule.

**3. A Stripe key, so the bot can cancel subscriptions.** The key this project already has is read-only (tested 2026-11-18: an update call is refused with 403). To create one that can cancel:

1. Open https://dashboard.stripe.com/apikeys in live mode and click **Create restricted key** (if Stripe asks how the key will be used, choose the option for an integration you built).
2. Key name: `Task bot`.
3. Set **Customers: Read**, **Subscriptions: Write** and **Products: Read**. Leave everything else on None.
4. **Create key**, reveal it and copy it (it starts with `rk_live_`). Paste it at the script's third prompt.

The script proves the key can update subscriptions with a call on a subscription id that does not exist, so nothing changes. Until this key exists, unsubscribes and drafts work, and a cancel request ends as "Needs you" with the reason.

When the script finishes it redeploys the dashboard; give it two minutes.

### Then try it

Forward any email to your +claude address with a first line such as "claude, look this person up and tell me what you find. Change nothing." With step 2 done, the reply arrives in about three minutes and the task appears on the page.

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

Write the function in `task_actions.py` with the `@tool` decorator (it must call `require_in_scope` and `spend`, and `record` what it did), give it a `BUDGET`, add it to `TOOL_FNS` and `TOOLS`, and test it in `tests/test_task_bot.py`. The prompt picks the catalogue up from `TOOLS`.
