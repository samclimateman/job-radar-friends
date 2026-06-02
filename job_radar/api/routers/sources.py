"""Stats, radar, and source health endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from job_radar.db.client import execute

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
        """SELECT COUNT(*) AS n FROM source_health
           WHERE error_status IS NOT NULL OR manual_review_needed = 1 OR likely_broken_url = 1"""
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
        f"""SELECT j.id, j.title, j.organization, j.location, j.source_url,
               j.first_seen_at, COALESCE(js.score, 0) AS strategic_fit_score,
               j.last_seen_at
            FROM jobs j LEFT JOIN job_scores js ON js.job_id = j.id
            WHERE j.lifecycle_status = 'new'
              AND j.user_status NOT IN ('archived', 'rejected')
            ORDER BY j.first_seen_at DESC LIMIT 10"""
    )
    reappeared = execute(
        f"""SELECT j.id, j.title, j.organization, j.location, j.source_url,
               j.first_seen_at, COALESCE(js.score, 0) AS strategic_fit_score,
               j.last_seen_at
            FROM jobs j LEFT JOIN job_scores js ON js.job_id = j.id
            WHERE j.lifecycle_status = 'reappeared'
              AND j.user_status NOT IN ('archived', 'rejected')
            ORDER BY j.last_seen_at DESC LIMIT 5"""
    )
    changed = execute(
        f"""SELECT j.id, j.title, j.organization, j.location, j.source_url,
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
        """SELECT s.id, s.url, s.organization, s.platform, s.parser_type, s.status,
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
    succeeded = sum(1 for r in sources if not r.get("error_status") and r.get("last_successful_at"))
    failed = sum(1 for r in sources if r.get("error_status"))

    results = [
        {
            "source_id": r["id"],
            "org_name": r["organization"] or r["url"],
            "platform": r["platform"] or "",
            "success": not bool(r.get("error_status")),
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
