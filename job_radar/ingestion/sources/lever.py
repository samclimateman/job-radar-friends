"""Lever public postings scraper."""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from job_radar.ingestion.models import ScrapedJob

API_URL = "https://api.lever.co/v0/postings/{company}"
TIMEOUT = 20


class LeverScraper:
    platform = "lever"

    def fetch(self, *, company: str, organization: str | None = None) -> list[ScrapedJob]:
        if not company:
            raise ValueError("Lever company is required")

        response = requests.get(
            API_URL.format(company=company),
            params={"mode": "json"},
            timeout=TIMEOUT,
            headers={"User-Agent": "job-radar/0.1"},
        )
        if response.status_code == 404:
            raise RuntimeError(f"Lever company not found: {company} (404)")
        response.raise_for_status()

        jobs = []
        for raw in response.json():
            title = (raw.get("text") or "").strip()
            source_url = (raw.get("hostedUrl") or raw.get("applyUrl") or "").strip()
            if not title or not source_url:
                continue
            categories = raw.get("categories") or {}
            jobs.append(
                ScrapedJob(
                    title=title,
                    organization=organization,
                    source_url=source_url,
                    source_job_id=str(raw.get("id") or ""),
                    location=categories.get("location"),
                    remote_status=_remote_status(categories),
                    raw_description=_description(raw),
                    raw_payload=raw,
                )
            )
        return jobs


def _remote_status(categories: dict) -> str | None:
    location = (categories.get("location") or "").lower()
    if "remote" in location:
        return "remote"
    return None


def _description(raw: dict) -> str:
    parts = [
        raw.get("descriptionPlain") or _html_to_text(raw.get("description") or ""),
    ]
    for list_item in raw.get("lists") or []:
        heading = list_item.get("text") or ""
        content = " ".join(item.get("text", "") for item in list_item.get("content") or [])
        parts.append(f"{heading} {content}".strip())
    return " ".join(p for p in parts if p).strip()


def _html_to_text(html: str) -> str:
    return " ".join(BeautifulSoup(html or "", "html.parser").get_text(" ").split())
