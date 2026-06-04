"""Personio XML feed scraper."""

from __future__ import annotations

from typing import Any

import requests
from bs4 import BeautifulSoup
from defusedxml.ElementTree import ParseError, fromstring

from job_radar.ingestion.models import ScrapedJob

XML_FEED = "https://{slug}.jobs.personio.com/xml"
JOB_URL = "https://{slug}.jobs.personio.com/job/{job_id}"
TIMEOUT = 20


class PersonioScraper:
    platform = "personio"

    def fetch(self, *, slug: str, organization: str | None = None) -> list[ScrapedJob]:
        if not slug:
            raise ValueError("Personio slug is required")

        response = requests.get(
            XML_FEED.format(slug=slug),
            timeout=TIMEOUT,
            headers={"User-Agent": "job-radar/0.1", "Accept": "application/xml, text/xml"},
        )
        if response.status_code == 404:
            raise RuntimeError(f"Personio feed not found: {slug} (404)")
        response.raise_for_status()

        try:
            root = fromstring(response.content)
        except ParseError as exc:
            raise RuntimeError(f"Failed to parse Personio XML for {slug}: {exc}") from exc

        jobs = []
        for position in root.findall("position"):
            title = (position.findtext("name") or "").strip()
            job_id = position.findtext("id") or ""
            if not title or not job_id:
                continue
            office = position.findtext("office") or ""
            jobs.append(
                ScrapedJob(
                    title=title,
                    organization=organization,
                    source_url=JOB_URL.format(slug=slug, job_id=job_id),
                    source_job_id=job_id,
                    location=office.strip() or None,
                    remote_status=_remote_status(office),
                    raw_description=_description(position),
                    raw_payload=_raw_payload(position),
                )
            )
        return jobs


def _remote_status(office: str) -> str | None:
    lower = office.lower()
    if "remote" in lower:
        return "remote"
    if "hybrid" in lower:
        return "hybrid"
    return None


def _description(position: Any) -> str:
    parts = []
    for key in ("department", "schedule", "seniority", "yearsOfExperience", "keywords"):
        value = position.findtext(key)
        if value:
            parts.append(f"{key}: {value}")
    for section in position.findall(".//jobDescription"):
        heading = (section.findtext("name") or "").strip()
        value = section.findtext("value") or ""
        text = " ".join(BeautifulSoup(value, "html.parser").get_text(" ").split())
        if text:
            parts.append(f"{heading}: {text}" if heading else text)
    return "\n".join(parts).strip() or (position.findtext("name") or "")


def _raw_payload(position: Any) -> dict:
    return {child.tag: child.text for child in position if child.text}
