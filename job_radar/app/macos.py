"""macOS application wrapper installer."""

from __future__ import annotations

import shutil
import stat
import subprocess
from importlib.resources import files
from pathlib import Path

APP_NAME = "Job Radar"
BUNDLE_ID = "local.job-radar.app"


def install_app(project_root: Path | None = None, app_path: Path | None = None) -> Path:
    root = project_root or Path.cwd()
    target = app_path or Path.home() / "Applications" / f"{APP_NAME}.app"
    contents_dir = target / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"

    if target.exists():
        shutil.rmtree(target)

    macos_dir.mkdir(parents=True)
    resources_dir.mkdir(parents=True)

    icon_file = _write_icon(resources_dir)
    icon_plist = f"<key>CFBundleIconFile</key><string>{icon_file}</string>" if icon_file else ""

    (contents_dir / "Info.plist").write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key><string>job-radar</string>
  <key>CFBundleIdentifier</key><string>{BUNDLE_ID}</string>
  <key>CFBundleName</key><string>{APP_NAME}</string>
  <key>CFBundleDisplayName</key><string>{APP_NAME}</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  {icon_plist}
  <key>LSMinimumSystemVersion</key><string>12.0</string>
</dict>
</plist>
""")

    executable = macos_dir / "job-radar"
    executable.write_text(f"""#!/bin/bash
PROJECT="{root}"
JOB_RADAR="$PROJECT/.venv/bin/job-radar"
PYTHON="$PROJECT/.venv/bin/python3"
LOG_DIR="$HOME/.job-radar"
LOG_FILE="$LOG_DIR/launcher.log"

mkdir -p "$LOG_DIR"
exec >> "$LOG_FILE" 2>&1

echo ""
echo "[$(date)] Starting Job Radar"

cd "$PROJECT" || {{
    echo "Project folder not found: $PROJECT"
    osascript -e 'display alert "Job Radar could not start" message "The project folder was not found. Check ~/.job-radar/launcher.log for details."'
    exit 1
}}

if [ ! -x "$PYTHON" ]; then
    echo "Creating virtual environment"
    /usr/bin/python3 -m venv "$PROJECT/.venv" || {{
        osascript -e 'display alert "Job Radar setup failed" message "Could not create the Python virtual environment. Check ~/.job-radar/launcher.log for details."'
        exit 1
    }}
fi

if [ ! -x "$JOB_RADAR" ]; then
    echo "Installing Job Radar package"
    "$PYTHON" -m pip install -e "$PROJECT" || {{
        osascript -e 'display alert "Job Radar setup failed" message "Could not install the local package. Check ~/.job-radar/launcher.log for details."'
        exit 1
    }}
fi

if [ -x "$JOB_RADAR" ]; then
    exec "$JOB_RADAR" start
fi

if [ -x "$PYTHON" ]; then
    exec "$PYTHON" -m job_radar.cli start
fi

osascript -e 'display alert "Job Radar could not start" message "No runnable Job Radar command was found. Check ~/.job-radar/launcher.log for details."'
exit 1
""")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return target


def _write_icon(resources_dir: Path) -> str | None:
    source = files("job_radar.ui.static").joinpath("logo.png")
    source_path = resources_dir / "logo.png"
    source_path.write_bytes(source.read_bytes())

    sips = shutil.which("sips")
    iconutil = shutil.which("iconutil")
    if not sips or not iconutil:
        return None

    iconset = resources_dir / "AppIcon.iconset"
    iconset.mkdir(parents=True, exist_ok=True)
    specs = [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512),
        ("icon_512x512@2x.png", 1024),
    ]

    try:
        for filename, size in specs:
            subprocess.run(
                [sips, "-z", str(size), str(size), str(source_path), "--out", str(iconset / filename)],
                check=True,
                capture_output=True,
                text=True,
            )
        icon_path = resources_dir / "AppIcon.icns"
        subprocess.run(
            [iconutil, "-c", "icns", str(iconset), "-o", str(icon_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        shutil.rmtree(iconset)
        return "AppIcon.icns"
    except subprocess.CalledProcessError:
        shutil.rmtree(iconset, ignore_errors=True)
        return None
