#!/usr/bin/env bash
# Claude Code Stop / SessionEnd hook for this project:
#   1. auto-commit + push the working tree (Igor's original auto-push behaviour)
#   2. digest this conversation into the advisor's encrypted memory, in the background so
#      the turn isn't blocked (see advisor_conversations.py)
# Hook JSON (session_id, transcript_path, hook_event_name) arrives on stdin.
REPO_DIR="/Users/igorscaldini/Documents/Claude/Growth Advisor - Clearer Thinking"
INPUT="$(cat)"

"$REPO_DIR/.claude/auto-push.sh"

printf '%s' "$INPUT" | nohup "$REPO_DIR/.venv/bin/python" "$REPO_DIR/advisor_conversations.py" --hook \
  >> "$REPO_DIR/.claude/digest.log" 2>&1 &

exit 0
