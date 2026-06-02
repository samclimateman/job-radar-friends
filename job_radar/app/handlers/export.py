"""Data export and backup/restore."""

from __future__ import annotations

import csv
import io
import shutil
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
    import json
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


def restore_database(backup_path: str) -> bool:
    source = Path(backup_path).expanduser()
    if not source.exists() or not source.is_file():
        set_state("last_restore_error", f"Backup file not found: {backup_path}")
        return False
    if source.suffix not in {".sqlite", ".db"}:
        set_state("last_restore_error", "Backup must be a .sqlite or .db file")
        return False

    destination = get_settings().db_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    init_db()
    set_state("last_restore_error", "")
    set_state("last_scan_report", None)
    return True
