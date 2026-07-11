"""Persistence for ingestion runs and jobs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import uuid4

from job_radar.db.client import execute, init_db
from job_radar.ingestion.confidence import update_source_confidence
from job_radar.ingestion.models import ScrapedJob
from job_radar.ingestion.source_store import StoredSource
from job_radar.scoring.deterministic import score_job
from job_radar.scoring.store import active_rubric, save_job_score

# Missed-scan thresholds for lifecycle transitions
_PROBABLY_CLOSED_THRESHOLD = 3
_DEAD_THRESHOLD = 7


@dataclass
class StoreResult:
    jobs_found: int = 0
    new_jobs_found: int = 0
    jobs_changed: int = 0
    jobs_unchanged: int = 0


def _description_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


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
    jobs_changed: int = 0,
    jobs_unchanged: int = 0,
    fetch_ms: int | None = None,
    upsert_ms: int | None = None,
    total_ms: int | None = None,
    error: str | None = None,
) -> None:
    execute(
        """
        UPDATE source_runs
        SET finished_at = CURRENT_TIMESTAMP,
            status = ?,
            jobs_found = ?,
            new_jobs_found = ?,
            jobs_changed = ?,
            jobs_unchanged = ?,
            fetch_ms = ?,
            upsert_ms = ?,
            total_ms = ?,
            error = ?
        WHERE id = ?
        """,
        (
            status,
            jobs_found,
            new_jobs_found,
            jobs_changed,
            jobs_unchanged,
            fetch_ms,
            upsert_ms,
            total_ms,
            error,
            source_run_id,
        ),
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
    update_source_confidence(source.id, source.status)


def touch_source_jobs(source_id: str, seen_urls: set[str]) -> int:
    """
    Mark the seen live jobs for a source as still-active without re-upserting.

    Called when response hashing shows the URL set is unchanged — we skip
    normalize/score/upsert but still reset missed_scans for the jobs that are
    still present. Stale rows from earlier scans must not be touched, otherwise
    removed jobs stay active forever once the cache has learned the newer URL
    set. Returns the number of rows updated when available.
    """
    if not seen_urls:
        return 0

    placeholders = ",".join("?" for _ in seen_urls)
    # semgrep:ignore python.sqlalchemy.security.sqlalchemy-execute-raw-query
    rows = execute(
        f"""
        UPDATE jobs
        SET last_seen_at     = CURRENT_TIMESTAMP,
            missed_scans     = 0,
            lifecycle_status = 'active'
        WHERE source_id      = ?
          AND is_live        = 1
          AND lifecycle_status NOT IN ('dead', 'excluded')
          AND source_url IN ({placeholders})
        """,
        (source_id, *seen_urls),
    )
    return len(rows) if rows is not None else 0


def mark_missing_source_jobs(source_id: str, seen_urls: set[str]) -> None:
    """Advance lifecycle for live jobs missing from a successful source scan."""
    if seen_urls:
        _update_missing_jobs(source_id, seen_urls)


def store_jobs(run_id: str, source: StoredSource, jobs: list[ScrapedJob]) -> StoreResult:
    result = StoreResult(jobs_found=len(jobs))
    seen_urls: set[str] = set()
    rubric_payload = active_rubric()

    for job in jobs:
        d_hash = _description_hash(job.raw_description or "")
        seen_urls.add(job.source_url)

        existing = execute(
            "SELECT id, description_hash, lifecycle_status FROM jobs WHERE source_id = ? AND source_url = ?",
            (source.id, job.source_url),
        )

        if existing:
            job_id = existing[0]["id"]
            old_hash = existing[0]["description_hash"]
            old_lifecycle = existing[0]["lifecycle_status"] or "active"
            description_changed = old_hash != d_hash

            if old_lifecycle in ("probably_closed", "dead"):
                # Job was gone, now back — flag it regardless of description change
                new_lifecycle = "reappeared"
                if description_changed:
                    result.jobs_changed += 1
                else:
                    result.jobs_unchanged += 1
            elif description_changed:
                result.jobs_changed += 1
                new_lifecycle = "changed"
            else:
                result.jobs_unchanged += 1
                new_lifecycle = "active"

            execute(
                """
                UPDATE jobs
                SET run_id = ?,
                    title = ?,
                    organization = ?,
                    location = ?,
                    remote_status = ?,
                    source_job_id = ?,
                    raw_description = ?,
                    normalized_description = ?,
                    description_hash = ?,
                    raw_payload = ?,
                    deadline = ?,
                    last_seen_at = CURRENT_TIMESTAMP,
                    last_changed_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE last_changed_at END,
                    times_seen = times_seen + 1,
                    missed_scans = 0,
                    lifecycle_status = ?,
                    is_live = 1
                WHERE id = ?
                """,
                (
                    run_id,
                    job.title,
                    job.organization or source.organization,
                    job.location,
                    job.remote_status,
                    job.source_job_id,
                    job.raw_description or "",
                    " ".join((job.raw_description or "").split()),
                    d_hash,
                    json.dumps(job.raw_payload or {}),
                    job.deadline,
                    description_changed,
                    new_lifecycle,
                    job_id,
                ),
            )
        else:
            result.new_jobs_found += 1
            job_id = str(uuid4())
            execute(
                """
                INSERT INTO jobs (
                    id, source_id, run_id, title, organization, location, remote_status,
                    source_url, source_job_id, raw_description, normalized_description,
                    description_hash, raw_payload, deadline, times_seen, lifecycle_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'new')
                """,
                (
                    job_id,
                    source.id,
                    run_id,
                    job.title,
                    job.organization or source.organization,
                    job.location,
                    job.remote_status,
                    job.source_url,
                    job.source_job_id,
                    job.raw_description or "",
                    " ".join((job.raw_description or "").split()),
                    d_hash,
                    json.dumps(job.raw_payload or {}),
                    job.deadline,
                ),
            )

        _insert_observation(job_id, source, run_id, job, d_hash)

        is_new = not bool(existing)
        desc_changed = existing and existing[0]["description_hash"] != d_hash
        if rubric_payload:
            _score_stored_job(job_id, job, rubric_payload, is_new=is_new, description_changed=bool(desc_changed))

    # On a successful scan, update lifecycle for jobs that weren't seen
    if seen_urls:
        _update_missing_jobs(source.id, seen_urls)
    elif not jobs:
        # Zero jobs from a successful scan — don't penalise missing jobs;
        # the source may simply have no open roles right now.
        pass

    return result


def _insert_observation(
    job_id: str,
    source: StoredSource,
    run_id: str,
    job: ScrapedJob,
    d_hash: str,
) -> None:
    execute(
        """
        INSERT INTO job_observations (id, job_id, source_id, run_id, title_raw, url_raw, description_hash, connector_used)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (str(uuid4()), job_id, source.id, run_id, job.title, job.source_url, d_hash, source.platform),
    )


