"""FastAPI application for Job Radar — serves the React dashboard."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from job_radar.api.routers import jobs, sources, refresh, notes, applications, blocklist, onboarding
from job_radar.db.client import init_db

app = FastAPI(title="Job Radar API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8766",
        "http://127.0.0.1:8766",
        "tauri://localhost",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(refresh.router, prefix="/api")
app.include_router(notes.router, prefix="/api")
app.include_router(applications.router, prefix="/api")
app.include_router(blocklist.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")

# Serve the built React frontend from frontend/dist if it exists
_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"

@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "app": "job-radar",
        "version": app.version,
    }

if (_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

if (_DIST / "index.html").exists():
    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        index = _DIST / "index.html"
        return FileResponse(index)
