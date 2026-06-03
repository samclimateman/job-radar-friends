from job_radar.config.settings import get_settings
from job_radar.db.client import execute
from job_radar.ingestion.source_store import add_source, list_sources, mark_manual_checked


def test_add_source_persists_detected_platform(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))

    source = add_source("https://jobs.lever.co/acme", organization="Acme")
    sources = list_sources()

    assert source.platform == "lever"
    assert source.status == "active"
    assert len(sources) == 1
    assert sources[0].organization == "Acme"
    get_settings.cache_clear()


def test_add_source_normalizes_bare_domain(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))

    source = add_source("jobs.lever.co/acme", organization="Acme")

    assert source.url == "https://jobs.lever.co/acme"
    get_settings.cache_clear()


def test_add_unknown_source_marks_needs_review(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))

    source = add_source("https://example.org/careers")

    assert source.platform == "generic_static"
    assert source.status == "needs_review"
    get_settings.cache_clear()


def test_mark_manual_checked_updates_source_health(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    source = add_source("https://example.org/careers")

    mark_manual_checked(source.id)

    health = execute("SELECT * FROM source_health WHERE source_id = ?", (source.id,))[0]
    assert health["manual_review_needed"] == 0
    assert health["error_status"] is None
    assert health["last_checked_at"] is not None
    get_settings.cache_clear()
