#!/bin/bash
set -e

APP="$HOME/Applications/Job Radar.app"

if [ ! -d "$APP" ]; then
  echo "Job Radar is not installed yet. Run Install Job Radar.command first."
  exit 1
fi

open "$APP"
