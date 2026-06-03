"""Local HTTP server for Job Radar — routing only."""

from __future__ import annotations

import io
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import parse_qs, urlparse

from job_radar.app.common import _find_free_port, _first, _port_open, _split_urls

# Re-exports for backward compatibility (tests and external callers import from here)
from job_radar.app.handlers.dashboard import (  # noqa: F401
    ANTHROPIC_KEYS_URL,
    OLLAMA_DOWNLOAD_URL,
    OPENAI_KEYS_URL,
    _scan_report_from_result,
    _stats,
    render_dashboard,
    render_rubric_preview,
)
from job_radar.app.handlers.export import export_jobs_csv, export_sources_json, restore_database
from job_radar.app.handlers.jobs import render_job_detail, update_job_status
from job_radar.app.handlers.notes import render_note_detail, render_notebook
from job_radar.app.handlers.source_packs import import_source_pack, render_source_packs
from job_radar.app.handlers.sources import (
    render_source_builder,
    render_source_health_center,
    set_source_status,
    update_source,
    update_source_notes,
)
from job_radar.app.handlers.wizard import render_wizard
from job_radar.app.state import set_state
from job_radar.config.env_file import save_api_env
from job_radar.config.settings import get_settings
from job_radar.db.client import execute, init_db
from job_radar.ingestion.runner import run_ingestion
from job_radar.ingestion.source_store import add_source, mark_manual_checked
from job_radar.scoring.store import save_rubric


