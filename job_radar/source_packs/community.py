"""Client for the shared community source registry.

The registry (https://github.com/samclimateman/job-radar-sources) is a public
repo of declarative source packs — org name, careers URL, platform, nothing
executable and nothing personal. The app fetches its generated ``index.json``,
caches it in the user data dir, and consults it when the user adds an
organization. Sharing goes the other way: a working local source becomes a
prefilled GitHub issue on the registry, which the user reviews and submits in
their browser.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlparse

import requests

from job_radar.config.settings import get_settings

REGISTRY_REPO_URL = "https://github.com/samclimateman/job-radar-sources"
REGISTRY_INDEX_URL = (
    "https://raw.githubusercontent.com/samclimateman/job-radar-sources/main/index.json"
)
FETCH_TIMEOUT_SECONDS = 10
CACHE_TTL = timedelta(hours=12)

# Hosts where the careers URL lives on the ATS, so the org's own domain
# cannot be derived from it. Bare domains: they must survive prefix
# stripping in normalize_domain (jobs.lever.co -> lever.co).
_ATS_HOST_MARKERS = (
    "greenhouse.io",
    "lever.co",
    "personio.com",
    "ashbyhq.com",
    "ashby.io",
    "workable.com",
    "smartrecruiters.com",
    "myworkdayjobs.com",
    "workdayjobs.com",
)
_GENERIC_HOST_PREFIXES = ("www.", "jobs.", "careers.", "apply.", "recruit.")

_PACK_REQUIRED_KEYS = {"domain", "organization", "careers_url", "platform"}


def _cache_path() -> Path:
    return get_settings().data_dir / "community_index.json"


def _meta_path() -> Path:
    return get_settings().data_dir / "community_index.meta.json"


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _valid_packs(index: dict) -> list[dict]:
    packs = index.get("packs")
    if not isinstance(packs, list):
        return []
    return [
        pack
        for pack in packs
        if isinstance(pack, dict)
        and _PACK_REQUIRED_KEYS.issubset(pack)
        and all(isinstance(pack[key], str) and pack[key] for key in _PACK_REQUIRED_KEYS)
        and str(pack["careers_url"]).startswith("https://")
    ]


def load_cached_index() -> dict | None:
    """Return the cached index, or None if never fetched (or unreadable)."""
    index = _read_json(_cache_path())
    if index is None or index.get("schema_version") != 1:
        return None
    return index


def cache_meta() -> dict:
    return _read_json(_meta_path()) or {}


def _cache_is_fresh(meta: dict) -> bool:
    fetched_at = meta.get("fetched_at")
    if not isinstance(fetched_at, str):
        return False
    try:
        fetched = datetime.fromisoformat(fetched_at)
    except ValueError:
        return False
    return datetime.now(UTC) - fetched < CACHE_TTL


def refresh_index(*, force: bool = False) -> dict | None:
    """Fetch the registry index, honoring the cache TTL and ETags.

    Never raises on network trouble — returns whatever cache exists instead,
    so the app works identically offline.
    """
    cached = load_cached_index()
    meta = cache_meta()
    if cached is not None and not force and _cache_is_fresh(meta):
        return cached

    headers = {}
    if cached is not None and isinstance(meta.get("etag"), str):
        headers["If-None-Match"] = meta["etag"]
    try:
        response = requests.get(
            REGISTRY_INDEX_URL, headers=headers, timeout=FETCH_TIMEOUT_SECONDS
        )
    except requests.RequestException:
        return cached

    now = datetime.now(UTC).isoformat()
    if response.status_code == 304 and cached is not None:
        _write_meta({"etag": meta.get("etag"), "fetched_at": now})
        return cached
    if response.status_code != 200:
        return cached

    try:
        index = response.json()
    except ValueError:
        return cached
    if not isinstance(index, dict) or index.get("schema_version") != 1:
        return cached

    index["packs"] = _valid_packs(index)
    index["pack_count"] = len(index["packs"])

    get_settings().data_dir.mkdir(parents=True, exist_ok=True)
    _cache_path().write_text(json.dumps(index, ensure_ascii=False))
    _write_meta({"etag": response.headers.get("ETag"), "fetched_at": now})
    return index


def _write_meta(meta: dict) -> None:
    get_settings().data_dir.mkdir(parents=True, exist_ok=True)
    _meta_path().write_text(json.dumps(meta))


def normalize_domain(value: str) -> str:
    """Reduce a URL, hostname, or bare domain to a comparable org domain."""
    candidate = (value or "").strip().lower()
    if not candidate:
        return ""
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    host = (urlparse(candidate).hostname or "").strip(".")
    if not host or not re.fullmatch(r"[a-z0-9.-]+", host):
        return ""
    changed = True
    while changed:
        changed = False
        for prefix in _GENERIC_HOST_PREFIXES:
            if host.startswith(prefix) and host.count(".") >= 2:
                host = host[len(prefix):]
                changed = True
    return host


def org_domain_from_url(url: str) -> str:
    """Derive the org's own domain from a careers URL, or '' if ATS-hosted."""
    host = normalize_domain(url)
    if not host or any(marker in host for marker in _ATS_HOST_MARKERS):
        return ""
    return host


