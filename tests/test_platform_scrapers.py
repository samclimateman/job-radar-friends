from unittest.mock import patch

from job_radar.ingestion.sources.ashby import AshbyScraper
from job_radar.ingestion.sources.personio import PersonioScraper
from job_radar.ingestion.sources.smartrecruiters import SmartRecruitersScraper
from job_radar.ingestion.sources.workable import WorkableScraper


class MockResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.content = payload if isinstance(payload, bytes) else b""

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"{self.status_code} error")


def test_workable_scraper_parses_widget_jobs():
    payload = {
        "jobs": [
            {
                "title": "Strategy Manager",
                "shortcode": "ABC123",
                "location": {"city": "London", "country": "United Kingdom"},
                "department": "Strategy",
                "description": "Work on market strategy.",
            }
        ]
    }

    with patch("job_radar.ingestion.sources.workable.requests.get") as mock_get:
        mock_get.return_value = MockResponse(payload)
        jobs = WorkableScraper().fetch(slug="acme", organization="Acme")

    assert len(jobs) == 1
    assert jobs[0].title == "Strategy Manager"
    assert jobs[0].location == "London, United Kingdom"
    assert jobs[0].source_url == "https://apply.workable.com/acme/j/ABC123/"


def test_ashby_scraper_parses_public_jobs():
    payload = {
        "results": [
            {
                "id": "ash-1",
                "title": "AI Strategy Lead",
                "jobUrl": "https://jobs.ashbyhq.com/acme/ash-1",
                "location": "New York",
                "isRemote": True,
                "descriptionPlain": "Lead AI strategy.",
            }
        ],
        "moreDataAvailable": False,
    }

    with patch("job_radar.ingestion.sources.ashby.requests.get") as mock_get:
        mock_get.return_value = MockResponse(payload)
        jobs = AshbyScraper().fetch(org_slug="acme", organization="Acme")

    assert len(jobs) == 1
    assert jobs[0].title == "AI Strategy Lead"
    assert jobs[0].remote_status == "remote"


def test_personio_scraper_parses_xml_feed():
    payload = b"""<?xml version="1.0" encoding="UTF-8"?>
    <workzag-jobs>
      <position>
        <id>42</id>
        <name>Policy Manager</name>
        <office>Berlin</office>
        <department>Policy</department>
        <jobDescriptions>
          <jobDescription>
            <name>Role</name>
            <value><![CDATA[<p>Work on German policy.</p>]]></value>
          </jobDescription>
        </jobDescriptions>
      </position>
    </workzag-jobs>"""

    with patch("job_radar.ingestion.sources.personio.requests.get") as mock_get:
        mock_get.return_value = MockResponse(payload)
        jobs = PersonioScraper().fetch(slug="acme", organization="Acme")

    assert len(jobs) == 1
    assert jobs[0].title == "Policy Manager"
    assert jobs[0].location == "Berlin"
    assert jobs[0].source_url == "https://acme.jobs.personio.com/job/42"


def test_smartrecruiters_scraper_fetches_detail_description():
    listing = {
        "content": [
            {
                "id": "job-1",
                "name": "Policy Lead",
                "location": {"city": "Berlin", "country": "Germany"},
            }
        ],
        "totalFound": 1,
    }
    detail = {
        "applyUrl": "https://jobs.smartrecruiters.com/acme/job-1",
        "jobAd": {
            "sections": {
                "jobDescription": {"text": "<p>Lead policy strategy.</p>"},
                "qualifications": {"text": "<p>Experience in Germany.</p>"},
            }
        },
    }

    with patch("job_radar.ingestion.sources.smartrecruiters.requests.get") as mock_get:
        mock_get.side_effect = [MockResponse(listing), MockResponse(detail)]
        jobs = SmartRecruitersScraper().fetch(company_id="Acme", organization="Acme")

    assert len(jobs) == 1
    assert jobs[0].title == "Policy Lead"
    assert jobs[0].location == "Berlin, Germany"
    assert "Lead policy strategy" in jobs[0].raw_description
