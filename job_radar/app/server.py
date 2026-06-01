"""Local HTTP dashboard for Job Radar."""

from __future__ import annotations

import csv
import html
import io
import json
import shutil
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from job_radar.app.state import get_state, set_state
from job_radar.config.env_file import load_api_env, save_api_env
from job_radar.config.settings import get_settings
from job_radar.db.client import execute, init_db
from job_radar.ingestion.runner import run_ingestion
from job_radar.ingestion.source_detection import detect_source
from job_radar.ingestion.source_store import add_source, mark_manual_checked
from job_radar.scoring.store import active_rubric_values, save_rubric
from job_radar.source_packs.loader import get_source_pack, list_source_packs

OPENAI_KEYS_URL = "https://platform.openai.com/api-keys"
ANTHROPIC_KEYS_URL = "https://console.anthropic.com/settings/keys"
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download"


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
        if parsed.path == "/export/sources.json":
            self._send_download(
                "sources.json",
                "application/json; charset=utf-8",
                export_sources_json(),
            )
            return
        if parsed.path == "/backup/database":
            db_path = get_settings().db_path
            init_db()
            execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self._send_download("job-radar.sqlite", "application/octet-stream", db_path.read_bytes())
            return
        if parsed.path == "/wizard":
            self._send_html(render_wizard())
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
        params = parse_qs(parsed.query)
        self._send_html(render_dashboard(view=_first(params, "view") or "best"))

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
            if pack_id:
                import_source_pack(pack_id, selected_urls)
            self._redirect("/#sources")
            return

        if self.path == "/jobs/status":
            job_id = _first(form, "job_id")
            status = _first(form, "status")
            if job_id and status:
                update_job_status(job_id, status)
            self._redirect("/#ranked")
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


def render_dashboard(
    preview_urls: list[str] | None = None,
    preview_org: str = "",
    view: str = "best",
) -> str:
    stats = _stats()
    rubric = active_rubric_values()
    api_env = load_api_env()
    onboarding_complete = bool(get_state("onboarding_complete", False))
    last_scan_report = get_state("last_scan_report", None)
    setup_class = "jr-band setup-needed" if stats["sources"] == 0 or not rubric or not onboarding_complete else "jr-band"
    preview_rows = _source_preview_rows(preview_urls or [], preview_org)
    setup_steps = _setup_steps(stats, rubric)
    strategy_summary = _strategy_summary(rubric)
    scan_report = _scan_report_card(last_scan_report)
    jobs = _dashboard_jobs(view)
    sources = execute(
        """
        SELECT s.id, s.url, s.organization, s.platform, s.parser_type, s.status,
               h.last_checked_at, h.jobs_found, h.new_jobs_found, h.error_status,
               h.manual_review_needed, h.likely_broken_url,
               h.confidence_label, h.confidence_score, h.confidence_note
        FROM sources s
        LEFT JOIN source_health h ON h.source_id = s.id
        ORDER BY s.created_at, s.url
        """
    )

    radar = _radar_section()
    job_rows = "\n".join(_job_row(row) for row in jobs) or _empty_row("No jobs ingested yet.", 11)
    source_rows = "\n".join(_source_row(row) for row in sources) or _empty_row("No sources saved yet.", 9)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Job Radar</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <header class="jr-header">
    <div class="jr-title-wrap">
      <img class="jr-logo" src="/static/logo.png" alt="" width="76" height="76">
      <div>
        <h1>Job Radar</h1>
        <p class="jr-subtitle">Local opportunity monitoring</p>
      </div>
    </div>
    <form method="post" action="/ingest">
      <button class="jr-button jr-button-refresh" type="submit">Refresh Now</button>
    </form>
  </header>

  <nav class="jr-tabs" aria-label="Dashboard views">
    <a class="active" href="#ranked">Ranked Jobs</a>
    <a href="/wizard">Onboarding</a>
    <a href="/source-packs">Source Packs</a>
    <a href="/source-builder">Source Builder</a>
    <a href="/source-health">Source Health</a>
    <a href="#setup">AI Setup</a>
    <a href="#strategy">Strategy</a>
  </nav>

  <section class="jr-meta" aria-label="Run summary">
    <span>{stats["jobs"]} jobs</span>
    <span>{stats["sources"]} sources</span>
    <span>{stats["issues"]} source issue(s)</span>
  </section>

  <main>
    {scan_report}
    {radar}
    <section class="{setup_class}" id="add">
      <div class="jr-band-heading">
        <h2>First-Run Setup</h2>
      </div>
      <div class="jr-steps">{setup_steps}</div>
      <p class="jr-help">Add career-page URLs, save a search strategy, optionally configure AI, then refresh.</p>
      <div class="jr-actions jr-onboarding-actions">
        <a class="jr-small-link" href="/wizard">Open Onboarding Wizard</a>
        <a class="jr-small-link" href="/source-packs">Browse Source Packs</a>
      </div>
      <form method="post" action="/sources/add" class="jr-source-form">
        <label>
          <span>Organization</span>
          <input name="organization" type="text" placeholder="Optional label">
        </label>
        <label class="wide">
          <span>Career page URLs</span>
          <textarea name="urls" rows="4" placeholder="https://jobs.lever.co/example&#10;https://job-boards.greenhouse.io/example"></textarea>
        </label>
        <button class="jr-button secondary" type="submit" formaction="/sources/preview">Preview Sources</button>
        <button class="jr-button" type="submit">Add URLs</button>
      </form>
      {preview_rows}
    </section>

    <section class="jr-band" id="setup">
      <div class="jr-band-heading">
        <h2>AI Setup</h2>
      </div>
      <div class="jr-provider-grid">
        {_provider("OpenAI", "OPENAI_API_KEY", OPENAI_KEYS_URL, "API keys")}
        {_provider("Claude", "ANTHROPIC_API_KEY", ANTHROPIC_KEYS_URL, "Anthropic Console")}
        {_provider("Local", "OLLAMA_BASE_URL", OLLAMA_DOWNLOAD_URL, "Install Ollama")}
      </div>
      <form method="post" action="/api/save" class="jr-api-form">
        <label>
          <span>Provider</span>
          <input name="llm_provider" type="text" value="{_esc(api_env.get("LLM_PROVIDER", ""))}" placeholder="openai, anthropic, or ollama">
        </label>
        <label>
          <span>OpenAI key</span>
          <input name="openai_api_key" type="password" value="{_esc(api_env.get("OPENAI_API_KEY", ""))}" placeholder="sk-...">
        </label>
        <label>
          <span>Claude key</span>
          <input name="anthropic_api_key" type="password" value="{_esc(api_env.get("ANTHROPIC_API_KEY", ""))}" placeholder="sk-ant-...">
        </label>
        <label>
          <span>Ollama URL</span>
          <input name="ollama_base_url" type="text" value="{_esc(api_env.get("OLLAMA_BASE_URL", "http://localhost:11434"))}">
        </label>
        <button class="jr-button" type="submit">Save API Settings</button>
      </form>
    </section>

    <section class="jr-band" id="strategy">
      <div class="jr-band-heading">
        <h2>Strategy</h2>
      </div>
      {strategy_summary}
      <form method="post" action="/strategy/save" class="jr-strategy-grid">
        <label>
          <span>Search narrative</span>
          <textarea name="strategy_narrative" rows="5" placeholder="e.g. Senior research or strategy roles at nonprofits or foundations, preferably remote or in major cities.">{_esc(rubric.get("strategy_narrative", ""))}</textarea>
        </label>
        <label>
          <span>Target locations</span>
          <textarea name="target_locations" rows="5" placeholder="e.g.&#10;London&#10;New York&#10;Remote">{_esc(rubric.get("target_locations", ""))}</textarea>
        </label>
        <label>
          <span>Industries</span>
          <textarea name="preferred_industries" rows="4" placeholder="e.g.&#10;technology&#10;research&#10;nonprofit&#10;consulting">{_esc(rubric.get("preferred_industries", ""))}</textarea>
        </label>
        <label>
          <span>Role types</span>
          <textarea name="role_types" rows="4" placeholder="e.g.&#10;analyst&#10;manager&#10;coordinator&#10;director">{_esc(rubric.get("role_types", ""))}</textarea>
        </label>
        <label>
          <span>Seniority</span>
          <textarea name="seniority" rows="4" placeholder="e.g.&#10;senior&#10;lead&#10;manager&#10;director">{_esc(rubric.get("seniority", ""))}</textarea>
        </label>
        <label>
          <span>Positive keywords</span>
          <textarea name="positive_keywords" rows="4" placeholder="e.g.&#10;strategy&#10;data&#10;communications">{_esc(rubric.get("positive_keywords", ""))}</textarea>
        </label>
        <label>
          <span>Negative keywords</span>
          <textarea name="negative_keywords" rows="4" placeholder="e.g.&#10;sales&#10;unpaid&#10;junior admin">{_esc(rubric.get("negative_keywords", ""))}</textarea>
        </label>
        <label>
          <span>Dealbreakers</span>
          <textarea name="dealbreakers" rows="4" placeholder="e.g.&#10;requires security clearance&#10;no remote&#10;unpaid internship">{_esc(rubric.get("dealbreakers", ""))}</textarea>
        </label>
        <button class="jr-button" type="submit">Save Strategy</button>
      </form>
    </section>

    <section class="jr-band" id="ranked">
      <div class="jr-band-heading">
        <h2>Ranked Jobs</h2>
        <div class="jr-actions">
          <a class="jr-small-link" href="/export/jobs.csv">Export CSV</a>
          <a class="jr-small-link" href="/backup/database">Backup DB</a>
        </div>
      </div>
      <form method="post" action="/backup/restore" class="jr-restore-form">
        <label>
          <span>Restore from backup path</span>
          <input name="backup_path" type="text" placeholder="/Users/you/Downloads/job-radar.sqlite">
        </label>
        <button class="jr-small-button danger" type="submit">Restore DB</button>
      </form>
      <div class="jr-table-wrap">
        {_saved_views(view)}
        {_job_cards(jobs[:6])}
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Organization</th>
              <th>Location</th>
              <th>Status</th>
              <th>Fit</th>
              <th>Why</th>
              <th>Seen</th>
              <th>Platform</th>
              <th>Source</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>{job_rows}</tbody>
        </table>
      </div>
    </section>

    <section class="jr-band" id="sources">
      <div class="jr-band-heading">
        <h2>Source Health</h2>
        <a class="jr-small-link" href="/export/sources.json">Export Sources</a>
      </div>
      <div class="jr-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Source</th>
              <th>Platform</th>
              <th>Parser</th>
              <th>Status</th>
              <th>Last Checked</th>
              <th>Jobs</th>
              <th>New</th>
              <th>Error</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>{source_rows}</tbody>
        </table>
      </div>
    </section>
  </main>
