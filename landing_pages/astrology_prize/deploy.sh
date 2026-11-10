#!/usr/bin/env bash
# Copies the hosted files of the astrology prize page into its GitHub Pages repo and pushes.
# Live: https://igormscaldini.github.io/astrology-prize/   Repo: github.com/igormscaldini/astrology-prize
# The source of truth stays here; edit here, run this, never edit the Pages repo by hand.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/Documents/Claude/astrology-prize"
FILES=(index.html logic.js ct-logo.svg ct-logo-on-dark.svg og.png)
[ -d "$DEST/.git" ] || { echo "Pages repo not found at $DEST" >&2; exit 1; }
for f in "${FILES[@]}"; do cp "$SRC/$f" "$DEST/$f"; done
cd "$DEST"
git add -A
if git diff --cached --quiet; then echo "nothing to deploy"; exit 0; fi
git commit -q -m "Update from Growth Advisor ($(date '+%Y-%m-%d %H:%M'))"
git push -q origin main
echo "pushed to github.com/igormscaldini/astrology-prize; Pages rebuilds in about a minute"
