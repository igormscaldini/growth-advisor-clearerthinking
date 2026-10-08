#!/usr/bin/env bash
# Mints a long-lived Claude Code token and saves it as the CLAUDE_CODE_OAUTH_TOKEN GitHub secret,
# with no copy-paste: records the `claude setup-token` session, extracts the token from it, tests
# it in an isolated config dir (so the local login cannot mask a bad token), and only then saves it.
# Run from a normal terminal (it opens a browser login): bash bots/set_claude_token.sh
# Tokens last about a year; rerun this when the preflight email says "Failed to authenticate".
set -euo pipefail
cd "$(dirname "$0")/.."

CLAUDE="${CLAUDE_BIN:-$(command -v claude || ls -td ~/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude 2>/dev/null | head -1)}"
[ -x "$CLAUDE" ] || { echo "Claude Code binary not found; set CLAUDE_BIN"; exit 1; }
MODEL="${ADVISOR_MODEL:-claude-opus-5}"

LOG=$(mktemp); CFG=$(mktemp -d)
OLD_COLS=$(stty size 2>/dev/null | awk '{print $2}')
cleanup() { rm -rf "$LOG" "$CFG"; [ -n "$OLD_COLS" ] && stty cols "$OLD_COLS" 2>/dev/null; true; }
trap cleanup EXIT

echo "Step 1/3: log in in the browser window that opens, then come back here."
stty cols 400 2>/dev/null || true   # wide terminal so the token is printed on one line
script -q "$LOG" "$CLAUDE" setup-token
[ -n "$OLD_COLS" ] && stty cols "$OLD_COLS" 2>/dev/null

TOKEN=$(perl -pe 's/\e\[[0-9;?]*[ -\/]*[@-~]//g; s/\e\][^\a]*\a//g; s/\r//g' "$LOG" \
  | grep -oE 'sk-ant-oat[0-9A-Za-z_-]+' | tail -1 || true)
[ -n "$TOKEN" ] || { echo "No token found in the setup-token output."; exit 1; }
echo "Got a token: ${TOKEN:0:14}... (${#TOKEN} characters)"

echo "Step 2/3: testing it with model $MODEL..."
REPLY=$(CLAUDE_CONFIG_DIR="$CFG" CLAUDE_CODE_OAUTH_TOKEN="$TOKEN" \
  "$CLAUDE" -p "Reply with just OK" --model "$MODEL" </dev/null 2>&1 || true)
if ! grep -q "OK" <<<"$REPLY"; then
  echo "The token did not work, so nothing was saved. Claude said:"; echo "$REPLY"; exit 1
fi
echo "Works."

echo "Step 3/3: saving it to GitHub..."
printf %s "$TOKEN" | gh secret set CLAUDE_CODE_OAUTH_TOKEN
echo "Saved. Check it on GitHub with: gh workflow run weekly-advisor-email.yml -f preflight=true"
