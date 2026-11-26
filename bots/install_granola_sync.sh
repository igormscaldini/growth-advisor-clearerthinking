#!/usr/bin/env bash
# Install (or reinstall) the launchd job that copies Granola meeting notes into the advisor's
# encrypted memory (granola_sync.py) on this Mac at 08:30, 12:30, 16:30 and 20:30 local time.
# A run missed while the Mac sleeps fires on wake. Output: .claude/granola_sync.log (gitignored).
#   bash bots/install_granola_sync.sh            install + run once now
#   bash bots/install_granola_sync.sh --remove   stop and uninstall
set -euo pipefail
LABEL="com.clearerthinking.granola-sync"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
if [[ "${1:-}" == "--remove" ]]; then
  rm -f "$PLIST"
  echo "Removed $LABEL."
  exit 0
fi

times=""
for h in 8 12 16 20; do
  times+="<dict><key>Hour</key><integer>$h</integer><key>Minute</key><integer>30</integer></dict>"
done

# macOS decides whether a background job may read ~/Documents from the program launchd starts.
# The venv's python is Apple's small launcher (.../bin/python3.9), which macOS identifies by its
# own path: Full Disk Access granted to "Python" (Python.app) does not cover it, and macOS never
# prompts for Apple's own binaries (checked in the TCC log, 2026-11-26). So start Python.app's
# binary directly and tell it which venv to use, exactly as the launcher itself would.
PY="$REPO/.venv/bin/python"
REAL="$("$PY" -c 'import os, sys; print(os.path.realpath(sys.executable))')"
APP_BIN="$(dirname "$(dirname "$REAL")")/Resources/Python.app/Contents/MacOS/Python"
PROGRAM="$PY"
VENV_ENV=""
if [[ -x "$APP_BIN" ]]; then
  PROGRAM="$APP_BIN"
  VENV_ENV="<key>__PYVENV_LAUNCHER__</key><string>$PY</string>"
fi

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PROGRAM</string>
    <string>$REPO/granola_sync.py</string>
  </array>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    $VENV_ENV
  </dict>
  <key>StartCalendarInterval</key>
  <array>$times</array>
  <key>StandardOutPath</key><string>$REPO/.claude/granola_sync.log</string>
  <key>StandardErrorPath</key><string>$REPO/.claude/granola_sync.log</string>
</dict>
</plist>
EOF
plutil -lint "$PLIST" >/dev/null
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl kickstart "$DOMAIN/$LABEL"
echo "Installed $LABEL and started a first run; follow it with: tail -f \"$REPO/.claude/granola_sync.log\""
