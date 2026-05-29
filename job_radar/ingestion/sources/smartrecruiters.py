"""SmartRecruiters public API scraper."""

from __future__ import annotations

import re

import requests

from job_radar.ingestion.models import ScrapedJob

LIST_URL = "https://api.smartrecruiters.com/v1/companies/{company_id}/postings"
DETAIL_URL = "https://api.smartrecruiters.com/v1/companies/{company_id}/postings/{job_id}"
PAGE_LIMIT = 100
TIMEOUT = 20
MAX_DETAIL_FETCHES = 25
TAG_RE = re.compile(r"<[^>]+>")


class SmartRecruitersScraper:
    platform = "smartrecruiters"

    def fetch(
        self,
        *,
        company_id: str,
        organization: str | None = None,
        department_filter: str | None = None,
    ) -> list[ScrapedJob]:
        if not company_id:
            raise ValueError("SmartRecruiters company_id is required")

        postings = self._fetch_all(company_id)
        if department_filter:
            needle = department_filter.lower()
            postings = [
                posting
                for posting in postings
                if needle in ((posting.get("department") or {}).get("label") or "").lower()
            ]

        jobs = []
        for index, posting in enumerate(postings):
            parsed = self._parse_posting(
                posting,
                company_id,
                organization,
                fetch_detail=index < MAX_DETAIL_FETCHES,
            )
            if parsed:
                jobs.append(parsed)
        return jobs

    def _fetch_all(self, company_id: str) -> list[dict]:
        postings: list[dict] = []
        offset = 0
        while True:
            response = requests.get(
                LIST_URL.format(company_id=company_id),
                headers={"User-Agent": "job-radar/0.1", "Accept": "application/json"},
                params={"limit": PAGE_LIMIT, "offset": offset},
                timeout=TIMEOUT,
            )
            if response.status_code == 404:
                raise RuntimeError(f"SmartRecruiters company not found: {company_id} (404)")
            response.raise_for_status()
            data = response.json()
            batch = data.get("content", [])
            postings.extend(batch)
            offset += len(batch)
            if not batch or offset >= data.get("totalFound", 0):
                break
        return postings

    def _parse_posting(
        self,
        posting: dict,
        company_id: str,
        organization: str | None,
        *,
        fetch_detail: bool = True,
    ) -> ScrapedJob | None:
        job_id = posting.get("id")
        title = (posting.get("name") or "").strip()
        if not job_id or not title:
            return None

        detail = posting
        if fetch_detail:
            try:
                response = requests.get(
                    DETAIL_URL.format(company_id=company_id, job_id=job_id),
                    headers={"User-Agent": "job-radar/0.1", "Accept": "application/json"},
                    timeout=TIMEOUT,
                )
                response.raise_for_status()
                detail = response.json()
            except requests.RequestException:
                detail = posting

        source_url = detail.get("applyUrl") or detail.get("postingUrl")
        if not source_url:
            source_url = f"https://careers.smartrecruiters.com/{company_id}/{job_id}"

        return ScrapedJob(
            title=title,
            organization=organization,
            source_url=source_url,
            source_job_id=str(job_id),
            location=_location(posting.get("location")),
            raw_description=_description(detail) or title,
            raw_payload={"list": posting, "detail": detail},
        )


def _description(detail: dict) -> str:
    sections = (detail.get("jobAd") or {}).get("sections") or {}
    parts = []
    for key in ("jobDescription", "qualifications", "additionalInformation"):
        text = (sections.get(key) or {}).get("text") or ""
        cleaned = " ".join(TAG_RE.sub(" ", text).split())
        if cleaned:
            parts.append(cleaned)
    return " ".join(parts)


def _location(raw_location: dict | None) -> str | None:
    if not raw_location:
        return None
    if raw_location.get("remote"):
        return "Remote"
    parts = [raw_location.get("city"), raw_location.get("country") or raw_location.get("countryCode")]
    return ", ".join(str(part).strip() for part in parts if part) or None
