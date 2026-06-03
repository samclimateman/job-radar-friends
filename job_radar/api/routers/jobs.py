"""Job list, detail, and mutation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from job_radar.db.client import execute

router = APIRouter(tags=["jobs"])

_ACTIVE = (
    "j.is_live = 1 AND j.is_excluded = 0 "
    "AND j.lifecycle_status NOT IN ('probably_closed', 'dead') "
    "AND j.user_status NOT IN ('archived', 'rejected')"
)

_JOB_COLS = """
    j.id, j.title, j.organization, j.location, j.remote_status,
    j.source_url, j.user_status AS application_status, j.lifecycle_status,
    j.is_live, j.is_excluded, j.exclusion_reason,
    j.first_seen_at, j.last_seen_at, j.deadline, j.notes,
    s.id AS source, s.platform,
    COALESCE(js.score, 0) AS strategic_fit_score,
    0 AS geo_score, 0 AS narrative_score, 0 AS policy_score,
    NULL AS role_type, NULL AS org_type
"""

_JOIN = """
    FROM jobs j
    LEFT JOIN job_scores js ON js.job_id = j.id
    LEFT JOIN sources s ON s.id = j.source_id
"""


def _view_clause(view: str) -> tuple[str, str]:
    if view == "new":
        return f"WHERE {_ACTIVE}", "ORDER BY j.first_seen_at DESC"
    if view == "shortlisted":
        return "WHERE j.user_status = 'shortlisted' AND j.is_live = 1", "ORDER BY COALESCE(js.score, 0) DESC"
    if view == "closing":
        return f"WHERE {_ACTIVE} AND j.deadline IS NOT NULL AND j.deadline != ''", "ORDER BY j.deadline ASC"
    if view == "stretch":
        return f"WHERE {_ACTIVE} AND COALESCE(js.score, 0) BETWEEN 35 AND 59", "ORDER BY COALESCE(js.score, 0) DESC"
    if view == "needs_review":
        return "WHERE j.is_excluded = 1 OR js.score IS NULL", "ORDER BY j.first_seen_at DESC"
    if view == "excluded":
        return (
            "WHERE j.is_excluded = 1 OR j.is_live = 0 OR j.lifecycle_status IN ('probably_closed', 'dead')",
            "ORDER BY j.first_seen_at DESC",
        )
    # best (default)
    return f"WHERE {_ACTIVE}", "ORDER BY COALESCE(js.score, 0) DESC, j.first_seen_at DESC"


@router.get("/jobs")
def list_jobs(view: str = "best", limit: int = 200, offset: int = 0):
    where, order = _view_clause(view)
    rows = execute(
        f"SELECT {_JOB_COLS} {_JOIN} {where} {order} LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return rows


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    rows = execute(
        f"""SELECT {_JOB_COLS},
               j.raw_description, j.source_job_id,
               j.last_changed_at, j.times_seen, j.missed_scans,
               j.created_at, j.updated_at,
               js.explanation_json
            {_JOIN}
            WHERE j.id = ?""",
        (job_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Job not found")
    row = rows[0]
    row["classification_data"] = {}
    return row


class StatusUpdate(BaseModel):
    status: str

class NoteUpdate(BaseModel):
    notes: str


@router.patch("/jobs/{job_id}/status")
def update_status(job_id: str, body: StatusUpdate):
    allowed = {"new", "shortlisted", "reviewing", "applied", "submitted",
               "rejected", "archived", "in_progress", "interviewing"}
    if body.status not in allowed:
        raise HTTPException(status_code=422, detail="Invalid status")
    execute("UPDATE jobs SET user_status = ? WHERE id = ?", (body.status, job_id))
    if body.status in ("applied", "submitted", "in_progress", "interviewing"):
        execute(
            """INSERT INTO applications (job_id, status, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(job_id) DO UPDATE SET status = excluded.status,
               updated_at = CURRENT_TIMESTAMP""",
            (job_id, body.status),
        )
    return {"ok": True}


@router.patch("/jobs/{job_id}/note")
def update_note(job_id: str, body: NoteUpdate):
    execute("UPDATE jobs SET notes = ? WHERE id = ?", (body.notes or None, job_id))
    return {"ok": True}