</body>
</html>"""


def render_wizard() -> str:
    stats = _stats()
    rubric = active_rubric_values()
    packs = list_source_packs()
    pack_cards = "".join(
        f"""
        <article class="jr-pack-card">
          <h3>{_esc(pack.name)}</h3>
          <p>{_esc(pack.description)}</p>
          <p class="muted">{len(pack.entries)} sources</p>
          <a class="jr-small-link" href="/source-packs#{_esc(pack.id)}">Review Pack</a>
        </article>
        """
        for pack in packs
    )
    body = f"""
    <section class="jr-band detail">
      <div class="jr-band-heading">
        <h2>Onboarding Wizard</h2>
        <a class="jr-small-link" href="/">Back to Dashboard</a>
      </div>
      <div class="jr-steps">
        {_wizard_step("Choose sources", stats["sources"] > 0, f"{stats['sources']} saved")}
        {_wizard_step("Define strategy", bool(rubric), "rubric saved" if rubric else "needed")}
        {_wizard_step("First scan", stats["jobs"] > 0, f"{stats['jobs']} jobs")}
      </div>
      <section class="jr-wizard-section">
        <h3>1. Choose An Ecosystem</h3>
        <div class="jr-pack-grid">{pack_cards}</div>
      </section>
      <section class="jr-wizard-section">
        <h3>2. Add Custom URLs</h3>
        <form method="post" action="/sources/add" class="jr-source-form">
          <label>
            <span>Organization</span>
            <input name="organization" type="text" placeholder="Optional label">
          </label>
          <label class="wide">
            <span>Career page URLs</span>
            <textarea name="urls" rows="4" placeholder="Paste one URL per line"></textarea>
          </label>
          <button class="jr-button" type="submit">Add URLs</button>
        </form>
      </section>
      <section class="jr-wizard-section">
        <h3>3. Define Strategy</h3>
        <p class="jr-help">Use the Strategy section on the dashboard for the full rubric editor.</p>
        <a class="jr-small-link" href="/#strategy">Open Strategy Editor</a>
      </section>
      <section class="jr-wizard-section">
        <h3>4. First Scan</h3>
        <form method="post" action="/ingest">
          <button class="jr-button jr-button-refresh" type="submit">Run First Scan</button>
        </form>
      </section>
      <form method="post" action="/onboarding/complete">
        <button class="jr-button" type="submit">Mark Onboarding Complete</button>
      </form>
    </section>
    """
    return _page("Onboarding", body)


def render_source_builder(
    test_url: str = "",
    organization: str | None = None,
) -> str:
    result_html = ""
    if test_url:
        result_html = _source_builder_result(test_url, organization)

    body = f"""
    <section class="jr-band detail">
      <div class="jr-band-heading">
        <h2>Source Builder</h2>
        <a class="jr-small-link" href="/">Back to Dashboard</a>
      </div>
      <p class="jr-help">
        Paste any career-page or feed URL to test whether Job Radar can extract jobs from it.
        No Python editing required.
      </p>
      <form method="post" action="/source-builder/test" class="jr-source-form">
        <label>
          <span>Organization name</span>
          <input name="organization" type="text" value="{_esc(organization or "")}" placeholder="e.g. Acme Foundation">
        </label>
        <label class="wide">
          <span>Career page or feed URL</span>
          <input name="url" type="url" value="{_esc(test_url)}" placeholder="https://example.org/jobs or https://example.org/feed.xml" required>
        </label>
        <button class="jr-button" type="submit">Test URL</button>
      </form>
      {result_html}
    </section>
    """
    return _page("Source Builder", body)


def _source_builder_result(url: str, organization: str | None) -> str:
    from job_radar.ingestion.runner import SCRAPERS

    detection = detect_source(url)
    scraper_cls = SCRAPERS.get(detection.platform)
    reliability = _platform_reliability(detection.platform, detection.parser_type)
    manual = detection.manual_review_needed or scraper_cls is None

    sample_rows = ""
    warning = ""
    jobs_found = 0
    suggested_action = "Save as active source"

    if not manual and scraper_cls is not None:
        try:
            scraper = scraper_cls()
            jobs = scraper.fetch(organization=organization, **detection.config)
            jobs_found = len(jobs)
            if jobs:
                for job in jobs[:5]:
                    sample_rows += f"""
                    <tr>
                      <td>{_esc(job.title)}</td>
                      <td>{_esc(job.organization or organization or "")}</td>
                      <td>{_esc(job.location or "")}</td>
                      <td><a class="jr-link" href="{_esc(job.source_url)}" target="_blank" rel="noreferrer">Open</a></td>
                    </tr>
                    """
            else:
                warning = "Extraction succeeded but returned 0 jobs. The page may be empty or require filters."
                suggested_action = "Save as active source — check again after next scan"
        except Exception as exc:
            warning = f"Extraction failed: {exc}"
            manual = True
            suggested_action = "Save as manual-watch — automation could not extract jobs"
    else:
        suggested_action = "Save as manual-watch — no automated connector available"
        if detection.note:
            warning = detection.note

    sample_table = f"""
    <div class="jr-table-wrap">
      <table>
        <thead><tr><th>Title</th><th>Organization</th><th>Location</th><th>Link</th></tr></thead>
        <tbody>{sample_rows or _empty_row("No jobs extracted.", 4)}</tbody>
      </table>
    </div>
    """ if not manual else ""

    warning_html = f'<p class="jr-help" style="color:#b45309">{_esc(warning)}</p>' if warning else ""

    return f"""
    <section class="jr-band">
      <div class="jr-band-heading">
        <h2>Test Result</h2>
        <span class="pill {'green' if not manual else 'amber'}">{_esc(reliability)}</span>
      </div>
      <dl class="jr-metadata">
        <dt>URL</dt><dd>{_esc(url)}</dd>
        <dt>Platform</dt><dd>{_esc(detection.platform)}</dd>
        <dt>Connector</dt><dd>{_esc(detection.parser_type)}</dd>
        <dt>Jobs found</dt><dd>{jobs_found}</dd>
        <dt>Suggested action</dt><dd>{_esc(suggested_action)}</dd>
      </dl>
      {warning_html}
      {sample_table}
      <div class="jr-actions" style="margin-top:1rem">
        <form method="post" action="/source-builder/save">
          <input type="hidden" name="url" value="{_esc(url)}">
          <input type="hidden" name="organization" value="{_esc(organization or "")}">
          <input type="hidden" name="manual" value="0">
          <button class="jr-button" type="submit">Save as Active Source</button>
        </form>
        <form method="post" action="/source-builder/save">
          <input type="hidden" name="url" value="{_esc(url)}">
          <input type="hidden" name="organization" value="{_esc(organization or "")}">
          <input type="hidden" name="manual" value="1">
          <button class="jr-button secondary" type="submit">Save as Manual Watch</button>
        </form>
      </div>
    </section>
    """


def render_source_packs() -> str:
    packs = list_source_packs()
    sections = []
    for pack in packs:
        rows = []
        for entry in pack.entries:
            detection = detect_source(entry.url)
            tags = ", ".join(entry.tags)
            rows.append(f"""
            <tr>
              <td>
                <label class="jr-check-row">
                  <input type="checkbox" name="source_url" value="{_esc(entry.url)}" checked>
                  <span><strong>{_esc(entry.organization)}</strong><br><span class="muted">{_esc(entry.url)}</span></span>
                </label>
              </td>
              <td>{_esc(entry.region)}</td>
              <td>{_esc(detection.platform)}</td>
              <td>{_esc(entry.confidence)}</td>
              <td class="muted">{_esc(tags)}</td>
            </tr>
            """)
        sections.append(f"""
        <section class="jr-band" id="{_esc(pack.id)}">
          <div class="jr-band-heading">
            <div>
              <h2>{_esc(pack.name)}</h2>
              <p class="jr-help">{_esc(pack.description)}</p>
            </div>
          </div>
          <form method="post" action="/source-packs/import">
            <input type="hidden" name="pack_id" value="{_esc(pack.id)}">
            <div class="jr-table-wrap">
              <table>
                <thead><tr><th>Source</th><th>Region</th><th>Detected</th><th>Confidence</th><th>Tags</th></tr></thead>
                <tbody>{''.join(rows)}</tbody>
              </table>
            </div>
            <button class="jr-button" type="submit">Import Selected Sources</button>
          </form>
        </section>
        """)
    return _page("Source Packs", "".join(sections) or '<p class="jr-help">No source packs bundled yet.</p>')


def render_source_health_center() -> str:
    sources = _source_health_rows()
    counts = _source_health_counts(sources)
    problem_rows = [row for row in sources if row["error_status"] or row["manual_review_needed"] or row["likely_broken_url"]]
    zero_rows = [row for row in sources if not row["jobs_found"] and row["last_checked_at"]]
    manual_rows = [row for row in sources if row["status"] == "needs_review" or row["manual_review_needed"]]
    body = f"""
    <section class="jr-band detail">
      <div class="jr-band-heading">
        <h2>Source Health Center</h2>
        <a class="jr-small-link" href="/">Back to Dashboard</a>
      </div>
      <div class="jr-health-grid">
        {_health_metric("Working", counts["working"], "green")}
        {_health_metric("Issues", counts["issues"], "amber")}
        {_health_metric("Manual Watch", counts["manual"], "amber")}
        {_health_metric("Disabled", counts["disabled"], "neutral")}
      </div>
      {_health_section("Needs Attention", problem_rows)}
      {_health_section("Zero Jobs Last Scan", zero_rows)}
      {_health_section("Manual Watch", manual_rows)}
      {_health_section("All Sources", sources)}
    </section>
    """
    return _page("Source Health Center", body)


def render_job_detail(job_id: str) -> str:
    rows = execute(
        """
        SELECT j.*, s.url AS source_home, s.platform, s.parser_type,
               js.score, js.explanation_json, js.scored_at
        FROM jobs j
        LEFT JOIN sources s ON s.id = j.source_id
        LEFT JOIN job_scores js ON js.job_id = j.id
        WHERE j.id = ?
        """,
        (job_id,),
    )
    if not rows:
        return _page("Job Not Found", "<p class=\"jr-help\">No job found for that id.</p>")

    row = rows[0]
    explanation = _explanation(row.get("explanation_json"))
    status_actions = _job_status_actions(row["id"])
    body = f"""
    <section class="jr-band detail">
      <div class="jr-band-heading">
        <h2>{_esc(row["title"])}</h2>
        <a class="jr-small-link" href="/">Back to Dashboard</a>
      </div>
      <div class="jr-detail-grid">
        <div>
          <h3>Role</h3>
          <p><strong>{_esc(row["organization"] or "")}</strong></p>
          <p>{_esc(row["location"] or "Location not specified")}</p>
          <p><a class="jr-link" href="{_esc(row["source_url"])}" target="_blank" rel="noreferrer">Open source posting</a></p>
        </div>
        <div>
          <h3>Fit</h3>
          <p><span class="pill green">{'Unscored' if row["score"] is None else f'{row["score"]:.1f}'}</span></p>
          {explanation}
        </div>
        <div>
          <h3>Status</h3>
          <p><span class="pill neutral">{_esc(row["user_status"])}</span></p>
          <div class="actions-cell">{status_actions}</div>
        </div>
      </div>
      <h3>Description</h3>
      <pre class="jr-description">{_esc(row["raw_description"] or "No description captured.")}</pre>
      <h3>Source Metadata</h3>
      <dl class="jr-metadata">
        <dt>Platform</dt><dd>{_esc(row["platform"] or "")}</dd>
        <dt>Parser</dt><dd>{_esc(row["parser_type"] or "")}</dd>
        <dt>First seen</dt><dd>{_esc(row["first_seen_at"] or "")}</dd>
        <dt>Last seen</dt><dd>{_esc(row["last_seen_at"] or "")}</dd>
        <dt>Source job id</dt><dd>{_esc(row["source_job_id"] or "")}</dd>
      </dl>
    </section>
    """
    return _page(row["title"], body)


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_esc(title)} - Job Radar</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <header class="jr-header compact">
    <div class="jr-title-wrap">
      <img class="jr-logo" src="/static/logo.png" alt="" width="76" height="76">
      <div><h1>Job Radar</h1><p class="jr-subtitle">Local opportunity monitoring</p></div>
    </div>
  </header>
  <main>{body}</main>
</body>
</html>"""


