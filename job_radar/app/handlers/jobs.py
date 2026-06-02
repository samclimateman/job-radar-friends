"""Job detail, job row rendering, and status updates."""

from __future__ import annotations

import html
import json

from job_radar.app.common import _esc, _empty_row, _page
from job_radar.db.client import execute


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


def _explanation_bits(payload: str | None, key: str, limit: int) -> list[str]:
    if not payload:
        return []
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    return list(data.get(key) or [])[:limit]


def _explanation_preview(payload: str | None) -> str:
    if not payload:
        return '<span class="muted">No score yet</span>'
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return '<span class="muted">—</span>'
    excluded = data.get("excluded") or []
    if excluded:
        reason = excluded[0].removeprefix("excluded because: ")
        return f'<span class="pill red" title="{_esc(excluded[0])}">Excluded: {_esc(reason[:40])}</span>'
    matched = data.get("matched") or []
    downgraded = data.get("downgraded") or []
    def _val(s: str) -> str:
        return s.split(": ", 1)[-1] if ": " in s else s
    top = [_val(m) for m in matched[:3]]
    parts = " · ".join(top) if top else "—"
    note = f' <span class="muted">({len(downgraded)} concern{"s" if len(downgraded) != 1 else ""})</span>' if downgraded else ""
    return f'<span class="muted">{_esc(parts)}</span>{note}'


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
