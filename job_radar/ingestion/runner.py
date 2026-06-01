"""Ingestion runner for saved sources."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from job_radar.db.client import execute, init_db
from job_radar.ingestion.source_store import StoredSource
from job_radar.ingestion.sources.ashby import AshbyScraper
from job_radar.ingestion.sources.greenhouse import GreenhouseScraper
from job_radar.ingestion.sources.lever import LeverScraper
from job_radar.ingestion.sources.personio import PersonioScraper
from job_radar.ingestion.sources.rss import RssScraper
from job_radar.ingestion.sources.smartrecruiters import SmartRecruitersScraper
from job_radar.ingestion.sources.workable import WorkableScraper
from job_radar.ingestion.store import (
    finish_run,
    finish_source_run,
    start_run,
    start_source_run,
    store_jobs,
)

SCRAPERS = {
    "ashby": AshbyScraper,
    "greenhouse": GreenhouseScraper,
    "lever": LeverScraper,
    "personio": PersonioScraper,
    "rss": RssScraper,
    "smartrecruiters": SmartRecruitersScraper,
    "workable": WorkableScraper,
}

_HTTP_WORKERS = 5
_browser_sem = threading.Semaphore(2)


@dataclass
class SourceIngestionResult:
    source_id: str
    url: str
    platform: str
    success: bool
    jobs_found: int = 0
    new_jobs_found: int = 0
    jobs_changed: int = 0
    fetch_ms: int | None = None
    total_ms: int | None = None
    error: str | None = None


@dataclass
class IngestionResult:
    run_id: str
    sources_attempted: int
    sources_succeeded: int = 0
    sources_failed: int = 0
    jobs_found: int = 0
    new_jobs_found: int = 0
    results: list[SourceIngestionResult] = field(default_factory=list)


def run_ingestion(source_id: str | None = None) -> IngestionResult:
    init_db()
    sources = _load_ingestible_sources(source_id)
    run_id = start_run(len(sources))
    result = IngestionResult(run_id=run_id, sources_attempted=len(sources))

    with ThreadPoolExecutor(max_workers=_HTTP_WORKERS) as pool:
        futures = {pool.submit(_ingest_source, run_id, source): source for source in sources}
        for future in as_completed(futures):
            item = future.result()
            result.results.append(item)
            if item.success:
                result.sources_succeeded += 1
                result.jobs_found += item.jobs_found
                result.new_jobs_found += item.new_jobs_found
            else:
                result.sources_failed += 1

    status = "success" if result.sources_failed == 0 else "partial" if result.sources_succeeded else "failed"
    finish_run(run_id, status, result.jobs_found, result.sources_failed)
    execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return result


def _ingest_source(run_id: str, source: StoredSource) -> SourceIngestionResult:
    source_run_id = start_source_run(run_id, source.id)
    scraper_cls = SCRAPERS.get(source.platform)
    total_start = time.monotonic()

    if scraper_cls is None:
        error = f"No scraper implemented for platform: {source.platform}"
        total_ms = int((time.monotonic() - total_start) * 1000)
        finish_source_run(source_run_id, source, status="failed", error=error, total_ms=total_ms)
        return SourceIngestionResult(source.id, source.url, source.platform, False, error=error)

    try:
        fetch_start = time.monotonic()
        jobs = _fetch_jobs(scraper_cls, source)
        fetch_ms = int((time.monotonic() - fetch_start) * 1000)

        upsert_start = time.monotonic()
        stored = store_jobs(run_id, source, jobs)
        upsert_ms = int((time.monotonic() - upsert_start) * 1000)

        total_ms = int((time.monotonic() - total_start) * 1000)
        finish_source_run(
            source_run_id, source,
            status="success",
            jobs_found=stored.jobs_found,
            new_jobs_found=stored.new_jobs_found,
            jobs_changed=stored.jobs_changed,
            jobs_unchanged=stored.jobs_unchanged,
            fetch_ms=fetch_ms,
            upsert_ms=upsert_ms,
            total_ms=total_ms,
        )
        return SourceIngestionResult(
            source.id, source.url, source.platform, True,
            jobs_found=stored.jobs_found,
            new_jobs_found=stored.new_jobs_found,
            jobs_changed=stored.jobs_changed,
            fetch_ms=fetch_ms,
            total_ms=total_ms,
        )
    except Exception as exc:
        total_ms = int((time.monotonic() - total_start) * 1000)
        error = str(exc)
        finish_source_run(source_run_id, source, status="failed", error=error, total_ms=total_ms)
        return SourceIngestionResult(source.id, source.url, source.platform, False, error=error)


def _fetch_jobs(scraper_cls, source: StoredSource):
    scraper = scraper_cls()
    if getattr(scraper_cls, "requires_browser", False):
        with _browser_sem:
            return scraper.fetch(organization=source.organization, **source.config)
    return scraper.fetch(organization=source.organization, **source.config)


def _load_ingestible_sources(source_id: str | None = None) -> list[StoredSource]:
    sql = "SELECT * FROM sources WHERE status = 'active'"
    params: tuple = ()
    if source_id:
        sql += " AND id = ?"
        params = (source_id,)
    sql += " ORDER BY created_at, url"
    rows = execute(sql, params)
    return [
        StoredSource(
            id=row["id"],
            url=row["url"],
            organization=row["organization"],
            platform=row["platform"],
            parser_type=row["parser_type"],
            config=json.loads(row["config_json"] or "{}"),
            status=row["status"],
            detection_note=row["detection_note"],
        )
        for row in rows
    ]