def _update_missing_jobs(source_id: str, seen_urls: set[str]) -> None:
    """Increment missed_scans for active jobs not returned in this successful scan."""
    placeholders = ",".join("?" for _ in seen_urls)

    # Increment missed_scans for unseen jobs
    # semgrep:ignore python.sqlalchemy.security.sqlalchemy-execute-raw-query
    execute(
        f"""
        UPDATE jobs
        SET missed_scans = missed_scans + 1,
            is_live = CASE WHEN missed_scans + 1 >= ? THEN 0 ELSE is_live END,
            lifecycle_status = CASE
                WHEN missed_scans + 1 >= ? THEN 'dead'
                WHEN missed_scans + 1 >= ? THEN 'probably_closed'
                ELSE lifecycle_status
            END
        WHERE source_id = ?
          AND lifecycle_status NOT IN ('dead', 'excluded')
          AND source_url NOT IN ({placeholders})
        """,
        (
            _DEAD_THRESHOLD,
            _DEAD_THRESHOLD,
            _PROBABLY_CLOSED_THRESHOLD,
            source_id,
            *seen_urls,
        ),
    )

    # Mark reappeared: jobs that were probably_closed/dead but are now seen again
    # (handled in the main loop via lifecycle_status check on existing rows)


def _score_stored_job(
    job_id: str,
    job: ScrapedJob,
    rubric_payload,
    *,
    is_new: bool = True,
    description_changed: bool = False,
) -> None:
    rubric_id, rubric = rubric_payload

    # Delta classification: skip if nothing changed and rubric is the same
    if not is_new and not description_changed:
        existing_score = execute(
            "SELECT rubric_id FROM job_scores WHERE job_id = ?", (job_id,)
        )
        if existing_score and existing_score[0]["rubric_id"] == rubric_id:
            return

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
