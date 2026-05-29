from unittest.mock import patch

from job_radar.config.settings import get_settings
from job_radar.db.client import execute
from job_radar.ingestion.runner import _fetch_jobs, run_ingestion
from job_radar.ingestion.source_store import StoredSource, add_source
from job_radar.ingestion.sources.playwright_base import PlaywrightBaseScraper
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

            raise requests.HTTPError(f"{self.status_code} error")


def test_greenhouse_source_ingests_jobs_and_updates_health(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    source = add_source("https://job-boards.greenhouse.io/acme", organization="Acme")

    payload = {
        "jobs": [
            {
                "id": 123,
                "title": "Policy Analyst",
                "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/123",
                "location": {"name": "Brussels"},
                "content": "<p>Energy security role.</p>",
            }
        ]
    }

    with patch("job_radar.ingestion.sources.greenhouse.requests.get") as mock_get:
        mock_get.return_value = MockResponse(payload)
        result = run_ingestion(source_id=source.id)

    assert result.sources_succeeded == 1
    assert result.jobs_found == 1
    assert result.new_jobs_found == 1

    jobs = execute("SELECT * FROM jobs")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Policy Analyst"
    assert jobs[0]["source_url"] == "https://job-boards.greenhouse.io/acme/jobs/123"
    assert jobs[0]["raw_payload"]

    health = execute("SELECT * FROM source_health WHERE source_id = ?", (source.id,))[0]
    assert health["jobs_found"] == 1
    assert health["new_jobs_found"] == 1
    assert health["error_status"] is None
    get_settings.cache_clear()


def test_ingestion_applies_active_rubric_score(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    save_rubric(target_locations="Brussels", role_types="Policy", positive_keywords="Energy security")
    source = add_source("https://job-boards.greenhouse.io/acme", organization="Acme")

    payload = {
        "jobs": [
            {
                "id": 123,
                "title": "Policy Analyst",
                "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/123",
                "location": {"name": "Brussels"},
                "content": "<p>Energy security role.</p>",
            }
        ]
    }

    with patch("job_radar.ingestion.sources.greenhouse.requests.get") as mock_get:
        mock_get.return_value = MockResponse(payload)
        run_ingestion(source_id=source.id)

    score = execute("SELECT score, explanation_json FROM job_scores")[0]
    assert score["score"] > 0
    assert "matched location: Brussels" in score["explanation_json"]
    get_settings.cache_clear()


def test_runner_records_failure_without_fabricating_jobs(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    source = add_source("https://job-boards.greenhouse.io/missing", organization="Missing")

    with patch("job_radar.ingestion.sources.greenhouse.requests.get") as mock_get:
        mock_get.return_value = MockResponse({}, status_code=404)
        result = run_ingestion(source_id=source.id)

    assert result.sources_failed == 1
    assert result.jobs_found == 0
    assert execute("SELECT * FROM jobs") == []

    health = execute("SELECT * FROM source_health WHERE source_id = ?", (source.id,))[0]
    assert "404" in health["error_status"]
    assert health["likely_broken_url"] == 1
    get_settings.cache_clear()


def test_browser_scrapers_are_throttled(monkeypatch):
    source = StoredSource(
        id="source_1",
        url="https://example.org/jobs",
        organization="Example",
        platform="browser_test",
        parser_type="browser",
        config={},
        status="active",
        detection_note="test",
    )
    calls = []

    class RecordingSemaphore:
        active = False

        def __enter__(self):
            self.active = True

        def __exit__(self, exc_type, exc, tb):
            self.active = False

    semaphore = RecordingSemaphore()

    class BrowserScraper(PlaywrightBaseScraper):
        def fetch(self, *, organization):
            calls.append(semaphore.active)
            return []

    monkeypatch.setattr("job_radar.ingestion.runner._browser_sem", semaphore)

    assert BrowserScraper.requires_browser is True
    assert _fetch_jobs(BrowserScraper, source) == []
    assert calls == [True]


def test_http_scrapers_do_not_use_browser_throttle(monkeypatch):
    source = StoredSource(
        id="source_1",
        url="https://example.org/jobs",
        organization="Example",
        platform="http_test",
        parser_type="api",
        config={},
        status="active",
        detection_note="test",
    )
    calls = []

    class RecordingSemaphore:
        active = False

        def __enter__(self):
            self.active = True

        def __exit__(self, exc_type, exc, tb):
            self.active = False

    semaphore = RecordingSemaphore()

    class HttpScraper:
        def fetch(self, *, organization):
            calls.append(semaphore.active)
            return []

    monkeypatch.setattr("job_radar.ingestion.runner._browser_sem", semaphore)

    assert _fetch_jobs(HttpScraper, source) == []
    assert calls == [False]
