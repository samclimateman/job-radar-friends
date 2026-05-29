"""Ingestion runner for saved sources."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field

from job_radar.db.client import execute, init_db
from job_radar.ingestion.source_store import StoredSource
from job_radar.ingestion.sources.ashby import AshbyScraper
from job_radar.ingestion.sources.greenhouse import GreenhouseScraper
from job_radar.ingestion.sources.lever import LeverScraper
from job_radar.ingestion.sources.personio import PersonioScraper
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
    "smartrecruiters": SmartRecruitersScraper,
    "workable": WorkableScraper,
}

_browser_sem = threading.Semaphore(2)


@dataclass
class SourceIngestionResult:
    source_id: str
    url: str
    platform: str
    success: bool
    jobs_found: int = 0
    new_jobs_found: int = 0
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

    for source in sources:
        source_run_id = start_source_run(run_id, source.id)
        scraper_cls = SCRAPERS.get(source.platform)
        if scraper_cls is None:
            error = f"No v0.1 scraper implemented for platform: {source.platform}"
            finish_source_run(source_run_id, source, status="failed", error=error)
            result.sources_failed += 1
            result.results.append(
                SourceIngestionResult(source.id, source.url, source.platform, False, error=error)
            )
            continue

        try:
            jobs = _fetch_jobs(scraper_cls, source)
            stored = store_jobs(run_id, source, jobs)
            finish_source_run(
                source_run_id,
                source,
                status="success",
                jobs_found=stored.jobs_found,
                new_jobs_found=stored.new_jobs_found,
            )
            result.sources_succeeded += 1
            result.jobs_found += stored.jobs_found
            result.new_jobs_found += stored.new_jobs_found
            result.results.append(
                SourceIngestionResult(
                    source.id,
                    source.url,
                    source.platform,
                    True,
                    jobs_found=stored.jobs_found,
                    new_jobs_found=stored.new_jobs_found,
                )
            )
        except Exception as exc:
            error = str(exc)
            finish_source_run(source_run_id, source, status="failed", error=error)
            result.sources_failed += 1
            result.results.append(
                SourceIngestionResult(source.id, source.url, source.platform, False, error=error)
            )

    status = "success" if result.sources_failed == 0 else "partial" if result.sources_succeeded else "failed"
    finish_run(run_id, status, result.jobs_found, result.sources_failed)
    return result


def _fetch_jobs(scraper_cls, source: StoredSource):
    scraper = scraper_cls()
    needs_browser = getattr(scraper_cls, "requires_browser", False)
    if needs_browser:
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
    sources = []
    for row in rows:
        sources.append(
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
        )
    return sources
