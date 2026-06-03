"""Main dashboard rendering."""

from __future__ import annotations

from job_radar.app.common import _empty_row, _esc, _provider, _stats
from job_radar.app.handlers.jobs import _explanation, _job_cards, _job_row, _score_label
from job_radar.app.handlers.sources import _source_row
from job_radar.app.state import get_state
from job_radar.config.env_file import load_api_env
from job_radar.db.client import execute
from job_radar.ingestion.source_detection import detect_source
from job_radar.scoring.store import active_rubric_values

OPENAI_KEYS_URL = "https://platform.openai.com/api-keys"
ANTHROPIC_KEYS_URL = "https://console.anthropic.com/settings/keys"
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download"

_ACTIVE = (
    "j.is_live = 1 AND j.is_excluded = 0 "
    "AND j.lifecycle_status NOT IN ('probably_closed', 'dead') "
    "AND j.user_status NOT IN ('archived', 'rejected')"
)


def render_dashboard(
    preview_urls: list[str] | None = None,
    preview_org: str = "",
    view: str = "best",
    q: str = "",
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
    jobs = _dashboard_jobs(view, q=q)
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
    <a href="/notebook">Notebook</a>
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
      <p style="margin-top:1rem"><a class="jr-small-link" href="/rubric/preview">Test a job against this rubric →</a></p>
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
        {_saved_views(view, q=q)}
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


def _dashboard_jobs(view: str, q: str = "") -> list[dict]:
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

    params: tuple = ()
    if q:
        like = f"%{q}%"
        where += " AND (j.title LIKE ? OR j.organization LIKE ? OR j.location LIKE ?)"
        params = (like, like, like)

    return execute(
        f"""
        SELECT j.id, j.title, j.organization, j.location, j.remote_status, j.deadline,
               j.source_url, j.user_status, j.is_live, j.is_excluded, j.exclusion_reason,
               j.first_seen_at, j.last_seen_at, j.lifecycle_status,
               s.platform, s.notes AS source_notes,
               h.error_status AS source_error,
               h.manual_review_needed AS source_manual_review, h.likely_broken_url AS source_broken,
               js.score, js.explanation_json
        FROM jobs j
        LEFT JOIN job_scores js ON js.job_id = j.id
        LEFT JOIN sources s ON s.id = j.source_id
        LEFT JOIN source_health h ON h.source_id = j.source_id
        {where}
        {order}
        LIMIT 200
        """,
        params,
    )


def _radar_section() -> str:
    new_jobs = execute(
        """
        SELECT j.id, j.title, j.organization, j.location, j.source_url,
               j.first_seen_at, js.score
        FROM jobs j
        LEFT JOIN job_scores js ON js.job_id = j.id
        WHERE j.lifecycle_status = 'new'
          AND j.user_status NOT IN ('archived', 'rejected')
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
          AND j.user_status NOT IN ('archived', 'rejected')
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


def _saved_views(active: str, q: str = "") -> str:
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
    q_param = f"&q={_esc(q)}" if q else ""
    links = "".join(
        f'<a class="{"active" if key == active else ""}" href="/?view={_esc(key)}{q_param}#ranked">{_esc(label)}</a>'
        for key, label in views
    )
    clear_link = f' <a class="jr-small-link" href="/?view={_esc(active)}#ranked">Clear</a>' if q else ""
    search_form = f"""<form class="jr-search-form" method="get" action="/" onsubmit="this.action='/#ranked'">
      <input type="hidden" name="view" value="{_esc(active)}">
      <input class="jr-search-input" type="search" name="q" value="{_esc(q)}" placeholder="Search jobs…" aria-label="Search jobs">
      <button class="jr-small-button" type="submit">Search</button>{clear_link}
    </form>"""
    return f'<nav class="jr-view-tabs" aria-label="Saved job views">{links}</nav>{search_form}'


def _source_preview_rows(urls: list[str], organization: str) -> str:
    if not urls:
        return ""
    rows = []
    for url in urls:
        detection = detect_source(url)
        from job_radar.app.handlers.sources import _platform_reliability
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


def render_rubric_preview(title: str, description: str, location: str) -> str:
    import json

    from job_radar.app.common import _page
    from job_radar.ingestion.models import ScrapedJob
    from job_radar.scoring.deterministic import score_job
    from job_radar.scoring.rubric import ScoringRubric, split_terms

    rubric_values = active_rubric_values()
    if not rubric_values:
        return _page("Rubric Preview", '<p class="jr-help">No strategy saved yet. Save a strategy first.</p>')

    rubric = ScoringRubric(
        strategy_narrative=rubric_values.get("strategy_narrative", ""),
        target_locations=split_terms(rubric_values.get("target_locations")),
        preferred_industries=split_terms(rubric_values.get("preferred_industries")),
        role_types=split_terms(rubric_values.get("role_types")),
        seniority=split_terms(rubric_values.get("seniority")),
        positive_keywords=split_terms(rubric_values.get("positive_keywords")),
        negative_keywords=split_terms(rubric_values.get("negative_keywords")),
        dealbreakers=split_terms(rubric_values.get("dealbreakers")),
    )

    job = ScrapedJob(
        title=title or "Untitled",
        organization=None,
        source_url="https://example.com",
        raw_description=description or "",
        location=location or None,
    )
    result = score_job(job, rubric)

    explanation_json = json.dumps({
        "matched": result.matched,
        "downgraded": result.downgraded,
        "excluded": result.excluded,
    })
    explanation_html = _explanation(explanation_json)
    label = _score_label(result.score)
    score_display = f"{result.score:.0f}" if not result.is_excluded else "excluded"

    body = f"""
    <section class="jr-band detail">
      <div class="jr-band-heading">
        <h2>Rubric Preview</h2>
        <a class="jr-small-link" href="/#strategy">Back to Strategy</a>
      </div>
      <p><strong>{_esc(title or "Untitled")}</strong>
      {f'<span class="muted"> · {_esc(location)}</span>' if location else ''}</p>
      <p>
        <span class="pill {'green' if result.score >= 50 else 'amber' if result.score >= 30 else 'neutral'}">{score_display}</span>
        <span class="muted" style="margin-left:8px;font-size:0.85rem">{_esc(label)}</span>
      </p>
      {explanation_html}
      <form method="post" action="/rubric/preview" class="jr-strategy-grid" style="margin-top:1.5rem">
        <label><span>Job title</span><input name="title" type="text" value="{_esc(title)}"></label>
        <label><span>Location</span><input name="location" type="text" value="{_esc(location)}"></label>
        <label class="wide"><span>Description</span><textarea name="description" rows="6">{_esc(description)}</textarea></label>
        <button class="jr-button" type="submit">Re-score</button>
      </form>
    </section>
    """
    return _page("Rubric Preview", body)
