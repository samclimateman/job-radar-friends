"""Stats, radar, and source health endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from job_radar.db.client import execute
from job_radar.ingestion.runner import run_ingestion
from job_radar.ingestion.source_detection import SourceUrlError, detect_source, normalize_source_url
from job_radar.ingestion.source_store import mark_manual_checked

router = APIRouter(tags=["sources"])

_ACTIVE = (
    "j.is_live = 1 AND j.is_excluded = 0 "
    "AND j.lifecycle_status NOT IN ('probably_closed', 'dead') "
    "AND j.user_status NOT IN ('archived', 'rejected')"
)


@router.get("/stats")
def get_stats():
    jobs = execute("SELECT COUNT(*) AS n FROM jobs WHERE is_live = 1 AND is_excluded = 0")[0]["n"]
    sources = execute("SELECT COUNT(*) AS n FROM sources WHERE status != 'disabled'")[0]["n"]
    issues = execute(
        """SELECT COUNT(*) AS n
           FROM sources s
           LEFT JOIN source_health h ON h.source_id = s.id
           WHERE s.status = 'needs_review'
              OR h.error_status IS NOT NULL
              OR h.manual_review_needed = 1
              OR h.likely_broken_url = 1"""
    )[0]["n"]
    last_run = execute(
        "SELECT finished_at FROM runs WHERE status = 'success' ORDER BY finished_at DESC LIMIT 1"
    )
    return {
        "jobs": jobs,
        "sources": sources,
        "issues": issues,
        "last_refresh": last_run[0]["finished_at"] if last_run else None,
    }


@router.get("/radar")
def get_radar():
    new_jobs = execute(
        """SELECT j.id, j.title, j.organization, j.location, j.source_url,
               j.first_seen_at, COALESCE(js.score, 0) AS strategic_fit_score,
               j.last_seen_at
            FROM jobs j LEFT JOIN job_scores js ON js.job_id = j.id
            WHERE j.lifecycle_status = 'new'
              AND j.user_status NOT IN ('archived', 'rejected')
            ORDER BY j.first_seen_at DESC LIMIT 10"""
    )
    reappeared = execute(
        """SELECT j.id, j.title, j.organization, j.location, j.source_url,
               j.first_seen_at, COALESCE(js.score, 0) AS strategic_fit_score,
               j.last_seen_at
            FROM jobs j LEFT JOIN job_scores js ON js.job_id = j.id
            WHERE j.lifecycle_status = 'reappeared'
              AND j.user_status NOT IN ('archived', 'rejected')
            ORDER BY j.last_seen_at DESC LIMIT 5"""
    )
    changed = execute(
        """SELECT j.id, j.title, j.organization, j.location, j.source_url,
               j.first_seen_at, COALESCE(js.score, 0) AS strategic_fit_score,
               j.last_seen_at
            FROM jobs j LEFT JOIN job_scores js ON js.job_id = j.id
            WHERE j.lifecycle_status = 'changed'
              AND j.user_status NOT IN ('archived', 'rejected')
            ORDER BY j.last_changed_at DESC LIMIT 5"""
    )
    return {"new": new_jobs, "reappeared": reappeared, "changed": changed}


@router.get("/sources/health")
def get_source_health():
    sources = execute(
        """SELECT s.id, s.url, s.organization, s.notes, s.platform, s.parser_type, s.status,
               h.last_checked_at, h.last_successful_at, h.jobs_found, h.new_jobs_found,
               h.error_status, h.manual_review_needed, h.likely_broken_url,
               h.confidence_label, h.confidence_score, h.confidence_note
            FROM sources s
            LEFT JOIN source_health h ON h.source_id = s.id
            ORDER BY s.created_at, s.url"""
    )
    if not sources:
        return None

    last_run = execute(
        "SELECT started_at, finished_at FROM runs ORDER BY started_at DESC LIMIT 1"
    )
    generated_at = last_run[0]["finished_at"] if last_run else None
    succeeded = sum(
        1 for r in sources
        if r["status"] == "active" and not r.get("error_status") and r.get("last_successful_at")
    )
    failed = sum(1 for r in sources if r.get("error_status"))

    results = [
        {
            "source_id": r["id"],
            "org_name": r["organization"] or r["url"],
            "url": r["url"],
            "platform": r["platform"] or "",
            "status": r["status"],
            "notes": r.get("notes"),
            "success": r["status"] == "active" and not bool(r.get("error_status")),
            "manual_review_needed": r["status"] == "needs_review" or bool(r.get("manual_review_needed")),
            "likely_broken_url": bool(r.get("likely_broken_url")),
            "jobs_found": r.get("jobs_found") or 0,
            "jobs_new": r.get("new_jobs_found") or 0,
            "jobs_updated": 0,
            "jobs_excluded": 0,
            "skipped": r["status"] == "disabled",
            "error": r.get("error_status"),
            "fetch_ms": 0,
            "total_ms": 0,
            "confidence_label": r.get("confidence_label"),
            "confidence_score": r.get("confidence_score"),
            "confidence_note": r.get("confidence_note"),
        }
        for r in sources
    ]

    return {
        "generated_at": generated_at or "",
        "previous_successful_refresh_at": None,
        "summary": {
            "sources_attempted": len(sources),
            "sources_succeeded": succeeded,
            "sources_failed": failed,
            "total_new": sum(r["jobs_new"] for r in results),
            "total_updated": 0,
            "total_excluded": 0,
            "total_stale": 0,
        },
        "results": results,
    }


class SourceUpdate(BaseModel):
    organization: str | None = None
    url: str
    notes: str | None = None


@router.patch("/sources/{source_id}")
def update_source(source_id: str, body: SourceUpdate):
    rows = execute("SELECT status FROM sources WHERE id = ?", (source_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Source not found")

    try:
        url = normalize_source_url(body.url)
    except SourceUrlError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    duplicate = execute("SELECT id FROM sources WHERE url = ? AND id != ?", (url, source_id))
    if duplicate:
        raise HTTPException(status_code=409, detail="A source with that URL already exists")

    detection = detect_source(url)
    current_status = rows[0]["status"]
    next_status = current_status if current_status == "disabled" else (
        "needs_review" if detection.manual_review_needed else "active"
    )
    execute(
        """
        UPDATE sources
        SET url = ?,
            organization = ?,
            platform = ?,
            parser_type = ?,
            config_json = ?,
            status = ?,
            detection_note = ?,
            notes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            url,
            body.organization.strip() if body.organization else None,
            detection.platform,
            detection.parser_type,
            json.dumps(detection.config),
            next_status,
            detection.note,
            body.notes.strip() if body.notes else None,
            source_id,
        ),
    )
    return {"ok": True}


