#!/usr/bin/env bash
# Switches the Unstuck AI proxy (Vercel project unstuck-suggest-api) to the safeguarded version.
# It changes production, so Igor runs it himself, once, from a terminal:
#
#   bash unstuck/unstuck-suggest-api/rollout.sh             # AI only through GuidedTrack (recommended)
#   bash unstuck/unstuck-suggest-api/rollout.sh --keep-web  # also keep AI in the GitHub Pages prototype
#
# What it does:
#   1. runs the proxy's tests;
#   2. sets UNSTUCK_GT_KEY on Vercel from .env.gt-key next to this script (gitignored; the same
#      value the GuidedTrack service "unstuckSuggest" already sends as X-Unstuck-Key);
#   3. sets or removes UNSTUCK_WEB_TOKEN (the web prototype's token, public in its page source);
#   4. removes the unused ANTHROPIC_API_KEY;
#   5. deploys, then checks the live endpoint with requests that never reach Gemini.
# Safe to run again. The hard ceiling on spend is still the Google Cloud quota (printed at the end).
set -euo pipefail
cd "$(dirname "$0")"

KEEP_WEB=0
[ "${1:-}" = "--keep-web" ] && KEEP_WEB=1
VERCEL="npx -y vercel@51"
BASE=https://unstuck-suggest-api.vercel.app

[ -f .vercel/project.json ] || { echo "Not linked to the Vercel project (.vercel/project.json missing)." >&2; exit 1; }
[ -f .env.gt-key ] || { echo "Missing .env.gt-key (a line UNSTUCK_GT_KEY=...) next to this script." >&2; exit 1; }
GT_KEY=$(sed -n 's/^UNSTUCK_GT_KEY=//p' .env.gt-key)
[ "${#GT_KEY}" -ge 32 ] || { echo "UNSTUCK_GT_KEY in .env.gt-key looks wrong (too short)." >&2; exit 1; }
WEB_TOKEN=$(grep -o "SUGGEST_PROTO_TOKEN = '[^']*'" ../index.html | sed "s/.*'\(.*\)'/\1/")
[ -n "$WEB_TOKEN" ] || { echo "Could not read the web prototype's token from ../index.html." >&2; exit 1; }

echo "1/5 Tests"
npm test --silent >/dev/null || { echo "Tests failed; nothing was changed." >&2; npm test; exit 1; }

echo "2/5 Environment variables (production)"
printf '%s' "$GT_KEY" | $VERCEL env add UNSTUCK_GT_KEY production --force --yes >/dev/null
if [ "$KEEP_WEB" = 1 ]; then
  printf '%s' "$WEB_TOKEN" | $VERCEL env add UNSTUCK_WEB_TOKEN production --force --yes >/dev/null
  echo "    web prototype token: kept"
else
  $VERCEL env rm UNSTUCK_WEB_TOKEN production --yes >/dev/null 2>&1 || true
  echo "    web prototype token: removed (its AI button will say Unauthorized)"
fi
$VERCEL env rm ANTHROPIC_API_KEY production --yes >/dev/null 2>&1 || true

echo "3/5 Deploy"
$VERCEL --prod --yes >/dev/null

echo "4/5 Live checks (none of these reach Gemini)"
status() { curl -s -o /dev/null -w '%{http_code}' -m 30 "$@"; }
FAIL=0
check() { # label, expected, actual
  if [ "$2" = "$3" ]; then echo "    ok   $1 ($3)"; else echo "    FAIL $1: expected $2, got $3"; FAIL=1; fi
}
check "no key is refused" 401 "$(status -X POST "$BASE/api/suggest" -H 'Content-Type: application/json' -d '{"task":"x"}')"
check "GuidedTrack key gets past the door" 400 "$(status -X POST "$BASE/api/suggest" -H 'Content-Type: application/json' -H "X-Unstuck-Key: $GT_KEY" -d '{"task":""}')"
if [ "$KEEP_WEB" = 1 ]; then WEB_EXPECTED=400; else WEB_EXPECTED=401; fi
check "public web token" "$WEB_EXPECTED" "$(status -X POST "$BASE/api/suggest" -H 'Content-Type: application/json' -H "X-Proto-Token: $WEB_TOKEN" -d '{"task":""}')"
check "old Anthropic endpoint is gone" 404 "$(status -X POST "$BASE/api/technique" -H 'Content-Type: application/json' -d '{}')"
[ "$FAIL" = 0 ] || { echo "Some checks failed: see above." >&2; exit 1; }

cat <<'TXT'
5/5 Done. One more step only you can do (the real spending cap, about 5 minutes):
    Google Cloud console > the project that owns GEMINI_API_KEY > IAM & Admin > Quotas:
    filter on "Generative Language API", then lower "Requests per day" (e.g. to 500) and
    "Requests per minute". Also: APIs & Services > Credentials > the key > restrict it to the
    Generative Language API, and Billing > Budgets & alerts > add an alert. A budget alert only
    emails you; the quota is what stops the spending.
    Kill switch at any time: npx -y vercel@51 env add AI_ENABLED production --value 0 --force --yes
    then redeploy with npx -y vercel@51 --prod (or set aiEnabled = 0 in the GuidedTrack program).
TXT