def serve(port: int = 8766, open_browser: bool = True) -> None:
    init_db()
    chosen_port = port if not _port_open(port) else _find_free_port(port + 1)
    server = ThreadingHTTPServer(("127.0.0.1", chosen_port), DashboardHandler)
    url = f"http://127.0.0.1:{chosen_port}/"
    print(f"Job Radar dashboard: {url}")
    print("Press Ctrl-C to stop.")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/static/app.css":
            self._send_css()
            return
        if parsed.path == "/static/logo.png":
            self._send_static("logo.png", "image/png")
            return
        if parsed.path == "/job":
            params = parse_qs(parsed.query)
            self._send_html(render_job_detail(_first(params, "job_id") or ""))
            return
        if parsed.path == "/export/jobs.csv":
            self._send_download("jobs.csv", "text/csv; charset=utf-8", export_jobs_csv())
            return
        if parsed.path == "/export/notes.json":
            from job_radar.notes.store import export_notes_json
            self._send_download("notes.json", "application/json; charset=utf-8",
                                export_notes_json().encode())
            return
        if parsed.path == "/export/notes.csv":
            from job_radar.notes.store import export_notes_csv
            self._send_download("notes.csv", "text/csv; charset=utf-8",
                                export_notes_csv().encode())
            return
        if parsed.path == "/export/sources.json":
            self._send_download(
                "sources.json",
                "application/json; charset=utf-8",
                export_sources_json(),
            )
            return
        if parsed.path == "/backup/database":
            import zipfile as _zf

            from job_radar.notes.store import (
                export_notes_csv,
                export_notes_json,
                export_notes_markdown,
            )
            db_path = get_settings().db_path
            init_db()
            execute("PRAGMA wal_checkpoint(TRUNCATE)")
            buf = io.BytesIO()
            with _zf.ZipFile(buf, "w", _zf.ZIP_DEFLATED) as zf:
                zf.writestr("job-radar.sqlite", db_path.read_bytes())
                zf.writestr("notes.json", export_notes_json())
                zf.writestr("notes.csv", export_notes_csv())
                for path, content in export_notes_markdown().items():
                    zf.writestr(path, content)
            self._send_download("job-radar-backup.zip", "application/zip", buf.getvalue())
            return
        if parsed.path == "/wizard":
            params = parse_qs(parsed.query)
            imported = int(_first(params, "imported") or 0)
            pack_name = _first(params, "pack") or ""
            self._send_html(render_wizard(imported=imported, pack_name=pack_name))
            return
        if parsed.path == "/source-packs":
            self._send_html(render_source_packs())
            return
        if parsed.path == "/source-health":
            self._send_html(render_source_health_center())
            return
        if parsed.path == "/source-builder":
            self._send_html(render_source_builder())
            return
        if parsed.path == "/notebook":
            params = parse_qs(parsed.query)
            self._send_html(render_notebook(
                filter_type=_first(params, "type") or "",
                flash=_first(params, "flash") or "",
            ))
            return
        if parsed.path == "/notebook/note":
            params = parse_qs(parsed.query)
            self._send_html(render_note_detail(_first(params, "note_id") or ""))
            return
        if parsed.path == "/rubric/preview":
            self._send_html(render_rubric_preview("", "", ""))
            return

        params = parse_qs(parsed.query)
        self._send_html(render_dashboard(
            view=_first(params, "view") or "best",
            q=_first(params, "q") or "",
        ))

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        form = parse_qs(body)

        if self.path == "/sources/add":
            organization = _first(form, "organization") or None
            for url in _split_urls(_first(form, "urls")):
                add_source(url, organization=organization)
            self._redirect("/")
            return

        if self.path == "/sources/preview":
            self._send_html(render_dashboard(
                preview_urls=_split_urls(_first(form, "urls")),
                preview_org=_first(form, "organization") or "",
            ))
            return

        if self.path == "/ingest":
            result = run_ingestion()
            set_state("last_scan_report", _scan_report_from_result(result))
            self._redirect("/")
            return

        if self.path == "/backup/restore":
            backup_path = _first(form, "backup_path")
            if backup_path:
                restore_database(backup_path)
            self._redirect("/")
            return

        if self.path == "/sources/retry":
            source_id = _first(form, "source_id")
            if source_id:
                run_ingestion(source_id=source_id)
            self._redirect("/#sources")
            return

        if self.path == "/sources/manual-check":
            source_id = _first(form, "source_id")
            if source_id:
                mark_manual_checked(source_id)
            self._redirect("/#sources")
            return

        if self.path == "/sources/edit":
            source_id = _first(form, "source_id")
            url = _first(form, "url")
            organization = _first(form, "organization")
            if source_id and url:
                update_source(source_id, url, organization)
            self._redirect("/source-health")
            return

        if self.path == "/sources/disable":
            source_id = _first(form, "source_id")
            if source_id:
                set_source_status(source_id, "disabled")
            self._redirect("/source-health")
            return

        if self.path == "/sources/enable":
            source_id = _first(form, "source_id")
            if source_id:
                set_source_status(source_id, "active")
            self._redirect("/source-health")
            return

        if self.path == "/strategy/save":
            save_rubric(
                strategy_narrative=_first(form, "strategy_narrative") or "",
                target_locations=_first(form, "target_locations") or "",
                preferred_industries=_first(form, "preferred_industries") or "",
                role_types=_first(form, "role_types") or "",
                seniority=_first(form, "seniority") or "",
                positive_keywords=_first(form, "positive_keywords") or "",
                negative_keywords=_first(form, "negative_keywords") or "",
                dealbreakers=_first(form, "dealbreakers") or "",
            )
            self._redirect("/#strategy")
            return

        if self.path == "/onboarding/complete":
            set_state("onboarding_complete", True)
            self._redirect("/")
            return

        if self.path == "/source-builder/test":
            url = _first(form, "url") or ""
            organization = _first(form, "organization") or None
            self._send_html(render_source_builder(test_url=url.strip(), organization=organization))
            return

        if self.path == "/source-builder/save":
            url = _first(form, "url") or ""
            organization = _first(form, "organization") or None
            manual = _first(form, "manual") == "1"
            if url.strip():
                source = add_source(url.strip(), organization=organization)
                if manual:
                    from job_radar.ingestion.source_store import set_source_needs_review
                    set_source_needs_review(source.id)
            self._redirect("/source-health")
            return

        if self.path == "/source-packs/import":
            pack_id = _first(form, "pack_id")
            selected_urls = set(form.get("source_url", []))
            redirect_to = _first(form, "redirect_to") or ""
            count, pack_name = 0, ""
            if pack_id:
                count, pack_name = import_source_pack(pack_id, selected_urls or None)
            if redirect_to == "wizard":
                from urllib.parse import quote
                self._redirect(f"/wizard?imported={count}&pack={quote(pack_name)}")
            else:
                self._redirect("/#sources")
            return

        if self.path == "/jobs/status":
            job_id = _first(form, "job_id")
            status = _first(form, "status")
            if job_id and status:
                update_job_status(job_id, status)
            self._redirect("/#ranked")
            return

        if self.path == "/sources/notes":
            source_id = _first(form, "source_id")
            notes = _first(form, "notes") or ""
            if source_id:
                update_source_notes(source_id, notes)
            self._redirect("/source-health")
            return

        if self.path == "/api/save":
            save_api_env({
                "LLM_PROVIDER": _first(form, "llm_provider") or "",
                "OPENAI_API_KEY": _first(form, "openai_api_key") or "",
                "ANTHROPIC_API_KEY": _first(form, "anthropic_api_key") or "",
                "OLLAMA_BASE_URL": _first(form, "ollama_base_url") or "",
            })
            self._redirect("/#setup")
            return

        if self.path == "/notes/create":
            from job_radar.notes.store import create_note
            body_text = _first(form, "body") or ""
            title = _first(form, "title") or None
            note_type = _first(form, "note_type") or "general"
            tags_raw = _first(form, "tags") or ""
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
            pinned = _first(form, "pinned") == "1"
            try:
                create_note(body=body_text, title=title, note_type=note_type, tags=tags, pinned=pinned)
                self._redirect("/notebook?flash=created")
            except ValueError:
                self._redirect("/notebook")
            return

        if self.path == "/notes/update":
            from job_radar.notes.store import update_note
            note_id = _first(form, "note_id") or ""
            if note_id:
                tags_raw = _first(form, "tags") or ""
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                update_note(
                    note_id,
                    title=_first(form, "title") or None,
                    body_markdown=_first(form, "body") or "",
                    note_type=_first(form, "note_type") or "general",
                    tags=tags,
                    pinned=_first(form, "pinned") == "1",
                )
            self._redirect(f"/notebook/note?note_id={note_id}")
            return

        if self.path == "/notes/archive":
            from job_radar.notes.store import archive_note
            note_id = _first(form, "note_id") or ""
            if note_id:
                archive_note(note_id)
            self._redirect("/notebook")
            return

        if self.path == "/rubric/preview":
            title = _first(form, "title") or ""
            description = _first(form, "description") or ""
            location = _first(form, "location") or ""
            self._send_html(render_rubric_preview(title, description, location))
            return

        if self.path == "/notes/delete":
            from job_radar.notes.store import soft_delete_note
            note_id = _first(form, "note_id") or ""
            if note_id:
                soft_delete_note(note_id)
            self._redirect("/notebook")
            return

        self.send_error(404)

    def log_message(self, format: str, *args) -> None:
        return

    def _send_html(self, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_css(self) -> None:
        payload = files("job_radar.ui.static").joinpath("app.css").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/css; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_static(self, filename: str, content_type: str) -> None:
        payload = files("job_radar.ui.static").joinpath(filename).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_download(self, filename: str, content_type: str, payload: str | bytes) -> None:
        if isinstance(payload, str):
            body = payload.encode("utf-8")
        else:
            body = payload
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()
