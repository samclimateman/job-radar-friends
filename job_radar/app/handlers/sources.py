"""Source builder, source health center, and source data mutations."""

from __future__ import annotations

import html
import json

from job_radar.app.common import _empty_row, _esc, _page
from job_radar.db.client import execute
from job_radar.ingestion.source_detection import detect_source


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
    notes_val = html.escape(row.get("notes") or "")
    notes_form = f"""
    <form method="post" action="/sources/notes" class="source-notes-form">
      <input type="hidden" name="source_id" value="{html.escape(row['id'])}">
      <input name="notes" type="text" value="{notes_val}" placeholder="Org notes (e.g. contact, hiring freeze, priority)">
      <button class="jr-small-button secondary" type="submit">Save note</button>
    </form>
    """
    return retry + manual + edit + notes_form + toggle


def _platform_reliability(platform: str, parser_type: str) -> str:
    if platform in {"greenhouse", "lever", "smartrecruiters", "workable", "ashby"}:
        return "Stable API"
    if platform == "personio":
        return "Stable XML"
    if parser_type == "static_html":
        return "Best effort"
    return "Manual watch"


def update_source_notes(source_id: str, notes: str) -> None:
    execute(
        "UPDATE sources SET notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (notes.strip() or None, source_id),
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
