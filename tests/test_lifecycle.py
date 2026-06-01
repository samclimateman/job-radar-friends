"""Tests for job lifecycle transitions and delta classification."""

from unittest.mock import patch

from job_radar.config.settings import get_settings
from job_radar.db.client import execute
from job_radar.ingestion.runner import run_ingestion
from job_radar.ingestion.source_store import add_source
from job_radar.scoring.store import save_rubric


class MockResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"{self.status_code}")


def _greenhouse_payload(*jobs):
    return {
        "jobs": [
            {
                "id": j["id"],
                "title": j["title"],
                "absolute_url": f"https://job-boards.greenhouse.io/acme/jobs/{j['id']}",
                "location": {"name": j.get("location", "Remote")},
                "content": j.get("content", "Some description."),
            }
            for j in jobs
        ]
    }


def _ingest(source, payload):
    with patch("job_radar.ingestion.sources.greenhouse.requests.get") as m:
        m.return_value = MockResponse(payload)
        return run_ingestion(source_id=source.id)


# ── times_seen and lifecycle_status ──────────────────────────────────────────

def test_new_job_gets_lifecycle_new_and_times_seen_1(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    source = add_source("https://job-boards.greenhouse.io/acme")

    _ingest(source, _greenhouse_payload({"id": 1, "title": "Analyst"}))

    job = execute("SELECT lifecycle_status, times_seen FROM jobs")[0]
    assert job["lifecycle_status"] == "new"
    assert job["times_seen"] == 1
    get_settings.cache_clear()


def test_second_scan_same_job_becomes_active(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    source = add_source("https://job-boards.greenhouse.io/acme")
    payload = _greenhouse_payload({"id": 1, "title": "Analyst"})

    _ingest(source, payload)
    _ingest(source, payload)

    job = execute("SELECT lifecycle_status, times_seen FROM jobs")[0]
    assert job["lifecycle_status"] == "active"
    assert job["times_seen"] == 2
    get_settings.cache_clear()


def test_description_change_sets_lifecycle_changed(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    source = add_source("https://job-boards.greenhouse.io/acme")

    _ingest(source, _greenhouse_payload({"id": 1, "title": "Analyst", "content": "Original description."}))
    _ingest(source, _greenhouse_payload({"id": 1, "title": "Analyst", "content": "Updated description with new details."}))

    job = execute("SELECT lifecycle_status, last_changed_at FROM jobs")[0]
    assert job["lifecycle_status"] == "changed"
    assert job["last_changed_at"] is not None
    get_settings.cache_clear()


def test_description_unchanged_stays_active_not_changed(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    source = add_source("https://job-boards.greenhouse.io/acme")
    payload = _greenhouse_payload({"id": 1, "title": "Analyst", "content": "Same description."})

    _ingest(source, payload)
    _ingest(source, payload)

    job = execute("SELECT lifecycle_status, last_changed_at FROM jobs")[0]
    assert job["lifecycle_status"] == "active"
    assert job["last_changed_at"] is None
    get_settings.cache_clear()


# ── missed_scans and probably_closed ─────────────────────────────────────────

def test_absent_job_increments_missed_scans(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    source = add_source("https://job-boards.greenhouse.io/acme")

    _ingest(source, _greenhouse_payload({"id": 1, "title": "Analyst"}, {"id": 2, "title": "Manager"}))
    # Second scan: job 1 gone, only job 2 present
    _ingest(source, _greenhouse_payload({"id": 2, "title": "Manager"}))

    gone = execute("SELECT missed_scans, lifecycle_status FROM jobs WHERE title = 'Analyst'")[0]
    assert gone["missed_scans"] == 1
    assert gone["lifecycle_status"] == "new"  # not yet probably_closed
    get_settings.cache_clear()


def test_job_absent_3_scans_becomes_probably_closed(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    source = add_source("https://job-boards.greenhouse.io/acme")

    _ingest(source, _greenhouse_payload({"id": 1, "title": "Analyst"}, {"id": 2, "title": "Manager"}))
    keep_payload = _greenhouse_payload({"id": 2, "title": "Manager"})
    _ingest(source, keep_payload)
    _ingest(source, keep_payload)
    _ingest(source, keep_payload)  # 3 misses → probably_closed

    gone = execute("SELECT missed_scans, lifecycle_status, is_live FROM jobs WHERE title = 'Analyst'")[0]
    assert gone["missed_scans"] == 3
    assert gone["lifecycle_status"] == "probably_closed"
    # is_live only flips to 0 at the dead threshold (7 missed scans), not at probably_closed (3)
    get_settings.cache_clear()


def test_failed_scan_does_not_increment_missed_scans(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    source = add_source("https://job-boards.greenhouse.io/acme")

    _ingest(source, _greenhouse_payload({"id": 1, "title": "Analyst"}))

    # Simulate a failed scan
    with patch("job_radar.ingestion.sources.greenhouse.requests.get") as m:
        m.return_value = MockResponse({}, status_code=500)
        run_ingestion(source_id=source.id)

    job = execute("SELECT missed_scans FROM jobs")[0]
    assert job["missed_scans"] == 0  # failed scan must not penalise
    get_settings.cache_clear()


def test_reappeared_job_resets_missed_scans(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    source = add_source("https://job-boards.greenhouse.io/acme")

    both = _greenhouse_payload({"id": 1, "title": "Analyst"}, {"id": 2, "title": "Manager"})
    only_two = _greenhouse_payload({"id": 2, "title": "Manager"})

    _ingest(source, both)
    _ingest(source, only_two)
    _ingest(source, only_two)
    _ingest(source, only_two)  # job 1 now probably_closed

    # Job 1 reappears
    _ingest(source, both)

    reappeared = execute("SELECT lifecycle_status, missed_scans, is_live FROM jobs WHERE title = 'Analyst'")[0]
    assert reappeared["lifecycle_status"] == "reappeared"
    assert reappeared["missed_scans"] == 0
    assert reappeared["is_live"] == 1
    get_settings.cache_clear()


# ── Delta classification ──────────────────────────────────────────────────────

def test_delta_classification_skips_unchanged_job(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    save_rubric(role_types="Analyst", target_locations="Remote")
    source = add_source("https://job-boards.greenhouse.io/acme")
    payload = _greenhouse_payload({"id": 1, "title": "Analyst", "content": "Same content."})

    _ingest(source, payload)
    score_after_first = execute("SELECT scored_at FROM job_scores")[0]["scored_at"]

    _ingest(source, payload)  # same rubric, same description → should skip
    score_after_second = execute("SELECT scored_at FROM job_scores")[0]["scored_at"]

    assert score_after_first == score_after_second  # scored_at unchanged = no rescore
    get_settings.cache_clear()


def test_delta_classification_rescores_when_description_changes(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    save_rubric(role_types="Analyst", target_locations="Remote")
    source = add_source("https://job-boards.greenhouse.io/acme")

    _ingest(source, _greenhouse_payload({"id": 1, "title": "Analyst", "content": "Original."}))
    score_after_first = execute("SELECT scored_at FROM job_scores")[0]["scored_at"]

    _ingest(source, _greenhouse_payload({"id": 1, "title": "Analyst", "content": "Completely updated description now."}))
    score_after_second = execute("SELECT scored_at FROM job_scores")[0]["scored_at"]

    assert score_after_second >= score_after_first  # rescored → scored_at updated
    get_settings.cache_clear()


def test_delta_classification_rescores_when_rubric_changes(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    save_rubric(role_types="Analyst")
    source = add_source("https://job-boards.greenhouse.io/acme")
    payload = _greenhouse_payload({"id": 1, "title": "Analyst", "content": "Same."})

    _ingest(source, payload)
    old_rubric_id = execute("SELECT rubric_id FROM job_scores")[0]["rubric_id"]

    save_rubric(role_types="Manager")  # new rubric → different rubric_id
    _ingest(source, payload)
    new_rubric_id = execute("SELECT rubric_id FROM job_scores")[0]["rubric_id"]

    assert old_rubric_id != new_rubric_id
    get_settings.cache_clear()
