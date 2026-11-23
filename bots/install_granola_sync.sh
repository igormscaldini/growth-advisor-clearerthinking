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

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$REPO/.venv/bin/python</string>
    <string>$REPO/granola_sync.py</string>
  </array>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
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
