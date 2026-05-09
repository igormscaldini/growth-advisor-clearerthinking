#!/usr/bin/env bash
# Auto-commit and push after every Claude turn.
# .env (and other secrets) are excluded via .gitignore — never staged.
set +e

REPO_DIR="/Users/igorscaldini/Documents/Claude/Growth Advisor - Clearer Thinking"
LOG_FILE="$REPO_DIR/.claude/auto-push.log"

cd "$REPO_DIR" || exit 0

# Bail if not a git repo (shouldn't happen, but be safe)
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

git add -A

# Nothing staged → nothing to do
if git diff --cached --quiet; then
  exit 0
fi

ts=$(date '+%Y-%m-%d %H:%M:%S')
{
  echo "=== $ts ==="
  git commit -m "auto: $ts"
  git push origin main
  echo
} >> "$LOG_FILE" 2>&1

exit 0