def _looks_like_domain_or_url(query: str) -> bool:
    return "://" in query or bool(re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}(/.*)?", query.strip().lower()))


def lookup(query: str, index: dict | None = None, *, limit: int = 5) -> list[dict]:
    """Match a typed org name, domain, or pasted URL against the index."""
    query = (query or "").strip()
    if len(query) < 3:
        return []
    if index is None:
        index = load_cached_index()
    if index is None:
        return []
    packs = _valid_packs(index)

    if _looks_like_domain_or_url(query):
        domain = normalize_domain(query)
        if not domain:
            return []
        exact = [pack for pack in packs if pack["domain"] == domain]
        if exact:
            return exact[:limit]
        return [
            pack
            for pack in packs
            if pack["domain"].endswith(f".{domain}") or domain.endswith(f".{pack['domain']}")
        ][:limit]

    needle = query.casefold()
    tokens = [token for token in re.split(r"[^a-z0-9]+", needle) if len(token) >= 3]
    scored: list[tuple[int, str, dict]] = []
    for pack in packs:
        name = str(pack["organization"]).casefold()
        domain_base = pack["domain"].split(".")[0]
        if needle == name:
            score = 100
        elif needle in name or name in needle:
            score = 80
        elif tokens and all(token in name or token in domain_base for token in tokens):
            score = 60
        elif tokens and any(token == domain_base for token in tokens):
            score = 50
        else:
            continue
        scored.append((score, name, pack))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [pack for _, _, pack in scored[:limit]]


def build_share_payload(
    *,
    url: str,
    organization: str | None,
    platform: str | None,
    last_successful_at: str | None,
    confidence_label: str | None = None,
) -> dict:
    """Build the pack JSON for sharing a working local source.

    The domain is derived from the URL when it is org-hosted; for ATS-hosted
    URLs it is left empty and the UI asks the user to fill it in.
    """
    last_verified = datetime.now(UTC).date().isoformat()
    if last_successful_at:
        match = re.match(r"\d{4}-\d{2}-\d{2}", last_successful_at)
        if match:
            last_verified = match.group(0)
    payload: dict = {
        "schema_version": 1,
        "domain": org_domain_from_url(url),
        "organization": (organization or "").strip(),
        "careers_url": url,
        "platform": platform or "generic_static",
        "last_verified": last_verified,
    }
    if confidence_label in {"low", "medium", "high"}:
        payload["confidence"] = confidence_label
    return payload


def share_issue_url(payload: dict) -> str:
    """Prefilled 'Submit a source' issue URL on the registry repo."""
    title = f"[Source] {payload.get('organization', '').strip()}".strip()
    pack_json = json.dumps(payload, indent=2, ensure_ascii=False)
    return (
        f"{REGISTRY_REPO_URL}/issues/new"
        f"?template=submit-source.yml"
        f"&title={quote(title)}"
        f"&pack={quote(pack_json)}"
    )
