# Task bot: email Claude an instruction, it gets done

Forward any email to your Gmail address with `+claude` before the `@` (the same address the script prints on install), and write what you want on the first line. The bot carries it out, replies in the same thread, and logs it at https://growth-advisor-clearerthinking.vercel.app/tasks.

Built 2026-11-18. Code: `task_bot.py` (reads the email, runs the task, reports), `task_actions.py` (the actions and their safety limits), `task_log.py` (the log), workflow `.github/workflows/task-bot.yml`, trigger `bots/task_bot_trigger.gs`, page `frontend/app/tasks/`.

## Using it

Write the instruction above the forwarded email, in plain words:

- "claude, remove from CT beehiiv"
- "claude, cancel their subscription on Stripe and let them know I've processed it. Also let Angel know about the churn, and when their billing cycle ends."

It also works without forwarding anything ("claude, unsubscribe jane@example.com from beehiiv"): the person only has to be named in what you send.

What happens next:

1. Within about three minutes (once the trigger below is installed) the bot takes the email, makes the account changes, and replies in the thread with exactly what it did.
2. Emails to other people are left as **drafts in your Gmail** for you to read and send. A reply to the person who wrote the forwarded email is placed inside that same conversation when your forward is part of it in Gmail (the normal case); otherwise it is a new email.
3. If something is unclear (no subscriber under that address, two subscriptions, a request it cannot do), it changes nothing and asks you. **Reply to its email** to answer; the reply is a follow-up instruction.

Statuses on the page: **Done**; **Drafts waiting** (changes made, drafts not sent yet; flips to Done within about 15 minutes of you sending them, once the trigger is installed); **Needs you** (it asked you something); **Failed** (it did not finish; the thread says what was and was not done); **Running**.

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

## Setup still needed from you (once)

### 1. Page password and Stripe key: one script

```
bash bots/set_task_bot_secrets.sh
```

It asks for two things at hidden prompts:

- **A password for the /tasks page** (12+ characters). Saved in Vercel; the page works about two minutes later. Until then the page shows "not set up yet" and nothing else.
- **A Stripe restricted key.** The key this project already has is read-only (tested 2026-11-18: an update call is refused with 403), so the bot cannot cancel anything until it gets its own. Create it in Stripe: Developers > API keys > Create restricted key, name it "Task bot", and set **Customers: Read**, **Subscriptions: Write**, **Products: Read**, everything else None. The script checks the key can update subscriptions (with a call on an id that does not exist, so nothing changes) before saving it.

Until the Stripe key exists, unsubscribes and drafts work, and a cancel request ends as "Needs you" with the reason.

### 2. The trigger, so tasks start within a minute (about five minutes)

Without it the bot still runs, but only when GitHub's own schedule fires: 5 or 6 times a day on this repository, so a task can wait a few hours.

1. Create a GitHub token: https://github.com/settings/personal-access-tokens/new . Repository access: **Only select repositories** > `growth-advisor-clearerthinking`. Permissions > Repository permissions > **Actions: Read and write**. Nothing else. Copy the token.
2. Open https://script.google.com signed in to the Gmail account you forward from, **New project**, name it "Claude task bot trigger".
3. Replace the contents of `Code.gs` with `bots/task_bot_trigger.gs`.
4. Left sidebar: **Services +** > **Gmail API** > Add.
5. Gear icon (Project Settings) > **Script properties** > Add: name `GITHUB_TOKEN`, value the token from step 1.
6. Back in the editor, pick the function **install** and press Run. Approve the permission screen (for a script you wrote yourself Google shows "Advanced" > "Go to project").
7. Check: pick **testStart** and Run. The log says "GitHub accepted the start." and a new run appears under Actions > Task bot.

The script checks Gmail every minute and tells GitHub only "run the workflow". No email content leaves Gmail through it. The token expires on the date you chose in step 1: put a reminder in your calendar, or tasks quietly fall back to the slow schedule.

## Checking it and fixing it

```
gh run list --workflow task-bot.yml --limit 5     # recent runs
gh workflow run task-bot.yml                      # run now
gh workflow disable task-bot.yml                  # pause (and run `uninstall` in the Apps Script)
python task_bot.py --dry-run                      # locally: read pending tasks, simulate, print; changes nothing
```

- A run that ends red means a task failed or a report could not be sent; you also get GitHub's own email. A task that failed is marked "Failed" and is not retried: forward the email again once the cause is fixed.
- "Not logged in" or "Failed to authenticate" in a report: the Claude token expired, run `bash bots/set_claude_token.sh`.
- A task email that never gets a reply: it was probably not sent from the Gmail account itself (for example from another mailbox). Only mail in that account's Sent folder counts.

## Adding an action

Write the function in `task_actions.py` with the `@tool` decorator (it must call `require_in_scope` and `spend`, and `record` what it did), give it a `BUDGET`, add it to `TOOL_FNS` and `TOOLS`, and test it in `tests/test_task_bot.py`. The prompt picks the catalogue up from `TOOLS`.
