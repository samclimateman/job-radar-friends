"""Detect common career-page platforms from pasted URLs."""

from __future__ import annotations

import re
from ipaddress import ip_address
from urllib.parse import urlparse

from job_radar.ingestion.models import SourceDetection

LOCAL_HOSTS = {"localhost"}
ALLOWED_SCHEMES = {"http", "https"}


class SourceUrlError(ValueError):
    """Raised when a pasted source URL is unsafe or unsupported."""


def normalize_source_url(url: str) -> str:
    """Return a safe, absolute HTTP(S) source URL."""
    candidate = (url or "").strip()
    if not candidate:
        raise SourceUrlError("Source URL cannot be empty")
    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise SourceUrlError("Source URL must start with http:// or https://")
    if not parsed.hostname:
        raise SourceUrlError("Source URL must include a hostname")
    if parsed.username or parsed.password:
        raise SourceUrlError("Source URL must not include credentials")

    host = parsed.hostname.lower().strip(".")
    if host in LOCAL_HOSTS or host.endswith(".localhost") or host.endswith(".local"):
        raise SourceUrlError("Localhost and local-network source URLs are not supported")
    try:
        parsed_ip = ip_address(host)
    except ValueError:
        pass
    else:
        if (
            parsed_ip.is_private
            or parsed_ip.is_loopback
            or parsed_ip.is_link_local
            or parsed_ip.is_reserved
            or parsed_ip.is_multicast
            or parsed_ip.is_unspecified
        ):
            raise SourceUrlError("Private or local-network source URLs are not supported")

    return parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower(), fragment="").geturl()


def _host(url: str) -> str:
    parsed = urlparse(normalize_source_url(url))
    return parsed.netloc.lower()


def _path(url: str) -> str:
    parsed = urlparse(normalize_source_url(url))
    return parsed.path.strip("/")


_RSS_EXTENSIONS = re.compile(r"\.(rss|xml|atom)$", re.IGNORECASE)
_RSS_PATH_HINTS = re.compile(r"/(feed|rss|atom)(/|$)", re.IGNORECASE)
_RSS_QUERY_HINTS = re.compile(r"(^|&)(feed|format)=(rss|atom|xml)", re.IGNORECASE)


def _is_rss_url(url: str) -> bool:
    parsed = urlparse(normalize_source_url(url))
    path = parsed.path
    return bool(
        _RSS_EXTENSIONS.search(path)
        or _RSS_PATH_HINTS.search(path)
        or _RSS_QUERY_HINTS.search(parsed.query)
    )


def detect_source(url: str) -> SourceDetection:
    clean_url = normalize_source_url(url)
    host = _host(url)
    path = _path(url)

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
