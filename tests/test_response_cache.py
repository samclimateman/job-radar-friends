"""Tests for the URL-set response cache."""

from job_radar.ingestion.response_cache import (
    compute_url_hash,
    invalidate,
    is_unchanged,
    update,
)


def test_compute_url_hash_is_deterministic():
    urls = {"https://example.org/jobs/1", "https://example.org/jobs/2"}
    assert compute_url_hash(urls) == compute_url_hash(urls)


def test_compute_url_hash_is_order_independent():
    a = compute_url_hash({"https://a.org", "https://b.org"})
    b = compute_url_hash({"https://b.org", "https://a.org"})
    assert a == b


def test_compute_url_hash_differs_for_different_sets():
    a = compute_url_hash({"https://example.org/jobs/1"})
    b = compute_url_hash({"https://example.org/jobs/2"})
    assert a != b


def test_is_unchanged_false_when_no_prior_record(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    from job_radar.config.settings import get_settings
    get_settings.cache_clear()
    assert is_unchanged("src-1", "abc123") is False
    get_settings.cache_clear()


def test_is_unchanged_true_after_update(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    from job_radar.config.settings import get_settings
    get_settings.cache_clear()
    update("src-1", "abc123")
    assert is_unchanged("src-1", "abc123") is True
    get_settings.cache_clear()


def test_is_unchanged_false_after_hash_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    from job_radar.config.settings import get_settings
    get_settings.cache_clear()
    update("src-1", "abc123")
    assert is_unchanged("src-1", "xyz999") is False
    get_settings.cache_clear()


def test_invalidate_clears_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    from job_radar.config.settings import get_settings
    get_settings.cache_clear()
    update("src-1", "abc123")
    invalidate("src-1")
    assert is_unchanged("src-1", "abc123") is False
    get_settings.cache_clear()


def test_multiple_sources_tracked_independently(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    from job_radar.config.settings import get_settings
    get_settings.cache_clear()
    update("src-1", "hash-a")
    update("src-2", "hash-b")
    assert is_unchanged("src-1", "hash-a") is True
    assert is_unchanged("src-2", "hash-b") is True
    assert is_unchanged("src-1", "hash-b") is False
    get_settings.cache_clear()
