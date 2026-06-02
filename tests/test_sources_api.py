from fastapi import HTTPException
import pytest

from job_radar.api.routers.sources import (
    SourceUpdate,
    delete_source,
    disable_source,
    enable_source,
    get_source_health,
    mark_source_checked,
    update_source,
)
from job_radar.config.settings import get_settings
from job_radar.db.client import execute, init_db
from job_radar.ingestion.source_store import add_source


def test_update_source_redetects_and_saves_notes(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    init_db()
    source = add_source("https://example.org/careers", "Example")

    update_source(source.id, SourceUpdate(
        organization="Acme",
        url="https://jobs.lever.co/acme",
        notes="Important source",
    ))

    row = execute("SELECT organization, url, platform, status, notes FROM sources WHERE id = ?", (source.id,))[0]
    assert row["organization"] == "Acme"
    assert row["url"] == "https://jobs.lever.co/acme"
    assert row["platform"] == "lever"
    assert row["status"] == "active"
    assert row["notes"] == "Important source"
    get_settings.cache_clear()


def test_source_management_actions_update_status_and_health(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    init_db()
    source = add_source("https://example.org/careers", "Example")

    mark_source_checked(source.id)
    row = execute("SELECT status FROM sources WHERE id = ?", (source.id,))[0]
    health = execute("SELECT manual_review_needed FROM source_health WHERE source_id = ?", (source.id,))[0]
    assert row["status"] == "active"
    assert health["manual_review_needed"] == 0

    disable_source(source.id)
    assert execute("SELECT status FROM sources WHERE id = ?", (source.id,))[0]["status"] == "disabled"

    enable_source(source.id)
    assert execute("SELECT status FROM sources WHERE id = ?", (source.id,))[0]["status"] == "active"
    get_settings.cache_clear()


def test_delete_source_only_when_no_jobs(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    init_db()
    source = add_source("https://jobs.lever.co/acme", "Acme")

    delete_source(source.id)
    assert execute("SELECT id FROM sources WHERE id = ?", (source.id,)) == []

    source = add_source("https://jobs.lever.co/beta", "Beta")
    execute(
        """
        INSERT INTO runs (id, status) VALUES ('run1', 'success');
        """
    )
    execute(
        """
        INSERT INTO jobs (id, source_id, run_id, title, source_url)
        VALUES ('job1', ?, 'run1', 'Policy Lead', 'https://jobs.lever.co/beta/1')
        """,
        (source.id,),
    )

    with pytest.raises(HTTPException) as exc:
        delete_source(source.id)
    assert exc.value.status_code == 409
    assert execute("SELECT id FROM sources WHERE id = ?", (source.id,))
    get_settings.cache_clear()


def test_source_health_includes_editable_fields(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    init_db()
    source = add_source("https://jobs.lever.co/acme", "Acme")
    update_source(source.id, SourceUpdate(
        organization="Acme",
        url="https://jobs.lever.co/acme",
        notes="Watch weekly",
    ))

    health = get_source_health()
    result = health["results"][0]
    assert result["url"] == "https://jobs.lever.co/acme"
    assert result["status"] == "active"
    assert result["notes"] == "Watch weekly"
    get_settings.cache_clear()
