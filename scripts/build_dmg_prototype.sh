#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$HOME/Applications/Job Radar.app"
DIST="$ROOT/dist"
DMG="$DIST/Job Radar Prototype.dmg"
VOLUME_ROOT="$DIST/dmg-root"

cd "$ROOT"

if [ ! -x ".venv/bin/job-radar" ]; then
  echo "Job Radar is not installed in .venv. Run Install Job Radar.command first."
  exit 1
fi

".venv/bin/job-radar" install-app

if [ ! -d "$APP" ]; then
  echo "Expected app bundle was not created: $APP"
  exit 1
fi

rm -rf "$DIST"
mkdir -p "$VOLUME_ROOT"
cp -R "$APP" "$VOLUME_ROOT/"
ln -s /Applications "$VOLUME_ROOT/Applications"

hdiutil create \
  -volname "Job Radar Prototype" \
  -srcfolder "$VOLUME_ROOT" \
  -ov \
  -format UDZO \
  "$DMG"

echo "Wrote $DMG"
