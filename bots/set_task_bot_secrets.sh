#!/usr/bin/env bash
# One-time setup of the two secrets the task bot needs that only Igor can supply. Nothing is
# pasted into a chat or printed: both values are typed at a hidden prompt.
#
#   bash bots/set_task_bot_secrets.sh            # both steps
#   bash bots/set_task_bot_secrets.sh page       # only the /tasks page password
#   bash bots/set_task_bot_secrets.sh stripe     # only the Stripe key
#
# Step "page":   asks for a password for https://growth-advisor-clearerthinking.vercel.app/tasks,
#                saves it and the task-log sheet id as Vercel production variables, and pushes an
#                empty commit so Vercel redeploys with them.
# Step "stripe": asks for a Stripe RESTRICTED key (Customers: Read, Subscriptions: Write,
#                Products: Read; see bots/TASK_BOT.md), proves it can update subscriptions with
#                a call on a subscription id that does not exist (so nothing changes), then
#                saves it as the STRIPE_TASKBOT_KEY GitHub secret and in .env.
set -euo pipefail
cd "$(dirname "$0")/.."
STEP="${1:-all}"
VERCEL=(npx --yes vercel@latest)

set_vercel_var() {   # name, value: replace the production variable
  (cd frontend && "${VERCEL[@]}" env rm "$1" production --yes >/dev/null 2>&1 || true)
  (cd frontend && printf %s "$2" | "${VERCEL[@]}" env add "$1" production >/dev/null)
  echo "  saved $1 in Vercel (production)"
}

if [ "$STEP" = "all" ] || [ "$STEP" = "page" ]; then
  echo "== The /tasks page =="
  SHEET_ID=$(grep -E '^TASK_LOG_SHEET_ID=' .env | tail -1 | cut -d= -f2- || true)
  [ -n "$SHEET_ID" ] || { echo "TASK_LOG_SHEET_ID is missing from .env (python task_log.py --create)"; exit 1; }
  while true; do
    read -r -s -p "Choose a password for the page (12+ characters, hidden): " PW; echo
    [ "${#PW}" -ge 12 ] || { echo "  too short, try again"; continue; }
    read -r -s -p "Type it again: " PW2; echo
    [ "$PW" = "$PW2" ] && break
    echo "  they do not match, try again"
  done
  set_vercel_var TASK_LOG_SHEET_ID "$SHEET_ID"
  set_vercel_var TASKS_PAGE_PASSWORD "$PW"
  unset PW PW2
  echo "  redeploying the dashboard so the page picks them up..."
  git pull -q --rebase --autostash origin main
  git commit -q --allow-empty -m "redeploy: /tasks page settings"
  git push -q origin HEAD:main
  echo "  done. In about two minutes: https://growth-advisor-clearerthinking.vercel.app/tasks"
fi

if [ "$STEP" = "all" ] || [ "$STEP" = "stripe" ]; then
  echo "== The Stripe key =="
  read -r -s -p "Paste the restricted key (rk_live_..., hidden): " KEY; echo
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
  unset KEY
  echo "  the key can update subscriptions; saved as the STRIPE_TASKBOT_KEY GitHub secret and in .env"
fi
