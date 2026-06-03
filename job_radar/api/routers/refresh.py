"""Ingestion trigger endpoints."""

from __future__ import annotations

import threading

from fastapi import APIRouter

router = APIRouter(prefix="/refresh", tags=["refresh"])

_state: dict = {"running": False, "done": False, "error": None, "new_jobs": 0, "failed": 0}
_lock = threading.Lock()


@router.post("/start")
def start_refresh():
    with _lock:
        if _state["running"]:
            return _state
        _state.update(running=True, done=False, error=None, new_jobs=0, failed=0)

    def _run():
        from job_radar.ingestion.runner import run_ingestion
        try:
            result = run_ingestion()
            with _lock:
                _state["new_jobs"] = result.new_jobs_found if hasattr(result, "new_jobs_found") else 0
                _state["failed"] = result.sources_failed if hasattr(result, "sources_failed") else 0
        except Exception as exc:
            with _lock:
                _state["error"] = str(exc)
        finally:
            with _lock:
                _state["running"] = False
                _state["done"] = True

    threading.Thread(target=_run, daemon=True).start()
    return _state


@router.get("/status")
def refresh_status():
    return _state


@router.get("/progress")
def refresh_progress():
    """Per-source progress for the most recent run."""
    from job_radar.db.client import execute

    runs = execute("SELECT id, status, jobs_found FROM runs ORDER BY started_at DESC LIMIT 1")
    if not runs:
        return {"running": False, "done": False, "jobs_found": 0, "sources": []}

    run = runs[0]
    source_rows = execute(
        """
        SELECT sr.source_id, sr.status, sr.jobs_found, sr.new_jobs_found, sr.error,
               s.organization, s.url
        FROM source_runs sr
        JOIN sources s ON sr.source_id = s.id
        WHERE sr.run_id = ?
        ORDER BY sr.started_at
        """,
        (run["id"],),
    )
    started_ids = {r["source_id"] for r in source_rows}

    pending = execute(
        "SELECT id, organization, url FROM sources WHERE status = 'active'",
    )
    sources = [
        {
            "source_id": r["source_id"],
            "organization": r["organization"] or r["url"],
            "status": r["status"],
            "jobs_found": r["jobs_found"],
            "new_jobs_found": r["new_jobs_found"],
            "error": r["error"],
        }
        for r in source_rows
    ] + [
        {
            "source_id": s["id"],
            "organization": s["organization"] or s["url"],
            "status": "pending",
            "jobs_found": 0,
            "new_jobs_found": 0,
            "error": None,
        }
        for s in pending
        if s["id"] not in started_ids
    ]

    return {
        "running": run["status"] == "running",
        "done": run["status"] in ("finished", "failed"),
        "jobs_found": run["jobs_found"],
        "sources": sources,
    }
