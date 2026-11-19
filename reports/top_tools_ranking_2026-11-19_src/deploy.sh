#!/usr/bin/env bash
# Publish the built page to https://igormscaldini.github.io/ct-top-tools/ (public repo igormscaldini/ct-top-tools).
# Refresh first:  fetch_data.py -> cross_check.py -> build_page.py   (all in this folder, run with .venv/bin/python)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CLONE="$HOME/Documents/Claude/ct-top-tools"
cp "$ROOT/reports/top_tools_ranking_2026-11-19.html" "$CLONE/index.html"
cd "$CLONE"
git add index.html
git diff --cached --quiet && { echo "No change to publish."; exit 0; }
git commit -q -m "Update ranking $(date +%Y-%m-%d)"
git push -q origin main
echo "Pushed. Live in about a minute: https://igormscaldini.github.io/ct-top-tools/"
