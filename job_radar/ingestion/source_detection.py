"""Detect common career-page platforms from pasted URLs."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from job_radar.ingestion.models import SourceDetection


def _host(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc.lower()


def _path(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.path.strip("/")


_RSS_EXTENSIONS = re.compile(r"\.(rss|xml|atom)$", re.IGNORECASE)
_RSS_PATH_HINTS = re.compile(r"/(feed|rss|atom)(/|$)", re.IGNORECASE)
_RSS_QUERY_HINTS = re.compile(r"(^|&)(feed|format)=(rss|atom|xml)", re.IGNORECASE)


def _is_rss_url(url: str) -> bool:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    path = parsed.path
    return bool(
        _RSS_EXTENSIONS.search(path)
        or _RSS_PATH_HINTS.search(path)
        or _RSS_QUERY_HINTS.search(parsed.query)
    )


def detect_source(url: str) -> SourceDetection:
    host = _host(url)
    path = _path(url)
    clean_url = url.strip()

    if _is_rss_url(url):
        return SourceDetection(
            "rss",
            "rss_atom",
            "RSS/Atom feed detected",
            {"feed_url": clean_url},
        )

    if "greenhouse.io" in host or "job-boards.greenhouse.io" in host:
        token = path.split("/")[0] if path else ""
        return SourceDetection("greenhouse", "api", "Greenhouse board detected", {"board_token": token})

    if "jobs.lever.co" in host:
        company = path.split("/")[0] if path else ""
        return SourceDetection("lever", "api", "Lever board detected", {"company": company})

    if host.endswith(".jobs.personio.com"):
        slug = host.split(".")[0]
        return SourceDetection("personio", "xml", "Personio XML feed detected", {"slug": slug})

    if "ashbyhq.com" in host or "jobs.ashbyhq.com" in host or "jobs.ashby.io" in host:
        parts = [p for p in path.split("/") if p]
        slug = parts[-1] if parts else host.split(".")[0]
        return SourceDetection("ashby", "api", "Ashby board detected", {"org_slug": slug})

    if "apply.workable.com" in host:
        slug = path.split("/")[0] if path else ""
        return SourceDetection("workable", "api", "Workable board detected", {"slug": slug})

    if "smartrecruiters.com" in host:
        parts = [p for p in path.split("/") if p]
        company_id = parts[0] if parts else ""
        return SourceDetection(
            "smartrecruiters",
            "api",
            "SmartRecruiters board detected",
            {"company_id": company_id},
        )

    if "workdayjobs.com" in host or re.search(r"\.wd\d+\.myworkdayjobs\.com$", host):
        return SourceDetection(
            "workday",
            "manual_watch",
            "Workday detected; deferred for v0.1 unless a stable endpoint is configured",
            {"url": clean_url},
            manual_review_needed=True,
        )

    return SourceDetection(
        "generic_static",
        "static_html",
        "No known platform detected; use best-effort static HTML or manual watch",
        {"url": clean_url},
        manual_review_needed=True,
    )