def _provider(name: str, env_name: str, url: str, link_label: str) -> str:
    return f"""
    <article class="jr-provider">
      <h3>{html.escape(name)}</h3>
      <code>{html.escape(env_name)}</code>
      <a href="{html.escape(url)}" target="_blank" rel="noreferrer">{html.escape(link_label)}</a>
    </article>
    """


def _wizard_step(label: str, done: bool, detail: str) -> str:
    return f"""
    <div class="jr-step {'done' if done else ''}">
      <strong>{_esc(label)}</strong>
      <span>{_esc(detail)}</span>
    </div>
    """


def _esc(value: str | None) -> str:
    return html.escape(value or "")


def _stats() -> dict[str, int]:
    jobs = execute("SELECT COUNT(*) AS n FROM jobs")
    sources = execute("SELECT COUNT(*) AS n FROM sources")
    issues = execute(
        """
        SELECT COUNT(*) AS n
        FROM source_health
        WHERE error_status IS NOT NULL OR manual_review_needed = 1 OR likely_broken_url = 1
        """
    )
    return {
        "jobs": jobs[0]["n"] if jobs else 0,
        "sources": sources[0]["n"] if sources else 0,
        "issues": issues[0]["n"] if issues else 0,
    }


_ACTIVE = (
    "j.is_live = 1 AND j.is_excluded = 0 "
    "AND j.lifecycle_status NOT IN ('probably_closed', 'dead')"
)


