#!/usr/bin/env python3
"""Install Job Radar as a macOS app in ~/Applications."""

from pathlib import Path

from job_radar.app.macos import install_app

if __name__ == "__main__":
    path = install_app(project_root=Path(__file__).resolve().parent.parent)
    print(f"Installed Job Radar at {path}")
