"""Persistence for ingestion runs and jobs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import uuid4

from job_radar.db.client import execute, init_db
from job_radar.ingestion.models import ScrapedJob
from job_radar.ingestion.source_store import StoredSource
from job_radar.scoring.deterministic import score_job
from job_radar.scoring.store import active_rubric, save_job_score


@dataclass
class StoreResult:
    jobs_found: int = 0
    new_jobs_found: int = 0


def start_run(source_count: int) -> str:
    init_db()
    run_id = str(uuid4())
    execute(
        "INSERT INTO runs (id, sources_attempted) VALUES (?, ?)",
        (run_id, source_count),
    )
    return run_id


def finish_run(run_id: str, status: str, jobs_found: int, errors: int) -> None:
    execute(
        """
        UPDATE runs
        SET finished_at = CURRENT_TIMESTAMP,
            status = ?,
            jobs_found = ?,
            errors = ?
        WHERE id = ?
        """,
        (status, jobs_found, errors, run_id),
    )


def start_source_run(run_id: str, source_id: str) -> str:
    source_run_id = str(uuid4())
    execute(
        "INSERT INTO source_runs (id, run_id, source_id) VALUES (?, ?, ?)",
        (source_run_id, run_id, source_id),
    )
    return source_run_id


def finish_source_run(
    source_run_id: str,
    source: StoredSource,
    *,
    status: str,
    jobs_found: int = 0,
    new_jobs_found: int = 0,
    error: str | None = None,
) -> None:
    execute(
        """
        UPDATE source_runs
        SET finished_at = CURRENT_TIMESTAMP,
            status = ?,
            jobs_found = ?,
            new_jobs_found = ?,
            error = ?
        WHERE id = ?
        """,
        (status, jobs_found, new_jobs_found, error, source_run_id),
    )
    execute(
        """
        INSERT INTO source_health (
            source_id, platform, parser_type, last_checked_at, last_successful_at,
            jobs_found, new_jobs_found, error_status, manual_review_needed, likely_broken_url
        )
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, CASE WHEN ? = 'success' THEN CURRENT_TIMESTAMP ELSE NULL END,
                ?, ?, ?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
            platform = excluded.platform,
            parser_type = excluded.parser_type,
            last_checked_at = excluded.last_checked_at,
            last_successful_at = COALESCE(excluded.last_successful_at, source_health.last_successful_at),
            jobs_found = excluded.jobs_found,
            new_jobs_found = excluded.new_jobs_found,
            error_status = excluded.error_status,
            manual_review_needed = excluded.manual_review_needed,
            likely_broken_url = excluded.likely_broken_url
        """,
        (
            source.id,
            source.platform,
            source.parser_type,
            status,
            jobs_found,
            new_jobs_found,
            error,
            1 if source.status == "needs_review" else 0,
            1 if error and "404" in error else 0,
        ),
    )


def store_jobs(run_id: str, source: StoredSource, jobs: list[ScrapedJob]) -> StoreResult:
    result = StoreResult(jobs_found=len(jobs))
    seen_urls = {job.source_url for job in jobs}
    rubric_payload = active_rubric()

    for job in jobs:
        existing = execute(
            "SELECT id FROM jobs WHERE source_id = ? AND source_url = ?",
            (source.id, job.source_url),
        )
        if existing:
            job_id = existing[0]["id"]
            execute(
                """
                UPDATE jobs
                SET run_id = ?,
                    title = ?,
                    organization = ?,
                    location = ?,
                    remote_status = ?,
                    source_url = ?,
                    source_job_id = ?,
                    raw_description = ?,
                    normalized_description = ?,
                    raw_payload = ?,
                    deadline = ?,
                    last_seen_at = CURRENT_TIMESTAMP,
                    is_live = 1
                WHERE id = ?
                """,
                (*_job_params(run_id, source, job), job_id),
            )
        else:
            result.new_jobs_found += 1
            job_id = str(uuid4())
            execute(
                """
                INSERT INTO jobs (
                    id, source_id, run_id, title, organization, location, remote_status,
                    source_url, source_job_id, raw_description, normalized_description,
                    raw_payload, deadline
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, source.id, *_job_params(run_id, source, job)),
            )
        if rubric_payload:
            _score_stored_job(job_id, job, rubric_payload)

    if seen_urls:
        placeholders = ",".join("?" for _ in seen_urls)
        execute(
            f"""
            UPDATE jobs
            SET is_live = 0, last_seen_at = CURRENT_TIMESTAMP
            WHERE source_id = ?
              AND is_live = 1
              AND source_url NOT IN ({placeholders})
            """,
            (source.id, *seen_urls),
        )

    return result


def _score_stored_job(job_id: str, job: ScrapedJob, rubric_payload) -> None:
    rubric_id, rubric = rubric_payload
    score = score_job(job, rubric)
    explanation = {
        "matched": score.matched,
        "downgraded": score.downgraded,
        "excluded": score.excluded,
    }
    save_job_score(job_id=job_id, rubric_id=rubric_id, score=score.score, explanation=explanation)
    execute(
        """
        UPDATE jobs
        SET is_excluded = ?,
            exclusion_reason = ?
        WHERE id = ?
        """,
        (
            1 if score.is_excluded else 0,
            "; ".join(score.excluded) if score.excluded else None,
            job_id,
        ),
    )


def _job_params(run_id: str, source: StoredSource, job: ScrapedJob) -> tuple:
    description = job.raw_description or ""
    return (
        run_id,
        job.title,
        job.organization or source.organization,
        job.location,
        job.remote_status,
        job.source_url,
        job.source_job_id,
        description,
        " ".join(description.split()),
        json.dumps(job.raw_payload or {}),
        job.deadline,
    )