def _dashboard_jobs(view: str) -> list[dict]:
    order = "ORDER BY COALESCE(js.score, -1) DESC, j.first_seen_at DESC"
    if view == "new":
        where = f"WHERE {_ACTIVE}"
        order = "ORDER BY j.first_seen_at DESC"
    elif view == "closing":
        where = f"WHERE {_ACTIVE} AND j.deadline IS NOT NULL AND j.deadline != ''"
        order = "ORDER BY j.deadline ASC, COALESCE(js.score, -1) DESC"
    elif view == "stretch":
        where = f"WHERE {_ACTIVE} AND COALESCE(js.score, 0) BETWEEN 45 AND 69"
        order = "ORDER BY COALESCE(js.score, -1) DESC"
    elif view == "needs_review":
        where = "WHERE j.is_excluded = 1 OR js.score IS NULL"
    elif view == "excluded":
        where = (
            "WHERE j.is_excluded = 1 OR j.is_live = 0 "
            "OR j.lifecycle_status IN ('probably_closed', 'dead')"
        )
    elif view == "organization":
        where = f"WHERE {_ACTIVE}"
        order = "ORDER BY LOWER(COALESCE(j.organization, '')), COALESCE(js.score, -1) DESC"
    elif view == "location":
        where = f"WHERE {_ACTIVE}"
        order = "ORDER BY LOWER(COALESCE(j.location, '')), COALESCE(js.score, -1) DESC"
    else:
        where = f"WHERE {_ACTIVE}"

    return execute(
        f"""
        SELECT j.id, j.title, j.organization, j.location, j.remote_status, j.deadline,
               j.source_url, j.user_status, j.is_live, j.is_excluded, j.exclusion_reason,
               j.first_seen_at, j.last_seen_at, s.platform, h.error_status AS source_error,
               h.manual_review_needed AS source_manual_review, h.likely_broken_url AS source_broken,
               js.score, js.explanation_json
        FROM jobs j
        LEFT JOIN job_scores js ON js.job_id = j.id
        LEFT JOIN sources s ON s.id = j.source_id
        LEFT JOIN source_health h ON h.source_id = j.source_id
        {where}
        {order}
        LIMIT 25
        """
    )


