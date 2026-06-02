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
