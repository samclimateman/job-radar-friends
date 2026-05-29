#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Installing Job Radar..."

if [ ! -d ".venv" ]; then
  /usr/bin/python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/job-radar setup
.venv/bin/job-radar install-app

echo ""
echo "Installed: $HOME/Applications/Job Radar.app"
echo "Opening the app now..."
open "$HOME/Applications/Job Radar.app"