def _source_health_rows() -> list[dict]:
    return execute(
        """
        SELECT s.id, s.url, s.organization, s.platform, s.parser_type, s.status,
               h.last_checked_at, h.last_successful_at, h.jobs_found, h.new_jobs_found,
               h.error_status, h.manual_review_needed, h.likely_broken_url,
               h.confidence_label, h.confidence_score, h.confidence_note
        FROM sources s
        LEFT JOIN source_health h ON h.source_id = s.id
        ORDER BY
          CASE
            WHEN h.error_status IS NOT NULL OR h.manual_review_needed = 1 OR h.likely_broken_url = 1 THEN 0
            WHEN s.status = 'disabled' THEN 2
            ELSE 1
          END,
          s.created_at,
          s.url
        """
    )


def _source_health_counts(sources: list[dict]) -> dict[str, int]:
    return {
        "working": sum(
            1 for row in sources
            if row["status"] == "active"
            and row["last_successful_at"]
            and not row["error_status"]
            and not row["manual_review_needed"]
            and not row["likely_broken_url"]
        ),
        "issues": sum(
            1 for row in sources
            if row["error_status"] or row["manual_review_needed"] or row["likely_broken_url"]
        ),
        "manual": sum(
            1 for row in sources
            if row["status"] == "needs_review" or row["manual_review_needed"]
        ),
        "disabled": sum(1 for row in sources if row["status"] == "disabled"),
    }


def _health_metric(label: str, value: int, klass: str) -> str:
    return f"""
    <article class="jr-health-metric">
      <span class="pill {klass}">{_esc(label)}</span>
      <strong>{value}</strong>
    </article>
    """


def _health_section(title: str, rows: list[dict]) -> str:
    table_rows = "".join(_source_row(row, health_center=True) for row in rows) or _empty_row(
        f"No sources in {title.lower()}.",
        10,
    )
    return f"""
    <section class="jr-health-section">
      <h3>{_esc(title)}</h3>
      <div class="jr-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Source</th>
              <th>Platform</th>
              <th>Parser</th>
              <th>Status</th>
              <th>Last Checked</th>
              <th>Last Success</th>
              <th>Jobs</th>
              <th>New</th>
              <th>Error</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>{table_rows}</tbody>
        </table>
      </div>
    </section>
    """


def _setup_steps(stats: dict[str, int], rubric: dict[str, str]) -> str:
    steps = [
        ("Sources", stats["sources"] > 0, f"{stats['sources']} saved"),
        ("Strategy", bool(rubric), "rubric saved" if rubric else "needed"),
        ("Refresh", stats["jobs"] > 0, f"{stats['jobs']} jobs"),
    ]
    return "".join(
        f"""
        <div class="jr-step {'done' if done else ''}">
          <strong>{_esc(label)}</strong>
          <span>{_esc(detail)}</span>
        </div>
        """
        for label, done, detail in steps
    )


def _strategy_summary(rubric: dict[str, str]) -> str:
    if not rubric:
        return '<p class="jr-help">No strategy saved yet. Add one before your first refresh for ranked results.</p>'
    chips = []
    for label, key in [
        ("Locations", "target_locations"),
        ("Industries", "preferred_industries"),
        ("Roles", "role_types"),
        ("Dealbreakers", "dealbreakers"),
    ]:
        value = rubric.get(key, "")
        if value:
            chips.append(f"<span class=\"summary-chip\"><strong>{label}</strong>{_esc(value.replace(chr(10), ', '))}</span>")
    narrative = rubric.get("strategy_narrative", "")
    return f"""
    <div class="jr-summary">
      {f'<p>{_esc(narrative)}</p>' if narrative else ''}
      <div class="jr-summary-chips">{''.join(chips)}</div>
    </div>
    """


def _source_preview_rows(urls: list[str], organization: str) -> str:
    if not urls:
        return ""
    rows = []
    for url in urls:
        detection = detect_source(url)
        reliability = _platform_reliability(detection.platform, detection.parser_type)
        rows.append(f"""
        <tr>
          <td><strong>{_esc(organization or 'Unlabeled')}</strong><br><span class="muted">{_esc(url)}</span></td>
          <td>{_esc(detection.platform)}</td>
          <td>{_esc(detection.parser_type)}</td>
          <td><span class="pill {'amber' if detection.manual_review_needed else 'green'}">{_esc(reliability)}</span></td>
          <td>{_esc(detection.note)}</td>
        </tr>
        """)
    return f"""
    <div class="jr-preview">
      <h3>Source Detection Preview</h3>
      <div class="jr-table-wrap">
        <table>
          <thead><tr><th>Source</th><th>Platform</th><th>Parser</th><th>Reliability</th><th>Note</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    </div>
    """


