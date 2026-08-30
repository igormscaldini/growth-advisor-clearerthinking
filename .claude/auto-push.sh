#!/usr/bin/env bash
# Auto-commit and push after every Claude turn (called from on-stop.sh).
# .gitignore keeps secrets, personal-data CSVs and large binaries out of the (public) repo.
set +e

REPO_DIR="/Users/igorscaldini/Documents/Claude/Growth Advisor - Clearer Thinking"
LOG_FILE="$REPO_DIR/.claude/auto-push.log"

cd "$REPO_DIR" || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

# Wait (up to 60s) if another git process (e.g. the digest script) holds the index lock.
for _ in $(seq 1 60); do [ -e .git/index.lock ] || break; sleep 1; done

git add -A

# Nothing staged -> nothing to do
if git diff --cached --quiet; then
  exit 0
fi

ts=$(date '+%Y-%m-%d %H:%M:%S')
{
  echo "=== $ts ==="
  git commit -m "auto: $ts"
  # The snapshot cron pushes to main every 30 min, so rebase onto origin before pushing.
  git pull --rebase --autostash origin main
  git push origin main
  echo
} >> "$LOG_FILE" 2>&1

exit 0
