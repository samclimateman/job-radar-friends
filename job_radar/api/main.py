"""FastAPI application for Job Radar — serves the React dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from job_radar.api.routers import applications, blocklist, jobs, notes, onboarding, refresh, sources
from job_radar.db.client import init_db
from job_radar.security.local_requests import is_trusted_local_request

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


@app.middleware("http")
async def reject_cross_site_mutations(request: Request, call_next):
    allowed_ports = {8766, 8767, 5173}
    trusted = is_trusted_local_request(
        method=request.method,
        origin=request.headers.get("origin"),
        referer=request.headers.get("referer"),
        sec_fetch_site=request.headers.get("sec-fetch-site"),
        allowed_ports=allowed_ports,
    )
    if not trusted:
        return JSONResponse({"detail": "Cross-site requests are not allowed"}, status_code=403)
    return await call_next(request)

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