def _radar_section() -> str:
    """Today's Radar — new, reappeared, changed, and source issues at a glance."""
    new_jobs = execute(
        """
        SELECT j.id, j.title, j.organization, j.location, j.source_url,
               j.first_seen_at, js.score
        FROM jobs j
        LEFT JOIN job_scores js ON js.job_id = j.id
        WHERE j.lifecycle_status = 'new'
        ORDER BY j.first_seen_at DESC
        LIMIT 8
        """
    )
    reappeared_jobs = execute(
        """
        SELECT j.id, j.title, j.organization, j.last_seen_at, js.score
        FROM jobs j
        LEFT JOIN job_scores js ON js.job_id = j.id
        WHERE j.lifecycle_status = 'reappeared'
        ORDER BY j.last_seen_at DESC
        LIMIT 5
        """
    )
    changed_jobs = execute(
        """
        SELECT j.id, j.title, j.organization, j.last_changed_at
        FROM jobs j
        WHERE j.lifecycle_status = 'changed'
        ORDER BY j.last_changed_at DESC
        LIMIT 5
        """
    )
    problem_sources = execute(
        """
        SELECT s.organization, s.url, h.confidence_label, h.confidence_score, h.confidence_note
        FROM sources s
        JOIN source_health h ON h.source_id = s.id
        WHERE h.confidence_label IN ('broken', 'degrading', 'watch')
        ORDER BY h.confidence_score ASC
        LIMIT 5
        """
    )

    if not new_jobs and not reappeared_jobs and not changed_jobs and not problem_sources:
        return ""

    new_items = "".join(
        f"""<li>
          <a class="jr-link" href="/job?job_id={_esc(j['id'])}">{_esc(j['title'])}</a>
          <span class="muted"> — {_esc(j['organization'] or '')}</span>
          {'<span class="pill green">' + str(int(j["score"])) + '</span>' if j.get("score") else ''}
        </li>"""
        for j in new_jobs
    ) or "<li class='muted'>None since last scan.</li>"

    reappeared_items = "".join(
        f"""<li>
          <span class="pill teal">back</span>
          <a class="jr-link" href="/job?job_id={_esc(j['id'])}">{_esc(j['title'])}</a>
          <span class="muted"> — {_esc(j['organization'] or '')}</span>
          {'<span class="pill green">' + str(int(j["score"])) + '</span>' if j.get("score") else ''}
        </li>"""
        for j in reappeared_jobs
    ) or "<li class='muted'>None.</li>"

    changed_items = "".join(
        f"""<li>
          <a class="jr-link" href="/job?job_id={_esc(j['id'])}">{_esc(j['title'])}</a>
          <span class="muted"> — {_esc(j['organization'] or '')}</span>
        </li>"""
        for j in changed_jobs
    ) or "<li class='muted'>None.</li>"

    source_items = "".join(
        f"""<li>
          <span class="pill {'red' if s['confidence_label'] == 'broken' else 'orange' if s['confidence_label'] == 'degrading' else 'amber'}"
                title="{_esc(s['confidence_note'] or '')}">{s.get('confidence_score') or 0}</span>
          <strong>{_esc(s['organization'] or s['url'])}</strong>
        </li>"""
        for s in problem_sources
    ) or "<li class='muted'>All sources healthy.</li>"

    return f"""
    <section class="jr-band" id="radar">
      <div class="jr-band-heading">
        <h2>Today&#8217;s Radar</h2>
        <a class="jr-small-link" href="/source-health">Source Health Center</a>
      </div>
      <div class="jr-radar-grid">
        <div class="jr-radar-col">
          <h3>New ({len(new_jobs)})</h3>
          <ul class="jr-radar-list">{new_items}</ul>
        </div>
        <div class="jr-radar-col">
          <h3>Reappeared ({len(reappeared_jobs)})</h3>
          <ul class="jr-radar-list">{reappeared_items}</ul>
        </div>
        <div class="jr-radar-col">
          <h3>Changed ({len(changed_jobs)})</h3>
          <ul class="jr-radar-list">{changed_items}</ul>
        </div>
        <div class="jr-radar-col">
          <h3>Sources ({len(problem_sources)} need attention)</h3>
          <ul class="jr-radar-list">{source_items}</ul>
        </div>
      </div>
    </section>
    """


def _scan_report_from_result(result) -> dict:
    return {
        "run_id": result.run_id,
        "sources_attempted": result.sources_attempted,
        "sources_succeeded": result.sources_succeeded,
        "sources_failed": result.sources_failed,
        "jobs_found": result.jobs_found,
        "new_jobs_found": result.new_jobs_found,
        "jobs_changed": sum(getattr(r, "jobs_changed", 0) for r in result.results),
        "failed_sources": [
            {"url": item.url, "platform": item.platform, "error": item.error}
            for item in result.results
            if not item.success
        ],
    }


def _scan_report_card(report: dict | None) -> str:
    if not report:
        return ""
    failed = int(report.get("sources_failed") or 0)
    failed_items = report.get("failed_sources") or []
    failed_rows = "".join(
        f"<li><strong>{_esc(item.get('platform'))}</strong> {_esc(item.get('url'))}: {_esc(item.get('error'))}</li>"
        for item in failed_items[:4]
    )
    return f"""
    <section class="jr-band jr-scan-report">
      <div class="jr-band-heading">
        <h2>Latest Scan Report</h2>
        <span class="pill {'amber' if failed else 'green'}">{failed} failed</span>
      </div>
      <div class="jr-report-grid">
        <span><strong>{report.get("sources_attempted", 0)}</strong> sources checked</span>
        <span><strong>{report.get("jobs_found", 0)}</strong> jobs found</span>
        <span><strong>{report.get("new_jobs_found", 0)}</strong> new</span>
        <span><strong>{report.get("jobs_changed", 0)}</strong> changed</span>
        <span><strong>{report.get("sources_succeeded", 0)}</strong> sources ok</span>
      </div>
      {f'<ul class="jr-report-errors">{failed_rows}</ul>' if failed_rows else ''}
    </section>
    """


def _platform_reliability(platform: str, parser_type: str) -> str:
    if platform in {"greenhouse", "lever", "smartrecruiters", "workable", "ashby"}:
        return "Stable API"
    if platform == "personio":
        return "Stable XML"
    if parser_type == "static_html":
        return "Best effort"
    return "Manual watch"


