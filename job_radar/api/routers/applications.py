"""Application tracking endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from job_radar.db.client import execute

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("")
def list_applications():
    return execute(
        """SELECT a.job_id AS id, a.job_id, j.title, j.organization, j.location,
               j.source_url, COALESCE(js.score, 0) AS strategic_fit_score,
               j.user_status AS application_status,
               a.status, a.notes, a.updated_at,
               NULL AS interview_stage, NULL AS outcome, NULL AS outcome_notes,
               NULL AS submitted_at, a.updated_at AS created_at
            FROM applications a
            JOIN jobs j ON j.id = a.job_id
            LEFT JOIN job_scores js ON js.job_id = j.id
            ORDER BY a.updated_at DESC"""
    )


class StageUpdate(BaseModel):
    stage: str | None


class OutcomeUpdate(BaseModel):
    outcome: str
    notes: str | None = None


@router.patch("/{job_id}/stage")
def update_stage(job_id: str, body: StageUpdate):
    execute(
        "UPDATE applications SET notes = ? WHERE job_id = ?",
        (body.stage, job_id),
    )
    return {"ok": True}


@router.patch("/{job_id}/outcome")
def update_outcome(job_id: str, body: OutcomeUpdate):
    execute(
        "UPDATE applications SET notes = ? WHERE job_id = ?",
        (body.notes or body.outcome, job_id),
    )
    return {"ok": True}
