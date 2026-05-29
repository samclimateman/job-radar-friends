"""Greenhouse public job board scraper."""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from job_radar.ingestion.models import ScrapedJob

API_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
TIMEOUT = 20


class GreenhouseScraper:
    platform = "greenhouse"

    def fetch(self, *, board_token: str, organization: str | None = None) -> list[ScrapedJob]:
        if not board_token:
            raise ValueError("Greenhouse board_token is required")

        response = requests.get(
            API_URL.format(board_token=board_token),
            params={"content": "true"},
            timeout=TIMEOUT,
            headers={"User-Agent": "job-radar/0.1"},
        )
        if response.status_code == 404:
            raise RuntimeError(f"Greenhouse board not found: {board_token} (404)")
        response.raise_for_status()

        jobs = []
        for raw in response.json().get("jobs", []):
            title = (raw.get("title") or "").strip()
            source_url = (raw.get("absolute_url") or "").strip()
            if not title or not source_url:
                continue
            jobs.append(
                ScrapedJob(
                    title=title,
                    organization=organization,
                    source_url=source_url,
                    source_job_id=str(raw.get("id") or ""),
                    location=(raw.get("location") or {}).get("name"),
                    raw_description=_html_to_text(raw.get("content") or ""),
                    raw_payload=raw,
                )
            )
        return jobs


def _html_to_text(html: str) -> str:
    return " ".join(BeautifulSoup(html or "", "html.parser").get_text(" ").split())