def _saved_views(active: str) -> str:
    views = [
        ("best", "Best Matches"),
        ("new", "New"),
        ("closing", "Closing Soon"),
        ("stretch", "Stretch Roles"),
        ("needs_review", "Needs Review"),
        ("excluded", "Excluded/Stale"),
        ("organization", "By Organization"),
        ("location", "By Location"),
    ]
    links = "".join(
        f'<a class="{"active" if key == active else ""}" href="/?view={_esc(key)}#ranked">{_esc(label)}</a>'
        for key, label in views
    )
    return f'<nav class="jr-view-tabs" aria-label="Saved job views">{links}</nav>'


def _job_cards(rows: list[dict]) -> str:
    if not rows:
        return ""
    cards = "".join(_job_card(row) for row in rows)
    return f'<div class="jr-job-card-grid">{cards}</div>'


def _job_card(row: dict) -> str:
    score = "Unscored" if row["score"] is None else f"{row['score']:.0f}"
    matched = _explanation_bits(row.get("explanation_json"), "matched", 2)
    concern = row["exclusion_reason"] or "; ".join(_explanation_bits(row.get("explanation_json"), "downgraded", 1))
    concern = concern or "No major concern recorded"
    source_status = _source_status_label(row)
    return f"""
    <article class="jr-job-card">
      <div class="jr-card-topline">
        <span class="pill {_score_class(row)}">Fit {score}</span>
        <span class="pill neutral">{_esc(row["user_status"] or "new")}</span>
      </div>
      <h3>{_esc(row["title"] or "")}</h3>
      <p class="muted">{_esc(row["organization"] or "Unknown organization")} - {_esc(row["location"] or "Location not specified")}</p>
      <p><strong>Matched:</strong> {_esc("; ".join(matched) or "No matched rules yet")}</p>
      <p><strong>Main concern:</strong> {_esc(concern)}</p>
      <p class="muted">Source: {_esc(row["platform"] or "unknown")} · {_esc(source_status)}</p>
      <div class="actions-cell">
        <a class="jr-small-link" href="/job?job_id={_esc(row["id"])}">Details</a>
        <a class="jr-small-link" href="{_esc(row["source_url"] or "#")}" target="_blank" rel="noreferrer">Open</a>
      </div>
    </article>
    """


def _score_class(row: dict) -> str:
    if row["is_excluded"]:
        return "amber"
    if row["score"] and row["score"] >= 65:
        return "green"
    return "neutral"


def _lifecycle_pill(status: str) -> str:
    classes = {
        "new": "green", "active": "neutral", "changed": "green",
        "reappeared": "green", "probably_closed": "amber", "dead": "amber",
    }
    return f'<span class="pill {classes.get(status, "neutral")}">{_esc(status)}</span>'


def _source_status_label(row: dict) -> str:
    if row.get("source_broken"):
        return "source likely broken"
    if row.get("source_error"):
        return "source has errors"
    if row.get("source_manual_review"):
        return "manual review"
    return "source healthy"


def _job_row(row: dict) -> str:
    score = "Unscored" if row["score"] is None else f"{row['score']:.1f}"
    score_class = _score_class(row)
    reason = row["exclusion_reason"] or ""
    explanation = _explanation_preview(row.get("explanation_json"))
    seen = _esc(row["first_seen_at"] or "")
    lifecycle = row.get("lifecycle_status") or "active"
    lifecycle_pill = _lifecycle_pill(lifecycle)
    return f"""
    <tr>
      <td><strong>{html.escape(row["title"] or "")}</strong>{f'<br><span class="muted">{html.escape(reason)}</span>' if reason else ''}</td>
      <td>{html.escape(row["organization"] or "")}</td>
      <td>{html.escape(row["location"] or "")}</td>
      <td>{lifecycle_pill}<br><span class="pill neutral">{html.escape(row["user_status"] or "new")}</span></td>
      <td><span class="pill {score_class}">{score}</span></td>
      <td class="muted">{explanation}</td>
      <td class="muted">{seen}</td>
      <td>{_esc(row["platform"] or "")}</td>
      <td><a class="jr-link" href="{html.escape(row["source_url"] or "#")}" target="_blank" rel="noreferrer">Open</a></td>
      <td class="actions-cell">
        <a class="jr-small-link" href="/job?job_id={_esc(row["id"])}">Details</a>
        {_job_status_actions(row["id"])}
      </td>
    </tr>
    """


def _source_row(row: dict, health_center: bool = False) -> str:
    confidence = row.get("confidence_label") or "unknown"
    score = row.get("confidence_score")
    note = row.get("confidence_note") or ""
    conf_class = {
        "healthy": "green", "watch": "amber", "degrading": "orange", "broken": "red",
    }.get(confidence, "neutral")
    score_str = f"{score} " if score is not None else ""
    conf_pill = f'<span class="pill {conf_class}" title="{html.escape(note)}">{score_str}{html.escape(confidence)}</span>'
    error = row.get("error_status") or ""
    if len(error) > 96:
        error = error[:93] + "..."
    label = row["organization"] or row["url"]
    last_success = f"<td>{html.escape(row.get('last_successful_at') or 'Never')}</td>" if health_center else ""
    return f"""
    <tr>
      <td><strong>{html.escape(label or "")}</strong><br><a class="jr-link muted" href="{html.escape(row["url"] or "#")}" target="_blank" rel="noreferrer">{html.escape(row["url"] or "")}</a></td>
      <td>{html.escape(row["platform"] or "")}</td>
      <td>{html.escape(row["parser_type"] or "")}</td>
      <td>{conf_pill}</td>
      <td>{html.escape(row.get("last_checked_at") or "Not checked")}</td>
      {last_success}
      <td>{row.get("jobs_found") or 0}</td>
      <td>{row.get("new_jobs_found") or 0}</td>
      <td class="error-cell">{html.escape(error)}</td>
      <td class="actions-cell">{_source_actions(row)}</td>
    </tr>
    """


