#!/usr/bin/env bash
# Mirrors unstuck/ into the Unstuck GitHub Pages repo and pushes (frontend only goes live this way).
# Live: https://igormscaldini.github.io/unstuck-prototype/   Repo: github.com/igormscaldini/unstuck-prototype
# The source of truth is this folder; edit here, run this, never edit the Pages repo by hand.
# The AI proxy deploys separately: cd unstuck/unstuck-suggest-api && npx vercel --prod
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/Documents/Claude/unstuck-prototype"
[ -d "$DEST/.git" ] || { echo "Pages repo not found at $DEST" >&2; exit 1; }
rsync -a --delete \
  --exclude .git --exclude .env --exclude '.env.*' --exclude .vercel --exclude node_modules \
  --exclude .DS_Store --exclude deploy.sh \
  "$SRC/" "$DEST/"
cd "$DEST"
git add -A
if git diff --cached --quiet; then echo "nothing to deploy"; exit 0; fi
git commit -q -m "Update from Growth Advisor ($(date '+%Y-%m-%d %H:%M'))"
git push -q origin main
echo "pushed to github.com/igormscaldini/unstuck-prototype; Pages rebuilds in about a minute"
