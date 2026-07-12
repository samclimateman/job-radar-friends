"""Community source registry: index caching, lookup, share, and API routes."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
import requests
from fastapi import HTTPException

from job_radar.api.routers.community import (
    CommunityImport,
    community_import,
    community_lookup,
    community_share,
    community_status,
)
from job_radar.config.settings import get_settings
from job_radar.db.client import execute, init_db
from job_radar.ingestion.source_store import add_source
from job_radar.source_packs import community

INDEX = {
    "schema_version": 1,
    "generated_at": "2026-07-12T00:00:00Z",
    "pack_count": 3,
    "packs": [
        {
            "schema_version": 1,
            "domain": "bruegel.org",
            "organization": "Bruegel",
            "careers_url": "https://www.bruegel.org/careers",
            "platform": "generic_static",
            "tags": ["policy", "eu"],
            "region": "Brussels",
            "last_verified": "2026-05-29",
        },
        {
            "schema_version": 1,
            "domain": "bain.com",
            "organization": "Bain & Company",
            "careers_url": "https://www.bain.com/careers/",
            "platform": "generic_static",
            "last_verified": "2026-07-01",
        },
        {
            "schema_version": 1,
            "domain": "oxfam.org.uk",
            "organization": "Oxfam GB",
            "careers_url": "https://jobs.oxfam.org.uk/",
            "platform": "generic_static",
            "last_verified": "2026-06-01",
        },
    ],
}


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    yield tmp_path
    get_settings.cache_clear()


def _write_cache(tmp_path, index=INDEX, fetched_at=None):
    (tmp_path / "community_index.json").write_text(json.dumps(index))
    meta = {
        "etag": '"abc"',
        "fetched_at": (fetched_at or datetime.now(UTC)).isoformat(),
    }
    (tmp_path / "community_index.meta.json").write_text(json.dumps(meta))


class FakeResponse:
    def __init__(self, status_code=200, body=None, etag='"new"'):
        self.status_code = status_code
        self._body = body
        self.headers = {"ETag": etag}

    def json(self):
        if self._body is None:
            raise ValueError("no body")
        return self._body


def test_refresh_uses_fresh_cache_without_network(data_dir, monkeypatch):
    _write_cache(data_dir)

    def boom(*args, **kwargs):
        raise AssertionError("network should not be hit while cache is fresh")

    monkeypatch.setattr(community.requests, "get", boom)
    index = community.refresh_index()
    assert index["pack_count"] == 3


def test_refresh_fetches_when_stale_and_writes_cache(data_dir, monkeypatch):
    _write_cache(data_dir, fetched_at=datetime.now(UTC) - timedelta(days=2))
    monkeypatch.setattr(
        community.requests, "get", lambda *a, **k: FakeResponse(200, INDEX)
    )
    index = community.refresh_index()
    assert index["pack_count"] == 3
    assert community.load_cached_index()["pack_count"] == 3
    assert community.cache_meta()["etag"] == '"new"'


def test_refresh_returns_cache_on_network_error(data_dir, monkeypatch):
    _write_cache(data_dir, fetched_at=datetime.now(UTC) - timedelta(days=2))

    def offline(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(community.requests, "get", offline)
    index = community.refresh_index(force=True)
    assert index["pack_count"] == 3


def test_refresh_returns_none_with_no_cache_and_no_network(data_dir, monkeypatch):
    def offline(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(community.requests, "get", offline)
    assert community.refresh_index() is None


def test_refresh_drops_malformed_packs(data_dir, monkeypatch):
    dirty = {
        "schema_version": 1,
        "packs": INDEX["packs"]
        + [
            {"domain": "no-required-fields.org"},
            {"domain": "http.org", "organization": "X", "careers_url": "http://x.org", "platform": "rss"},
            "not-a-dict",
        ],
    }
    monkeypatch.setattr(
        community.requests, "get", lambda *a, **k: FakeResponse(200, dirty)
    )
    index = community.refresh_index(force=True)
    assert index["pack_count"] == 3


def test_normalize_domain_strips_prefixes_and_paths():
    assert community.normalize_domain("https://www.bruegel.org/careers") == "bruegel.org"
    assert community.normalize_domain("jobs.oxfam.org.uk") == "oxfam.org.uk"
    assert community.normalize_domain("Bain & Company") == ""


def test_org_domain_from_url_refuses_ats_hosts():
    assert community.org_domain_from_url("https://www.e3g.org/about/careers/") == "e3g.org"
    assert community.org_domain_from_url("https://boards.greenhouse.io/acme") == ""
    assert community.org_domain_from_url("https://jobs.lever.co/acme") == ""


def test_lookup_matches_domain_url_and_name():
    by_url = community.lookup("https://www.bain.com/careers/", INDEX)
    assert [p["domain"] for p in by_url] == ["bain.com"]

    by_domain = community.lookup("bain.com", INDEX)
    assert [p["domain"] for p in by_domain] == ["bain.com"]

    by_name = community.lookup("bain", INDEX)
    assert [p["domain"] for p in by_name] == ["bain.com"]

    by_partial_name = community.lookup("oxfam", INDEX)
    assert [p["domain"] for p in by_partial_name] == ["oxfam.org.uk"]

    assert community.lookup("ba", INDEX) == []
    assert community.lookup("no such org", INDEX) == []


def test_share_payload_and_issue_url():
    payload = community.build_share_payload(
        url="https://www.bruegel.org/careers",
        organization="Bruegel",
        platform="generic_static",
        last_successful_at="2026-07-10 09:30:00",
        confidence_label="medium",
    )
    assert payload["domain"] == "bruegel.org"
    assert payload["last_verified"] == "2026-07-10"
    assert payload["confidence"] == "medium"

    url = community.share_issue_url(payload)
    assert url.startswith(community.REGISTRY_REPO_URL + "/issues/new")
    assert "template=submit-source.yml" in url
    assert "pack=" in url and "bruegel.org" in url


def test_api_lookup_flags_already_added(data_dir, monkeypatch):
    _allow_public_dns(monkeypatch)
    _write_cache(data_dir)
    init_db()
    add_source("https://www.bruegel.org/careers", "Bruegel")

    result = community_lookup("bruegel.org")
    assert len(result["matches"]) == 1
    assert result["matches"][0]["already_added"] is True

    result = community_lookup("bain.com")
    assert result["matches"][0]["already_added"] is False


def _allow_public_dns(monkeypatch):
    def fake_getaddrinfo(host, port, type=None):
        return [(None, None, None, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(
        "job_radar.ingestion.source_detection.socket.getaddrinfo", fake_getaddrinfo
    )


def test_api_import_adds_source_and_rejects_duplicates(data_dir, monkeypatch):
    _allow_public_dns(monkeypatch)
    _write_cache(data_dir)
    init_db()

    result = community_import(CommunityImport(domain="bain.com"))
    assert result["ok"] is True
    assert result["source"]["organization"] == "Bain & Company"
    rows = execute("SELECT url FROM sources")
    assert rows[0]["url"] == "https://www.bain.com/careers/"

    with pytest.raises(HTTPException) as excinfo:
        community_import(CommunityImport(domain="bain.com"))
    assert excinfo.value.status_code == 409

    with pytest.raises(HTTPException) as excinfo:
        community_import(CommunityImport(domain="unknown.org"))
    assert excinfo.value.status_code == 404


def test_api_share_builds_prefilled_issue(data_dir, monkeypatch):
    _allow_public_dns(monkeypatch)
    init_db()
    source = add_source("https://www.bruegel.org/careers", "Bruegel")

    result = community_share(source.id)
    assert result["payload"]["domain"] == "bruegel.org"
    assert result["domain_missing"] is False
    assert result["issue_url"].startswith(community.REGISTRY_REPO_URL)

    with pytest.raises(HTTPException) as excinfo:
        community_share("missing")
    assert excinfo.value.status_code == 404


def test_api_status_reports_cache_state(data_dir):
    status = community_status()
    assert status["available"] is False

    _write_cache(data_dir)
    status = community_status()
    assert status["available"] is True
    assert status["pack_count"] == 3