def _source_actions(row: dict) -> str:
    retry = f"""
    <form method="post" action="/sources/retry">
      <input type="hidden" name="source_id" value="{html.escape(row["id"])}">
      <button class="jr-small-button" type="submit">Retry</button>
    </form>
    """
    manual = ""
    if row["status"] == "needs_review" or row["manual_review_needed"]:
        manual = f"""
        <form method="post" action="/sources/manual-check">
          <input type="hidden" name="source_id" value="{html.escape(row["id"])}">
          <button class="jr-small-button secondary" type="submit">Mark Checked</button>
        </form>
        """
    edit = f"""
    <form method="post" action="/sources/edit" class="source-edit-form">
      <input type="hidden" name="source_id" value="{html.escape(row["id"])}">
      <input name="organization" type="text" value="{html.escape(row["organization"] or "")}" placeholder="Org">
      <input name="url" type="text" value="{html.escape(row["url"] or "")}" placeholder="URL">
      <button class="jr-small-button secondary" type="submit">Save</button>
    </form>
    """
    if row["status"] == "disabled":
        toggle = f"""
        <form method="post" action="/sources/enable">
          <input type="hidden" name="source_id" value="{html.escape(row["id"])}">
          <button class="jr-small-button secondary" type="submit">Enable</button>
        </form>
        """
    else:
        toggle = f"""
        <form method="post" action="/sources/disable">
          <input type="hidden" name="source_id" value="{html.escape(row["id"])}">
          <button class="jr-small-button danger" type="submit">Disable</button>
        </form>
        """
    return retry + manual + edit + toggle


def _job_status_actions(job_id: str) -> str:
    return "".join(
        f"""
        <form method="post" action="/jobs/status">
          <input type="hidden" name="job_id" value="{_esc(job_id)}">
          <input type="hidden" name="status" value="{_esc(status)}">
          <button class="jr-small-button {klass}" type="submit">{_esc(label)}</button>
        </form>
        """
        for status, label, klass in [
            ("shortlisted", "Shortlist", "secondary"),
            ("reviewing", "Reviewing", ""),
            ("applied", "Applied", "secondary"),
            ("rejected", "Reject", "danger"),
            ("archived", "Archive", ""),
        ]
    )


def _explanation_preview(payload: str | None) -> str:
    if not payload:
        return "No score explanation yet"
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return "Score explanation unavailable"
    parts = (data.get("excluded") or []) + (data.get("matched") or []) + (data.get("downgraded") or [])
    return _esc("; ".join(parts[:2]) or "No matched rules")


def _explanation_bits(payload: str | None, key: str, limit: int) -> list[str]:
    if not payload:
        return []
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    return list(data.get(key) or [])[:limit]


def _explanation(payload: str | None) -> str:
    if not payload:
        return '<p class="muted">No score explanation yet.</p>'
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return '<p class="muted">Score explanation unavailable.</p>'
    sections = []
    for label, key in [("Matched", "matched"), ("Downgraded", "downgraded"), ("Excluded", "excluded")]:
        values = data.get(key) or []
        if values:
            items = "".join(f"<li>{_esc(value)}</li>" for value in values)
            sections.append(f"<h4>{label}</h4><ul>{items}</ul>")
    return "".join(sections) or '<p class="muted">No matched rules.</p>'


def update_job_status(job_id: str, status: str) -> None:
    allowed = {"new", "shortlisted", "reviewing", "applied", "interviewing", "rejected", "archived"}
    if status not in allowed:
        return
    execute("UPDATE jobs SET user_status = ? WHERE id = ?", (status, job_id))
    execute(
        """
        INSERT INTO applications (job_id, status, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(job_id) DO UPDATE SET
            status = excluded.status,
            updated_at = CURRENT_TIMESTAMP
        """,
        (job_id, status),
    )


def update_source(source_id: str, url: str, organization: str | None) -> None:
    clean_url = url.strip()
    if not clean_url:
        return
    detection = detect_source(clean_url)
    execute(
        """
        UPDATE sources
        SET url = ?,
            organization = ?,
            platform = ?,
            parser_type = ?,
            config_json = ?,
            detection_note = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            clean_url,
            organization or None,
            detection.platform,
            detection.parser_type,
            json.dumps(detection.config),
            detection.note,
            source_id,
        ),
    )


def set_source_status(source_id: str, status: str) -> None:
    if status not in {"active", "disabled", "needs_review"}:
        return
    execute(
        """
        UPDATE sources
        SET status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, source_id),
    )


def import_source_pack(pack_id: str, selected_urls: set[str] | None = None) -> int:
    pack = get_source_pack(pack_id)
    if not pack:
        return 0
    selected = selected_urls or {entry.url for entry in pack.entries}
    count = 0
    for entry in pack.entries:
        if entry.url not in selected:
            continue
        add_source(entry.url, organization=entry.organization)
        count += 1
    return count


def restore_database(backup_path: str) -> bool:
    source = Path(backup_path).expanduser()
    if not source.exists() or not source.is_file():
        set_state("last_restore_error", f"Backup file not found: {backup_path}")
        return False
    if source.suffix not in {".sqlite", ".db"}:
        set_state("last_restore_error", "Backup must be a .sqlite or .db file")
        return False

    destination = get_settings().db_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    init_db()
    set_state("last_restore_error", "")
    set_state("last_scan_report", None)
    return True


def export_jobs_csv() -> str:
    rows = execute(
        """
        SELECT j.title, j.organization, j.location, j.user_status, j.is_live,
               j.is_excluded, j.exclusion_reason, j.source_url, s.platform,
               js.score, js.explanation_json
        FROM jobs j
        LEFT JOIN sources s ON s.id = j.source_id
        LEFT JOIN job_scores js ON js.job_id = j.id
        ORDER BY COALESCE(js.score, -1) DESC, j.first_seen_at DESC
        """
    )
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=[
        "title",
        "organization",
        "location",
        "user_status",
        "is_live",
        "is_excluded",
        "exclusion_reason",
        "source_url",
        "platform",
        "score",
        "explanation_json",
    ])
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def export_sources_json() -> str:
    rows = execute(
        """
        SELECT s.*, h.last_checked_at, h.last_successful_at, h.jobs_found,
               h.new_jobs_found, h.error_status, h.manual_review_needed, h.likely_broken_url
        FROM sources s
        LEFT JOIN source_health h ON h.source_id = s.id
        ORDER BY s.created_at, s.url
        """
    )
    return json.dumps(rows, indent=2)


def _empty_row(text: str, columns: int) -> str:
    return f'<tr><td colspan="{columns}" class="empty">{html.escape(text)}</td></tr>'


def _split_urls(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.replace(",", "\n").splitlines() if part.strip()]


def _first(form: dict[str, list[str]], key: str) -> str | None:
    values = form.get(key)
    return values[0].strip() if values else None


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _find_free_port(start: int) -> int:
    port = start
    while _port_open(port):
        port += 1
    return port
