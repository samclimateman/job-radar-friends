"""Ashby public postings scraper."""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from job_radar.ingestion.models import ScrapedJob

API_URL = "https://api.ashbyhq.com/posting-api/job-board/{org_slug}"
TIMEOUT = 20


class AshbyScraper:
    platform = "ashby"

    def fetch(self, *, org_slug: str, organization: str | None = None) -> list[ScrapedJob]:
        if not org_slug:
            raise ValueError("Ashby org_slug is required")

        response = requests.get(
            API_URL.format(org_slug=org_slug),
            timeout=TIMEOUT,
            headers={"User-Agent": "job-radar/0.1", "Accept": "application/json"},
        )
        if response.status_code == 404:
            raise RuntimeError(f"Ashby organization not found: {org_slug} (404)")
        response.raise_for_status()
        payload = response.json()
        all_jobs = payload.get("jobs") or payload.get("results") or []

        jobs = []
        for raw in all_jobs:
            title = (raw.get("title") or "").strip()
            source_url = raw.get("jobUrl") or raw.get("applyUrl") or ""
            if not title or not source_url:
                continue
            jobs.append(
                ScrapedJob(
                    title=title,
                    organization=organization,
                    source_url=source_url,
                    source_job_id=str(raw.get("id") or ""),
                    location=_location(raw),
                    remote_status=_remote_status(raw),
                    raw_description=raw.get("descriptionPlain")
                    or _html_to_text(raw.get("descriptionHtml") or ""),
                    raw_payload=raw,
                )
            )
        return jobs


def _remote_status(raw: dict) -> str | None:
    if raw.get("isRemote") is True:
        return "remote"
    if raw.get("isRemote") is False:
        return "onsite"
    if str(raw.get("workplaceType") or "").lower() == "remote":
        return "remote"
    return None


def _location(raw: dict) -> str | None:
    location = raw.get("location")
    if isinstance(location, str):
        return location
    if isinstance(location, dict):
        return location.get("location") or location.get("name")
    address = ((raw.get("address") or {}).get("postalAddress") or {})
    parts = [address.get("addressLocality"), address.get("addressRegion"), address.get("addressCountry")]
    return ", ".join(str(part).strip() for part in parts if part) or None


def _html_to_text(value: str) -> str:
    return " ".join(BeautifulSoup(value or "", "html.parser").get_text(" ").split())
