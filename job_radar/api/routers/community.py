"""Community source registry: lookup, import, and share endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from job_radar.db.client import execute
from job_radar.ingestion.source_detection import SourceUrlError
from job_radar.ingestion.source_store import add_source
from job_radar.source_packs import community

router = APIRouter(prefix="/community", tags=["community"])


def _known_domains() -> set[str]:
    rows = execute("SELECT url FROM sources WHERE status != 'disabled'")
    return {
        domain
        for row in rows
        if (domain := community.normalize_domain(row["url"]))
    }


def _known_urls() -> set[str]:
    return {row["url"] for row in execute("SELECT url FROM sources")}


def _with_added_flag(packs: list[dict]) -> list[dict]:
    domains = _known_domains()
    urls = _known_urls()
    return [
        {
            **pack,
            "already_added": pack["careers_url"] in urls or pack["domain"] in domains,
        }
        for pack in packs
    ]


@router.get("/status")
def community_status():
    index = community.load_cached_index()
    meta = community.cache_meta()
    return {
        "available": index is not None,
        "pack_count": index.get("pack_count", 0) if index else 0,
        "fetched_at": meta.get("fetched_at"),
        "registry_url": community.REGISTRY_REPO_URL,
    }


@router.post("/refresh")
def community_refresh(force: bool = False):
    index = community.refresh_index(force=force)
    return {
        "available": index is not None,
        "pack_count": index.get("pack_count", 0) if index else 0,
    }


@router.get("/lookup")
def community_lookup(q: str):
    index = community.load_cached_index()
    if index is None:
        index = community.refresh_index()
    matches = community.lookup(q, index)
    return {"matches": _with_added_flag(matches)}


class CommunityImport(BaseModel):
    domain: str


@router.post("/import")
def community_import(body: CommunityImport):
    index = community.load_cached_index()
    if index is None:
        raise HTTPException(status_code=503, detail="Community index is not available yet")
    pack = next(
        (p for p in index.get("packs", []) if p.get("domain") == body.domain),
        None,
    )
    if pack is None:
        raise HTTPException(status_code=404, detail="No community source for that domain")
    if pack["careers_url"] in _known_urls():
        raise HTTPException(status_code=409, detail="That source is already in your list")
    try:
        source = add_source(pack["careers_url"], pack["organization"], resolve_dns=True)
    except SourceUrlError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "ok": True,
        "source": {
            "id": source.id,
            "organization": source.organization,
            "url": source.url,
            "platform": source.platform,
            "status": source.status,
        },
    }


@router.get("/share-suggestions")
def community_share_suggestions():
    """Working sources the user set up that the registry doesn't have yet."""
    index = community.load_cached_index()
    if index is None:
        return {"suggestions": []}
    packs = index.get("packs", [])
    known_domains = {p.get("domain") for p in packs}
    known_urls = {p.get("careers_url") for p in packs}
    rows = execute(
        """SELECT s.id, s.url, s.organization
             FROM sources s
             JOIN source_health h ON h.source_id = s.id
            WHERE s.status != 'disabled'
              AND h.error_status IS NULL
              AND h.last_successful_at IS NOT NULL
              AND h.jobs_found > 0"""
    )
    suggestions = []
    for row in rows:
        domain = community.normalize_domain(row["url"])
        if row["url"] in known_urls or (domain and domain in known_domains):
            continue
        suggestions.append(
            {"source_id": row["id"], "organization": row["organization"] or row["url"]}
        )
    return {"suggestions": suggestions}


@router.get("/share/{source_id}")
def community_share(source_id: str):
    rows = execute(
        """SELECT s.url, s.organization, s.platform,
                  h.last_successful_at, h.confidence_label
             FROM sources s
             LEFT JOIN source_health h ON h.source_id = s.id
            WHERE s.id = ?""",
        (source_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Source not found")
    row = rows[0]
    payload = community.build_share_payload(
        url=row["url"],
        organization=row["organization"],
        platform=row["platform"],
        last_successful_at=row["last_successful_at"],
        confidence_label=row["confidence_label"],
    )
    return {
        "payload": payload,
        "issue_url": community.share_issue_url(payload),
        "domain_missing": not payload["domain"],
    }
