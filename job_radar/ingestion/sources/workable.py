"""Workable public widget scraper."""

from __future__ import annotations

import requests

from job_radar.ingestion.models import ScrapedJob

BASE_URL = "https://apply.workable.com/api/v1/widget/accounts/{slug}"
JOB_URL = "https://apply.workable.com/{slug}/j/{shortcode}/"
TIMEOUT = 20


class WorkableScraper:
    platform = "workable"

    def fetch(self, *, slug: str, organization: str | None = None) -> list[ScrapedJob]:
        if not slug:
            raise ValueError("Workable slug is required")

        response = requests.get(
            BASE_URL.format(slug=slug),
            timeout=TIMEOUT,
            headers={"User-Agent": "job-radar/0.1", "Accept": "application/json"},
        )
        if response.status_code == 404:
            raise RuntimeError(f"Workable account not found: {slug} (404)")
        response.raise_for_status()

        jobs = []
        for raw in response.json().get("jobs", []):
            title = (raw.get("title") or "").strip()
            shortcode = raw.get("shortcode") or ""
            source_url = raw.get("url") or JOB_URL.format(slug=slug, shortcode=shortcode)
            if not title or not source_url:
                continue
            jobs.append(
                ScrapedJob(
                    title=title,
                    organization=organization,
                    source_url=source_url,
                    source_job_id=str(shortcode),
                    location=_location(raw.get("location")),
                    remote_status="remote" if raw.get("remote") else None,
                    raw_description=_description(raw, organization),
                    raw_payload=raw,
                )
            )
        return jobs


def _location(raw_location) -> str | None:
    if isinstance(raw_location, dict):
        parts = [raw_location.get("city"), raw_location.get("country")]
        return ", ".join(part for part in parts if part) or None
    return str(raw_location) if raw_location else None


def _description(raw: dict, organization: str | None) -> str:
    description = raw.get("description") or raw.get("requirements") or ""
    if description:
        return " ".join(str(description).split())
    department = raw.get("department") or ""
    return f"{raw.get('title', '')} at {organization or 'organization'}. Department: {department}."
