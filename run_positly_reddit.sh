#!/bin/zsh
# Runner for the daily Positly Reddit finder (invoked by launchd, Mon-Fri 09:00 local).
# Sends the real email; all output is appended to a log for debugging.
cd "/Users/igorscaldini/Documents/Claude/Growth Advisor - Clearer Thinking" || exit 1
LOG="$HOME/Library/Logs/positly-reddit-finder.log"
echo "===== run $(date '+%Y-%m-%d %H:%M:%S %Z') =====" >> "$LOG"
exec ./.venv/bin/python positly_reddit_recruiter.py >> "$LOG" 2>&1
