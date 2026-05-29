from job_radar.app.server import (
    ANTHROPIC_KEYS_URL,
    OLLAMA_DOWNLOAD_URL,
    OPENAI_KEYS_URL,
    export_jobs_csv,
    import_source_pack,
    render_dashboard,
    render_job_detail,
    render_source_health_center,
    render_source_packs,
    render_wizard,
    restore_database,
    set_source_status,
    update_job_status,
    update_source,
)
from job_radar.app.state import get_state, set_state
from job_radar.config.settings import get_settings
from job_radar.db.client import execute, init_db
from job_radar.ingestion.source_store import add_source


def test_dashboard_renders_ai_setup_links(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    init_db()

    html = render_dashboard()

    assert "Job Radar" in html
    assert OPENAI_KEYS_URL in html
    assert ANTHROPIC_KEYS_URL in html
    assert OLLAMA_DOWNLOAD_URL in html
    assert "Source Health" in html
    get_settings.cache_clear()


def test_dashboard_renders_source_preview(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    init_db()

    html = render_dashboard(preview_urls=["https://jobs.lever.co/acme"], preview_org="Acme")

    assert "Source Detection Preview" in html
    assert "lever" in html
    assert "Stable API" in html
    get_settings.cache_clear()


def test_status_actions_update_job_and_application(tmp_path, monkeypatch):
    job_id = _seed_job(tmp_path, monkeypatch)

    update_job_status(job_id, "shortlisted")

    job = execute("SELECT user_status FROM jobs WHERE id = ?", (job_id,))[0]
    app = execute("SELECT status FROM applications WHERE job_id = ?", (job_id,))[0]
    assert job["user_status"] == "shortlisted"
    assert app["status"] == "shortlisted"
    get_settings.cache_clear()


def test_job_detail_and_export_render_stored_job(tmp_path, monkeypatch):
    job_id = _seed_job(tmp_path, monkeypatch)

    detail = render_job_detail(job_id)
    csv_text = export_jobs_csv()

    assert "Policy Analyst" in detail
    assert "Description" in detail
    assert "Policy Analyst" in csv_text
    assert "source_url" in csv_text
    get_settings.cache_clear()


def test_wizard_and_source_pack_import(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    init_db()

    wizard = render_wizard()
    packs = render_source_packs()
    imported = import_source_pack("brussels_policy", {"https://www.bruegel.org/careers"})

    assert "Onboarding Wizard" in wizard
    assert "Brussels Policy Starter Pack" in packs
    assert imported == 1
    sources = execute("SELECT organization, url FROM sources")
    assert sources[0]["organization"] == "Bruegel"
    assert sources[0]["url"] == "https://www.bruegel.org/careers"
    get_settings.cache_clear()


def test_dashboard_renders_scan_report(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    init_db()
    set_state("last_scan_report", {
        "sources_attempted": 2,
        "sources_succeeded": 1,
        "sources_failed": 1,
        "jobs_found": 4,
        "new_jobs_found": 2,
        "failed_sources": [{"url": "https://example.org", "platform": "generic", "error": "timeout"}],
    })

    html = render_dashboard()

    assert "Latest Scan Report" in html
    assert "sources checked" in html
    assert "timeout" in html
    get_settings.cache_clear()


def test_restore_database_from_backup_path(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path / "live"))
    init_db()
    source = add_source("https://jobs.lever.co/acme", organization="Acme")
    backup_path = tmp_path / "backup.sqlite"
    get_settings().db_path.replace(backup_path)

    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path / "restored"))
    get_settings.cache_clear()

    assert restore_database(str(backup_path)) is True
    rows = execute("SELECT url FROM sources WHERE id = ?", (source.id,))
    assert rows[0]["url"] == "https://jobs.lever.co/acme"
    assert get_state("last_restore_error", "") == ""
    get_settings.cache_clear()


def test_source_health_center_and_source_actions(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    source = add_source("https://jobs.lever.co/acme", organization="Acme")
    execute(
        """
        INSERT INTO source_health (
            source_id, platform, parser_type, last_checked_at, error_status, manual_review_needed
        )
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """,
        (source.id, "lever", "api", "timeout", 1),
    )

    html = render_source_health_center()

    assert "Source Health Center" in html
    assert "Needs Attention" in html
    assert "timeout" in html
    assert "Disable" in html

    set_source_status(source.id, "disabled")
    update_source(source.id, "https://jobs.lever.co/acme-renamed", "Acme Renamed")
    row = execute("SELECT status, url, organization FROM sources WHERE id = ?", (source.id,))[0]
    assert row["status"] == "disabled"
    assert row["url"] == "https://jobs.lever.co/acme-renamed"
    assert row["organization"] == "Acme Renamed"
    get_settings.cache_clear()


def test_dashboard_saved_views_and_job_cards(tmp_path, monkeypatch):
    job_id = _seed_job(tmp_path, monkeypatch)
    execute(
        """
        INSERT INTO job_scores (job_id, score, explanation_json)
        VALUES (?, ?, ?)
        """,
        (
            job_id,
            68,
            '{"matched": ["matched location: London"], "downgraded": ["stretch seniority"], "excluded": []}',
        ),
    )

    html = render_dashboard(view="stretch")

    assert "Stretch Roles" in html
    assert "jr-job-card" in html
    assert "Main concern" in html
    assert "matched location: London" in html
    get_settings.cache_clear()


def _seed_job(tmp_path, monkeypatch) -> str:
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    source = add_source("https://jobs.lever.co/acme", organization="Acme")
    run_id = "run-1"
    job_id = "job-1"
    execute(
        "INSERT INTO runs (id, status, sources_attempted) VALUES (?, ?, ?)",
        (run_id, "success", 1),
    )
    execute(
        """
        INSERT INTO jobs (
            id, source_id, run_id, title, organization, location, source_url, raw_description
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            source.id,
            run_id,
            "Policy Analyst",
            "Acme",
            "London",
            "https://jobs.lever.co/acme/job-1",
            "Full job description.",
        ),
    )
    return job_id
