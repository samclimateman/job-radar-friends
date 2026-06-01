"""RSS/Atom feed connector."""

from __future__ import annotations

import re
from datetime import datetime

import feedparser

from job_radar.ingestion.models import ScrapedJob

# Default keywords that suggest a feed item is a job posting
_DEFAULT_INCLUDE = [
    "job", "jobs", "vacancy", "vacancies", "career", "careers",
    "position", "positions", "hiring", "opportunity", "role", "opening",
]

# Default keywords that suggest a feed item is NOT a job
_DEFAULT_EXCLUDE = [
    "event", "webinar", "newsletter", "blog", "press release",
    "report", "publication", "podcast", "video", "announcement",
    "procurement", "tender", "rfp",
]


class RssScraper:
    """Parse RSS/Atom feeds and return job candidates."""

    requires_browser = False

    def fetch(
        self,
        organization: str | None = None,
        feed_url: str = "",
        include_keywords: list[str] | None = None,
        exclude_keywords: list[str] | None = None,
        apply_filters: bool = True,
        **_kwargs,
    ) -> list[ScrapedJob]:
        if not feed_url:
            raise ValueError("RssScraper requires feed_url in source config")

        feed = feedparser.parse(feed_url)
        if not feed.entries and feed.get("bozo"):
            exc = feed.get("bozo_exception") or "unknown parse error"
            raise RuntimeError(f"Failed to parse feed: {exc}")
        if not feed.entries and not feed.get("feed"):
            raise RuntimeError("Failed to parse feed: no entries and no feed metadata found")

        include = [k.lower() for k in (include_keywords if include_keywords is not None else _DEFAULT_INCLUDE)]
        exclude = [k.lower() for k in (exclude_keywords if exclude_keywords is not None else _DEFAULT_EXCLUDE)]

        jobs: list[ScrapedJob] = []
        for entry in feed.entries:
            title = _text(entry.get("title", ""))
            link = entry.get("link", "")
            if not title or not link:
                continue

            summary = _text(entry.get("summary") or entry.get("content", [{}])[0].get("value", ""))
            guid = entry.get("id") or entry.get("guid") or link

            if apply_filters and not _passes_filters(title, summary, include, exclude):
                continue

            published = _parse_date(entry)

            jobs.append(ScrapedJob(
                title=title,
                organization=organization,
                source_url=link,
                source_job_id=guid,
                raw_description=summary,
                deadline=published,
            ))

        return jobs


def _text(value: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    clean = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(clean.split()).strip()


def _passes_filters(title: str, summary: str, include: list[str], exclude: list[str]) -> bool:
    haystack = (title + " " + summary).lower()
    if any(kw in haystack for kw in exclude):
        return False
    if include:
        return any(kw in haystack for kw in include)
    return True


def _parse_date(entry) -> str | None:
    for field in ("published_parsed", "updated_parsed"):
        val = entry.get(field)
        if val:
            try:
                return datetime(*val[:6]).strftime("%Y-%m-%d")
            except Exception:
                pass
    return None
