#!/usr/bin/env bash
# One-time setup of the three things the task bot needs that only Igor can supply. Nothing is
# pasted into a chat or printed: every value is typed or pasted at a hidden prompt, and each
# step can be skipped by pressing Enter and run again later.
#
#   bash bots/set_task_bot_secrets.sh            # all three steps
#   bash bots/set_task_bot_secrets.sh page       # only the /tasks page password
#   bash bots/set_task_bot_secrets.sh trigger    # only the GitHub token (fast start)
#   bash bots/set_task_bot_secrets.sh stripe     # only the Stripe key (cancellations)
#
# page:    a password for https://growth-advisor-clearerthinking.vercel.app/tasks (Vercel variable).
# trigger: a GitHub fine-grained token (this repository only, Actions: Read and write). The
#          dashboard's every-minute check (frontend/app/api/task-bot-ping) uses it to start the
#          bot as soon as a task email arrives. Proven here by starting one run of the workflow.
# stripe:  a Stripe RESTRICTED key (Customers: Read, Subscriptions: Write, Products: Read).
#          Proven here with an update call on a subscription id that does not exist, so nothing
#          changes; saved as the STRIPE_TASKBOT_KEY GitHub secret and in .env.
# How to create the token and the key: bots/TASK_BOT.md.
set -euo pipefail
cd "$(dirname "$0")/.."
STEP="${1:-all}"
REPO="igormscaldini/growth-advisor-clearerthinking"
SITE="growth-advisor-clearerthinking.vercel.app"
VERCEL=(npx --yes vercel@latest)
NEED_REDEPLOY=0

wants() { [ "$STEP" = "all" ] || [ "$STEP" = "$1" ]; }

set_vercel_var() {   # name, value: replace the production variable
  (cd frontend && "${VERCEL[@]}" env rm "$1" production --yes >/dev/null 2>&1 </dev/null || true)
  (cd frontend && printf %s "$2" | "${VERCEL[@]}" env add "$1" production >/dev/null 2>&1) \
    || { echo "  could not save $1 in Vercel. Run 'cd frontend && npx vercel whoami' to check the login."; exit 1; }
  echo "  saved $1 in Vercel (production)"
  NEED_REDEPLOY=1
}

has_vercel_var() { (cd frontend && "${VERCEL[@]}" env ls production 2>/dev/null </dev/null | grep -q "^ *$1 "); }

if wants page; then
  echo; echo "== 1. Password for the /tasks page =="
  SHEET_ID=$(grep -E '^TASK_LOG_SHEET_ID=' .env | tail -1 | cut -d= -f2- || true)
  [ -n "$SHEET_ID" ] || { echo "TASK_LOG_SHEET_ID is missing from .env (python task_log.py --create)"; exit 1; }
  while true; do
    read -r -s -p "Choose a password, 12+ characters (hidden; Enter to skip): " PW; echo
    [ -z "$PW" ] && { echo "  skipped"; break; }
    [ "${#PW}" -ge 12 ] || { echo "  too short, try again"; continue; }
    read -r -s -p "Type it again: " PW2; echo
    [ "$PW" = "$PW2" ] || { echo "  they do not match, try again"; continue; }
    set_vercel_var TASK_LOG_SHEET_ID "$SHEET_ID"
    set_vercel_var TASKS_PAGE_PASSWORD "$PW"
    break
  done
  unset PW PW2
fi

if wants trigger; then
  echo; echo "== 2. GitHub token, so tasks start within a minute =="
  read -r -s -p "Paste the token, github_pat_... (hidden; Enter to skip): " TOKEN; echo
  if [ -z "$TOKEN" ]; then
    echo "  skipped"
  else
    case "$TOKEN" in github_pat_*|ghp_*) ;; *) echo "  that does not look like a GitHub token. Nothing saved."; exit 1;; esac
    CODE=$(printf 'Authorization: Bearer %s\n' "$TOKEN" | curl -s -o /dev/null -w '%{http_code}' -m 30 -X POST \
      -H @- -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28" \
      "https://api.github.com/repos/$REPO/actions/workflows/task-bot.yml/dispatches" -d '{"ref":"main"}' || true)
    if [ "$CODE" != "204" ]; then
      echo "  GitHub refused the token (HTTP $CODE). It needs: Only select repositories > growth-advisor-clearerthinking,"
      echo "  and Repository permissions > Actions: Read and write. Nothing saved."
      exit 1
    fi
    echo "  the token works (it just started one run of the task bot)"
    has_vercel_var CRON_SECRET || set_vercel_var CRON_SECRET "$(openssl rand -hex 32)"
    set_vercel_var TASK_BOT_GITHUB_TOKEN "$TOKEN"
  fi
  unset TOKEN
fi

if wants stripe; then
  echo; echo "== 3. Stripe key, so the bot can cancel subscriptions =="
  read -r -s -p "Paste the restricted key, rk_live_... (hidden; Enter to skip): " KEY; echo
  if [ -z "$KEY" ]; then
    echo "  skipped"
  else
    case "$KEY" in rk_live_*) ;; *) echo "  that is not a live restricted key (it should start with rk_live_). Nothing saved."; exit 1;; esac
    RESULT=$(STRIPE_PROBE_KEY="$KEY" .venv/bin/python - <<'EOF' 2>/dev/null
import os, stripe
stripe.api_key = os.environ["STRIPE_PROBE_KEY"]
problems = []
try:
    stripe.Subscription.modify("sub_taskbot_permission_probe_does_not_exist", cancel_at_period_end=True)
except Exception as e:
    if getattr(e, "http_status", None) != 404:
        problems.append("Subscriptions: Write")
for label, call in (("Customers: Read", lambda: stripe.Customer.list(limit=1)),
                    ("Products: Read", lambda: stripe.Product.list(limit=1))):
    try:
        call()
    except Exception:
        problems.append(label)
print("MISSING " + ", ".join(problems) if problems else "OK")
EOF
)
    if [ "$RESULT" != "OK" ]; then
      echo "  the key does not have what the bot needs (${RESULT:-could not test it}). Nothing saved."
      echo "  Edit the key in Stripe (Developers > API keys) and run: bash bots/set_task_bot_secrets.sh stripe"
      exit 1
    fi
    printf %s "$KEY" | gh secret set STRIPE_TASKBOT_KEY
    # Appended, never rewritten: .env holds every other credential, and the last line for a name wins.
    printf '\n# Task bot: Stripe restricted key that may update subscriptions (bots/TASK_BOT.md)\nSTRIPE_TASKBOT_KEY=%s\n' "$KEY" >> .env
    echo "  the key can update subscriptions; saved as the STRIPE_TASKBOT_KEY GitHub secret and in .env"
  fi
  unset KEY
fi

if [ "$NEED_REDEPLOY" = "1" ]; then
  echo; echo "Redeploying the dashboard so the new settings take effect (one to two minutes)..."
  if (cd frontend && "${VERCEL[@]}" redeploy "$SITE" >/dev/null 2>&1 </dev/null); then
    echo "  done: https://$SITE/tasks"
  else
    # Same effect through git: any push to main makes Vercel build a new deployment.
    git pull -q --rebase --autostash origin main
    git commit -q --allow-empty -m "redeploy: task bot settings"
    git push -q origin HEAD:main
    echo "  started through a push; ready in about two minutes: https://$SITE/tasks"
  fi
fi
echo; echo "Finished."
