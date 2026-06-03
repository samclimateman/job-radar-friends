"""Command line interface for Job Radar."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from job_radar import __version__
from job_radar.app.handlers.export import write_backup_zip
from job_radar.app.macos import install_app
from job_radar.config.settings import get_settings
from job_radar.db.client import init_db
from job_radar.ingestion.runner import run_ingestion
from job_radar.ingestion.source_detection import detect_source
from job_radar.ingestion.source_store import add_source, list_sources


def cmd_setup(args: argparse.Namespace) -> int:
    db_path = init_db()
    settings = get_settings()
    profile_path = settings.data_dir / "rubric.example.json"
    if not profile_path.exists():
        profile_path.write_text(json.dumps(_example_rubric(), indent=2) + "\n")
    print(f"Job Radar {__version__}")
    print(f"Data directory: {settings.data_dir}")
    print(f"SQLite database: {db_path}")
    print(f"Example rubric: {profile_path}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    settings = get_settings()
    db_path = init_db()
    print("Job Radar doctor")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Data directory exists: {settings.data_dir.exists()}")
    print(f"SQLite database exists: {db_path.exists()}")
    print("Playwright: deferred for v0.1 core loop")
    return 0


def cmd_detect(args: argparse.Namespace) -> int:
    for url in args.urls:
        detection = detect_source(url)
        print(json.dumps({
            "url": url,
            "platform": detection.platform,
            "parser_type": detection.parser_type,
            "note": detection.note,
            "config": detection.config,
            "manual_review_needed": detection.manual_review_needed,
        }, indent=2))
    return 0


def cmd_sources_add(args: argparse.Namespace) -> int:
    init_db()
    for url in args.urls:
        source = add_source(url, organization=args.organization)
        print(f"{source.id}  {source.platform:<18} {source.status:<12} {source.url}")
    return 0


def cmd_sources_list(args: argparse.Namespace) -> int:
    init_db()
    sources = list_sources()
    if not sources:
        print("No sources saved yet.")
        return 0
    for source in sources:
        org = f"  {source.organization}" if source.organization else ""
        print(f"{source.id}  {source.platform:<18} {source.status:<12} {source.url}{org}")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    import threading
    import webbrowser

    import uvicorn

    from job_radar.app.server import serve as serve_html

    init_db()

    # Start the HTML admin server (wizard, source builder, strategy) on port+1
    admin_port = args.port + 1
    admin_thread = threading.Thread(
        target=serve_html,
        kwargs={"port": admin_port, "open_browser": False},
        daemon=True,
    )
    admin_thread.start()

    # Open browser/Tauri webview at the React dashboard
    if not args.no_open:
        threading.Timer(0.8, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()

    # Start FastAPI (blocks until interrupted)
    uvicorn.run(
        "job_radar.api.main:app",
        host="127.0.0.1",
        port=args.port,
        log_level="warning",
        access_log=False,
    )
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    init_db()
    result = run_ingestion(source_id=args.source_id)
    print(f"Run: {result.run_id}")
    print(
        f"Sources: {result.sources_succeeded}/{result.sources_attempted} succeeded; "
        f"{result.sources_failed} failed"
    )
    print(f"Jobs: {result.jobs_found} found; {result.new_jobs_found} new")
    for item in result.results:
        if item.success:
            print(f"  OK    {item.platform:<12} {item.jobs_found:>3} found  {item.url}")
        else:
            print(f"  FAIL  {item.platform:<12} {item.error}  {item.url}")
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    init_db()
    dest = write_backup_zip(Path(args.output) if args.output else None)
    print(f"Backup written: {dest}")
    return 0


def cmd_install_app(args: argparse.Namespace) -> int:
    target = install_app()
    print(f"Installed Job Radar at {target}")
    print("Open it from Finder once, then choose Keep in Dock.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Job Radar local career opportunity tracker")
    parser.add_argument("--version", action="version", version=f"job-radar {__version__}")
    sub = parser.add_subparsers(dest="command")

    setup = sub.add_parser("setup", help="Initialize local app data and SQLite database")
    setup.set_defaults(func=cmd_setup)

    start = sub.add_parser("start", help="Start the local app")
    start.add_argument("--port", type=int, default=8766)
    start.add_argument("--no-open", action="store_true", help="Do not open a browser window")
    start.set_defaults(func=cmd_start)

    ingest = sub.add_parser("ingest", help="Run ingestion")
    ingest.add_argument("--source-id", help="Only ingest one saved source id")
    ingest.set_defaults(func=cmd_ingest)

    doctor = sub.add_parser("doctor", help="Check local runtime")
    doctor.set_defaults(func=cmd_doctor)

    backup = sub.add_parser("backup", help="Create a portable backup zip")
    backup.add_argument("--output", help="Backup file path")
    backup.set_defaults(func=cmd_backup)

    install = sub.add_parser("install-app", help="Install a macOS Dock app wrapper")
    install.set_defaults(func=cmd_install_app)

    detect = sub.add_parser("detect", help="Detect source platforms from URLs")
    detect.add_argument("urls", nargs="+")
    detect.set_defaults(func=cmd_detect)

    sources = sub.add_parser("sources", help="Manage career-page sources")
    source_sub = sources.add_subparsers(dest="sources_command")

    sources_add = source_sub.add_parser("add", help="Add career-page URLs")
    sources_add.add_argument("urls", nargs="+")
    sources_add.add_argument("--organization", "-o", help="Optional organization label")
    sources_add.set_defaults(func=cmd_sources_add)

    sources_list = source_sub.add_parser("list", help="List saved sources")
    sources_list.set_defaults(func=cmd_sources_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


def _example_rubric() -> dict:
    return {
        "target_locations": ["London", "New York", "Remote"],
        "preferred_industries": ["technology", "research", "nonprofit"],
        "role_types": ["analyst", "manager", "coordinator"],
        "seniority": ["senior", "lead", "manager"],
        "positive_keywords": ["strategy", "data", "communications"],
        "negative_keywords": ["sales", "unpaid", "junior admin"],
        "dealbreakers": ["requires security clearance", "no remote"],
        "weights": {
            "location": 0.2,
            "role_type": 0.25,
            "industry": 0.25,
            "seniority": 0.15,
            "keyword_fit": 0.15,
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
