"""Tests for ingestion/store.py lifecycle transitions and touch_source_jobs."""

from job_radar.config.settings import get_settings
from job_radar.db.client import execute, init_db
from job_radar.ingestion.models import ScrapedJob
from job_radar.ingestion.source_store import StoredSource, add_source
from job_radar.ingestion.store import (
    _DEAD_THRESHOLD,
    _PROBABLY_CLOSED_THRESHOLD,
    start_run,
    store_jobs,
    touch_source_jobs,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _source(tmp_path, monkeypatch) -> StoredSource:
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    init_db()
    stored = add_source("https://job-boards.greenhouse.io/acme", organization="Acme")
    return StoredSource(
        id=stored.id,
        url=stored.url,
        organization=stored.organization,
        platform=stored.platform,
        parser_type=stored.parser_type,
        config={},
        status="active",
        detection_note="",
    )


def _job(url: str = "https://jobs.example.com/1", title: str = "Analyst") -> ScrapedJob:
    return ScrapedJob(
        title=title,
        organization="Acme",
        source_url=url,
        raw_description="A policy analyst role.",
    )


def _run_id(source) -> str:
    return start_run(1)


def _lifecycle(source_id: str, url: str) -> str:
    rows = execute(
        "SELECT lifecycle_status FROM jobs WHERE source_id = ? AND source_url = ?",
        (source_id, url),
    )
    return rows[0]["lifecycle_status"] if rows else ""


def _missed(source_id: str, url: str) -> int:
    rows = execute(
        "SELECT missed_scans FROM jobs WHERE source_id = ? AND source_url = ?",
        (source_id, url),
    )
    return rows[0]["missed_scans"] if rows else -1


# ── New job ───────────────────────────────────────────────────────────────────

def test_new_job_has_lifecycle_new(tmp_path, monkeypatch):
    src = _source(tmp_path, monkeypatch)
    store_jobs(_run_id(src), src, [_job()])
    assert _lifecycle(src.id, "https://jobs.example.com/1") == "new"
    get_settings.cache_clear()


# ── Active / unchanged ────────────────────────────────────────────────────────

def test_seen_again_unchanged_becomes_active(tmp_path, monkeypatch):
    src = _source(tmp_path, monkeypatch)
    run_id = _run_id(src)
    store_jobs(run_id, src, [_job()])
    store_jobs(_run_id(src), src, [_job()])   # second scan, same description
    assert _lifecycle(src.id, "https://jobs.example.com/1") == "active"
    get_settings.cache_clear()


def test_seen_again_changed_description_becomes_changed(tmp_path, monkeypatch):
    src = _source(tmp_path, monkeypatch)
    store_jobs(_run_id(src), src, [_job()])
    changed = _job()
    changed = ScrapedJob(
        title="Analyst", organization="Acme",
        source_url="https://jobs.example.com/1",
        raw_description="Completely different description.",
    )
    store_jobs(_run_id(src), src, [changed])
    assert _lifecycle(src.id, "https://jobs.example.com/1") == "changed"
    get_settings.cache_clear()


# ── Missed scans → probably_closed ────────────────────────────────────────────

def test_missed_scans_increments_when_job_absent(tmp_path, monkeypatch):
    src = _source(tmp_path, monkeypatch)
    store_jobs(_run_id(src), src, [_job(url="https://jobs.example.com/1")])

    # Scan returns a different job — job/1 is absent
    store_jobs(_run_id(src), src, [_job(url="https://jobs.example.com/2")])
    assert _missed(src.id, "https://jobs.example.com/1") == 1
    get_settings.cache_clear()


def test_probably_closed_at_threshold(tmp_path, monkeypatch):
    src = _source(tmp_path, monkeypatch)
    store_jobs(_run_id(src), src, [_job(url="https://jobs.example.com/1")])

    other = _job(url="https://jobs.example.com/other")
    for _ in range(_PROBABLY_CLOSED_THRESHOLD):
        store_jobs(_run_id(src), src, [other])

    assert _lifecycle(src.id, "https://jobs.example.com/1") == "probably_closed"
    get_settings.cache_clear()


def test_dead_at_threshold(tmp_path, monkeypatch):
    src = _source(tmp_path, monkeypatch)
    store_jobs(_run_id(src), src, [_job(url="https://jobs.example.com/1")])

    other = _job(url="https://jobs.example.com/other")
    for _ in range(_DEAD_THRESHOLD):
        store_jobs(_run_id(src), src, [other])

    row = execute(
        "SELECT lifecycle_status, is_live FROM jobs WHERE source_id = ? AND source_url = ?",
        (src.id, "https://jobs.example.com/1"),
    )[0]
    assert row["lifecycle_status"] == "dead"
    assert row["is_live"] == 0
    get_settings.cache_clear()


# ── Reappeared ────────────────────────────────────────────────────────────────

def test_probably_closed_job_reappears(tmp_path, monkeypatch):
    src = _source(tmp_path, monkeypatch)
    job_url = "https://jobs.example.com/1"
    other = _job(url="https://jobs.example.com/other")

    store_jobs(_run_id(src), src, [_job(url=job_url)])
    for _ in range(_PROBABLY_CLOSED_THRESHOLD):
        store_jobs(_run_id(src), src, [other])

    assert _lifecycle(src.id, job_url) == "probably_closed"

    # Job comes back
    store_jobs(_run_id(src), src, [_job(url=job_url)])
    assert _lifecycle(src.id, job_url) == "reappeared"
    assert _missed(src.id, job_url) == 0
    get_settings.cache_clear()


def test_dead_job_reappears(tmp_path, monkeypatch):
    src = _source(tmp_path, monkeypatch)
    job_url = "https://jobs.example.com/1"
    other = _job(url="https://jobs.example.com/other")

    store_jobs(_run_id(src), src, [_job(url=job_url)])
    for _ in range(_DEAD_THRESHOLD):
        store_jobs(_run_id(src), src, [other])

    assert _lifecycle(src.id, job_url) == "dead"

    store_jobs(_run_id(src), src, [_job(url=job_url)])
    row = execute(
        "SELECT lifecycle_status, is_live, missed_scans FROM jobs WHERE source_id = ? AND source_url = ?",
        (src.id, job_url),
    )[0]
    assert row["lifecycle_status"] == "reappeared"
    assert row["is_live"] == 1
    assert row["missed_scans"] == 0
    get_settings.cache_clear()


def test_reappeared_with_changed_description(tmp_path, monkeypatch):
    src = _source(tmp_path, monkeypatch)
    job_url = "https://jobs.example.com/1"
    other = _job(url="https://jobs.example.com/other")

    store_jobs(_run_id(src), src, [_job(url=job_url)])
    for _ in range(_PROBABLY_CLOSED_THRESHOLD):
        store_jobs(_run_id(src), src, [other])

    # Comes back with updated description — reappeared takes priority over changed
    updated = ScrapedJob(
        title="Analyst", organization="Acme",
        source_url=job_url, raw_description="New description after repost.",
    )
    store_jobs(_run_id(src), src, [updated])
    assert _lifecycle(src.id, job_url) == "reappeared"
    get_settings.cache_clear()


# ── touch_source_jobs ─────────────────────────────────────────────────────────

def test_touch_source_jobs_resets_missed_scans(tmp_path, monkeypatch):
    src = _source(tmp_path, monkeypatch)
    job_url = "https://jobs.example.com/1"
    other = _job(url="https://jobs.example.com/other")

    store_jobs(_run_id(src), src, [_job(url=job_url)])
    store_jobs(_run_id(src), src, [other])   # job/1 missed once

    assert _missed(src.id, job_url) == 1
    touch_source_jobs(src.id, {job_url})
    assert _missed(src.id, job_url) == 0
    get_settings.cache_clear()


def test_touch_source_jobs_sets_active(tmp_path, monkeypatch):
    src = _source(tmp_path, monkeypatch)
    job_url = "https://jobs.example.com/1"
    other = _job(url="https://jobs.example.com/other")

    store_jobs(_run_id(src), src, [_job(url=job_url)])
    for _ in range(_PROBABLY_CLOSED_THRESHOLD):
        store_jobs(_run_id(src), src, [other])

    assert _lifecycle(src.id, job_url) == "probably_closed"
    touch_source_jobs(src.id, {job_url})
    assert _lifecycle(src.id, job_url) == "active"
    get_settings.cache_clear()


def test_touch_does_not_revive_dead_jobs(tmp_path, monkeypatch):
    src = _source(tmp_path, monkeypatch)
    job_url = "https://jobs.example.com/1"
    other = _job(url="https://jobs.example.com/other")

    store_jobs(_run_id(src), src, [_job(url=job_url)])
    for _ in range(_DEAD_THRESHOLD):
        store_jobs(_run_id(src), src, [other])

    assert _lifecycle(src.id, job_url) == "dead"
    touch_source_jobs(src.id, {job_url})
    # dead jobs have is_live=0, touch only affects live jobs
    assert _lifecycle(src.id, job_url) == "dead"
    get_settings.cache_clear()


def test_touch_source_jobs_only_touches_seen_urls(tmp_path, monkeypatch):
    src = _source(tmp_path, monkeypatch)
    stale_url = "https://jobs.example.com/stale"
    current_url = "https://jobs.example.com/current"

    store_jobs(_run_id(src), src, [
        _job(url=stale_url, title="Stale role"),
        _job(url=current_url, title="Current role"),
    ])
    store_jobs(_run_id(src), src, [_job(url=current_url, title="Current role")])

    assert _missed(src.id, stale_url) == 1
    assert _missed(src.id, current_url) == 0

    touch_source_jobs(src.id, {current_url})

    assert _missed(src.id, stale_url) == 1
    assert _missed(src.id, current_url) == 0
    get_settings.cache_clear()