@router.post("/sources/{source_id}/checked")
def mark_source_checked(source_id: str):
    if not execute("SELECT id FROM sources WHERE id = ?", (source_id,)):
        raise HTTPException(status_code=404, detail="Source not found")
    mark_manual_checked(source_id)
    execute("UPDATE sources SET status = 'active', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (source_id,))
    return {"ok": True}


@router.post("/sources/{source_id}/disable")
def disable_source(source_id: str):
    if not execute("SELECT id FROM sources WHERE id = ?", (source_id,)):
        raise HTTPException(status_code=404, detail="Source not found")
    execute("UPDATE sources SET status = 'disabled', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (source_id,))
    return {"ok": True}


@router.post("/sources/{source_id}/enable")
def enable_source(source_id: str):
    if not execute("SELECT id FROM sources WHERE id = ?", (source_id,)):
        raise HTTPException(status_code=404, detail="Source not found")
    execute("UPDATE sources SET status = 'active', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (source_id,))
    return {"ok": True}


@router.post("/sources/{source_id}/retry")
def retry_source(source_id: str):
    if not execute("SELECT id FROM sources WHERE id = ?", (source_id,)):
        raise HTTPException(status_code=404, detail="Source not found")
    result = run_ingestion(source_id=source_id)
    return {
        "ok": True,
        "sources_succeeded": result.sources_succeeded,
        "sources_failed": result.sources_failed,
        "jobs_found": result.jobs_found,
        "new_jobs_found": result.new_jobs_found,
    }


@router.delete("/sources/{source_id}")
def delete_source(source_id: str):
    if not execute("SELECT id FROM sources WHERE id = ?", (source_id,)):
        raise HTTPException(status_code=404, detail="Source not found")
    job_count = execute("SELECT COUNT(*) AS n FROM jobs WHERE source_id = ?", (source_id,))[0]["n"]
    if job_count:
        raise HTTPException(
            status_code=409,
            detail="This source has jobs. Disable it instead so saved jobs remain inspectable.",
        )
    execute("DELETE FROM job_observations WHERE source_id = ?", (source_id,))
    execute("DELETE FROM source_runs WHERE source_id = ?", (source_id,))
    execute("DELETE FROM source_health WHERE source_id = ?", (source_id,))
    execute("DELETE FROM sources WHERE id = ?", (source_id,))
    return {"ok": True}
