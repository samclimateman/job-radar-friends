"""Data export and backup/restore."""

from __future__ import annotations

import csv
import io
import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from job_radar.app.state import set_state
from job_radar.config.settings import get_settings
from job_radar.db.client import execute, init_db


def export_jobs_csv() -> str:
    rows = execute(
        """
        SELECT j.title, j.organization, j.location, j.user_status, j.is_live,
               j.is_excluded, j.exclusion_reason, j.source_url, s.platform,
               js.score, js.explanation_json
        FROM jobs j
        LEFT JOIN sources s ON s.id = j.source_id
        LEFT JOIN job_scores js ON js.job_id = j.id
        ORDER BY COALESCE(js.score, -1) DESC, j.first_seen_at DESC
        """
    )
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=[
        "title", "organization", "location", "user_status", "is_live",
        "is_excluded", "exclusion_reason", "source_url", "platform",
        "score", "explanation_json",
    ])
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def export_sources_json() -> str:
    rows = execute(
        """
        SELECT s.*, h.last_checked_at, h.last_successful_at, h.jobs_found,
               h.new_jobs_found, h.error_status, h.manual_review_needed, h.likely_broken_url
        FROM sources s
        LEFT JOIN source_health h ON h.source_id = s.id
        ORDER BY s.created_at, s.url
        """
    )
    return json.dumps(rows, indent=2)


def create_backup_bytes() -> bytes:
    """Create a portable backup zip containing database and user exports."""
    from job_radar.notes.store import export_notes_csv, export_notes_json, export_notes_markdown

    db_path = get_settings().db_path
    init_db()
    execute("PRAGMA wal_checkpoint(TRUNCATE)")

    metadata = {
        "app": "job-radar",
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "database_file": db_path.name,
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("job-radar.sqlite", db_path.read_bytes())
        zf.writestr("exports/jobs.csv", export_jobs_csv())
        zf.writestr("exports/sources.json", export_sources_json())
        zf.writestr("exports/notes.json", export_notes_json())
        zf.writestr("exports/notes.csv", export_notes_csv())
        for path, content in export_notes_markdown().items():
            zf.writestr(f"exports/{path}", content)
        zf.writestr("metadata.json", json.dumps(metadata, indent=2))
    return buf.getvalue()


def write_backup_zip(output_path: Path | None = None) -> Path:
    """Write a portable backup zip and return its path."""
    if output_path is None:
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
        output_path = Path.cwd() / f"job-radar-backup-{ts}.zip"
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(create_backup_bytes())
    return output_path


_REQUIRED_TABLES = {"sources", "runs", "jobs", "source_health", "notes"}


def restore_database(backup_path: str) -> bool:
    source = Path(backup_path).expanduser()
    if not source.exists() or not source.is_file():
        set_state("last_restore_error", f"Backup file not found: {backup_path}")
        return False

    destination = get_settings().db_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="job-radar-restore-", suffix=".sqlite", delete=False) as tmp:
        staged = Path(tmp.name)

    if source.suffix == ".zip":
        try:
            with zipfile.ZipFile(source) as zf:
                names = set(zf.namelist())
                if "job-radar.sqlite" not in names:
                    staged.unlink(missing_ok=True)
                    set_state("last_restore_error", "Backup ZIP does not contain job-radar.sqlite")
                    return False
                info = zf.getinfo("job-radar.sqlite")
                if info.file_size <= 0:
                    staged.unlink(missing_ok=True)
                    set_state("last_restore_error", "Backup ZIP contains an empty database")
                    return False
                with zf.open(info) as db_file, staged.open("wb") as out:
                    shutil.copyfileobj(db_file, out)
        except zipfile.BadZipFile:
            staged.unlink(missing_ok=True)
            set_state("last_restore_error", "Backup ZIP could not be read")
            return False
    elif source.suffix in {".sqlite", ".db"}:
        shutil.copy2(source, staged)
    else:
        staged.unlink(missing_ok=True)
        set_state("last_restore_error", "Backup must be a .zip, .sqlite, or .db file")
        return False

    try:
        _validate_restore_database(staged)
    except ValueError as exc:
        staged.unlink(missing_ok=True)
        _cleanup_sqlite_sidecars(staged)
        set_state("last_restore_error", str(exc))
        return False

    pre_restore_backup = _write_pre_restore_backup()
    _cleanup_sqlite_sidecars(destination)
    staged.replace(destination)
    _cleanup_sqlite_sidecars(staged)
    _cleanup_sqlite_sidecars(destination)
    init_db()
    set_state("last_restore_error", "")
    set_state("last_pre_restore_backup", str(pre_restore_backup) if pre_restore_backup else "")
    set_state("last_scan_report", None)
    return True


def _validate_restore_database(path: Path) -> None:
    try:
        init_db(path)
        with sqlite3.connect(path) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise ValueError("Restore database failed SQLite integrity check")
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
    except sqlite3.DatabaseError as exc:
        raise ValueError("Restore database could not be read as SQLite") from exc

    missing = sorted(_REQUIRED_TABLES - tables)
    if missing:
        raise ValueError(f"Restore database is missing required table(s): {', '.join(missing)}")


def _write_pre_restore_backup() -> Path | None:
    destination = get_settings().db_path
    if not destination.exists():
        return None
    backup_dir = get_settings().data_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    backup_path = backup_dir / f"pre-restore-{ts}.zip"
    backup_path.write_bytes(create_backup_bytes())
    return backup_path


def _cleanup_sqlite_sidecars(path: Path) -> None:
    for suffix in ("-wal", "-shm"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)
