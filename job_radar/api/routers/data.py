"""Data safety, privacy, and support endpoints for the React app."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from job_radar.app.handlers.export import (
    create_backup_bytes,
    export_jobs_csv,
    export_sources_json,
    restore_database,
)
from job_radar.app.state import get_state
from job_radar.config.settings import get_settings
from job_radar.db.client import execute
from job_radar.notes.store import export_notes_csv, export_notes_json

router = APIRouter(prefix="/data", tags=["data"])


class RestoreRequest(BaseModel):
    backup_path: str


def _download(content: str | bytes, filename: str, media_type: str) -> Response:
    body = content.encode("utf-8") if isinstance(content, str) else content
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/location")
def data_location():
    settings = get_settings()
    return {
        "data_dir": str(settings.data_dir.expanduser()),
        "database_path": str(settings.db_path.expanduser()),
        "database_exists": settings.db_path.exists(),
    }


@router.get("/backup")
def backup_zip():
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    return _download(create_backup_bytes(), f"job-radar-backup-{ts}.zip", "application/zip")


@router.get("/export/jobs.csv")
def export_jobs():
    return _download(export_jobs_csv(), "job-radar-jobs.csv", "text/csv; charset=utf-8")


@router.get("/export/sources.json")
def export_sources():
    return _download(export_sources_json(), "job-radar-sources.json", "application/json")


@router.get("/export/notes.json")
def export_notes_as_json():
    return _download(export_notes_json(), "job-radar-notes.json", "application/json")


@router.get("/export/notes.csv")
def export_notes_as_csv():
    return _download(export_notes_csv(), "job-radar-notes.csv", "text/csv; charset=utf-8")


@router.post("/restore")
def restore(body: RestoreRequest):
    if not restore_database(body.backup_path):
        raise HTTPException(status_code=422, detail=get_state("last_restore_error", "Restore failed"))
    return {"ok": True}


@router.get("/diagnostics")
def diagnostics_bundle():
    settings = get_settings()
    source_health = execute(
        """
        SELECT s.status, s.platform, h.confidence_label, h.error_status,
               h.manual_review_needed, h.likely_broken_url
        FROM sources s
        LEFT JOIN source_health h ON h.source_id = s.id
        """
    )
    runs = execute(
        "SELECT status, started_at, finished_at, sources_attempted, jobs_found, errors "
        "FROM runs ORDER BY started_at DESC LIMIT 5"
    )
    counts = {
        "jobs": execute("SELECT COUNT(*) AS n FROM jobs")[0]["n"],
        "active_jobs": execute("SELECT COUNT(*) AS n FROM jobs WHERE is_live = 1 AND is_excluded = 0")[0]["n"],
        "sources": execute("SELECT COUNT(*) AS n FROM sources")[0]["n"],
        "notes": execute("SELECT COUNT(*) AS n FROM notes WHERE deleted_at IS NULL")[0]["n"],
    }
    diagnostics = {
        "app": "job-radar",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "privacy": {
            "redacted_by_default": True,
            "omits": ["api_keys", "env_values", "job_descriptions", "notes", "applications", "source_urls"],
        },
        "paths": {
            "data_dir": str(settings.data_dir.expanduser()),
            "database_name": settings.db_path.name,
            "database_exists": settings.db_path.exists(),
        },
        "counts": counts,
        "source_health": {
            "total": len(source_health),
            "statuses": _count_by(source_health, "status"),
            "platforms": _count_by(source_health, "platform"),
            "confidence": _count_by(source_health, "confidence_label"),
            "manual_review_needed": sum(1 for row in source_health if row.get("manual_review_needed")),
            "likely_broken_url": sum(1 for row in source_health if row.get("likely_broken_url")),
            "error_statuses": _count_by(source_health, "error_status"),
        },
        "recent_runs": runs,
    }

    return _download(
        json.dumps(diagnostics, indent=2, default=str),
        "job-radar-diagnostics.json",
        "application/json",
    )


def _count_by(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(key) or "unknown"
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts
