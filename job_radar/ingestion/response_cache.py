"""URL-set hashing cache for skipping unchanged sources.

After a successful fetch we hash the set of returned source URLs.  If the
hash matches the previous run the page hasn't changed, so we skip
normalize / score / upsert and just touch last_seen_at on the existing rows.

Cache file: {data_dir}/response_cache.json
  {"source_id": {"url_hash": "abc123de", "checked_at": "2026-06-01T12:00:00"}}

Thread-safety: a per-process lock guards read-modify-write so concurrent
source threads don't corrupt the file.
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime
from pathlib import Path

from job_radar.config.settings import get_settings

_LOCK = threading.Lock()
_FILENAME = "response_cache.json"


def _cache_path() -> Path:
    return get_settings().data_dir / _FILENAME


def _load() -> dict:
    p = _cache_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _save(data: dict) -> None:
    _cache_path().write_text(json.dumps(data, indent=2))


def compute_url_hash(seen_urls: set[str]) -> str:
    return hashlib.sha256("\n".join(sorted(seen_urls)).encode()).hexdigest()[:16]


def is_unchanged(source_id: str, url_hash: str) -> bool:
    with _LOCK:
        return _load().get(source_id, {}).get("url_hash") == url_hash


def update(source_id: str, url_hash: str) -> None:
    with _LOCK:
        data = _load()
        data[source_id] = {
            "url_hash":   url_hash,
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        }
        _save(data)


def invalidate(source_id: str) -> None:
    """Force re-processing on next run (e.g. after a source URL change)."""
    with _LOCK:
        data = _load()
        data.pop(source_id, None)
        _save(data)
