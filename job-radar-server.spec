# PyInstaller spec for the Job Radar server sidecar.
#
# Produces: dist/job-radar-server/job-radar-server
# The Tauri build copies this binary into the .app bundle.
#
# Build with:
#   .venv/bin/pyinstaller job-radar-server.spec

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("job_radar")

a = Analysis(
    ["job_radar/cli.py"],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "job_radar",
        "job_radar.app",
        "job_radar.app.server",
        "job_radar.app.macos",
        "job_radar.app.state",
        "job_radar.config",
        "job_radar.config.settings",
        "job_radar.config.env_file",
        "job_radar.db",
        "job_radar.db.client",
        "job_radar.ingestion",
        "job_radar.ingestion.runner",
        "job_radar.ingestion.source_detection",
        "job_radar.ingestion.source_store",
        "job_radar.ingestion.store",
        "job_radar.ingestion.sources",
        "job_radar.ingestion.sources.greenhouse",
        "job_radar.ingestion.sources.lever",
        "job_radar.ingestion.sources.workable",
        "job_radar.ingestion.sources.smartrecruiters",
        "job_radar.ingestion.sources.ashby",
        "job_radar.ingestion.sources.personio",
        "job_radar.scoring",
        "job_radar.scoring.deterministic",
        "job_radar.scoring.rubric",
        "job_radar.scoring.store",
        "job_radar.source_packs",
        "job_radar.source_packs.loader",
        "pydantic",
        "pydantic_settings",
        "bs4",
        "yaml",
        "requests",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="job-radar-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="job-radar-server",
)
