"""Persistence helpers for user-provided career sources."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from uuid import uuid4

from job_radar.db.client import execute, init_db
from job_radar.ingestion.source_detection import detect_source


@dataclass(frozen=True)
class StoredSource:
    id: str
    url: str
    organization: str | None
    platform: str
    parser_type: str
    config: dict[str, str]
    status: str
    detection_note: str


def _source_id(url: str, organization: str | None) -> str:
    seed = organization or re.sub(r"^https?://", "", url).split("/")[0]
    slug = re.sub(r"[^a-z0-9]+", "_", seed.lower()).strip("_")
    return f"{slug or 'source'}_{uuid4().hex[:8]}"


def add_source(url: str, organization: str | None = None) -> StoredSource:
    init_db()
    clean_url = url.strip()
    detection = detect_source(clean_url)
    status = "needs_review" if detection.manual_review_needed else "active"
    source_id = _source_id(clean_url, organization)

    execute(
        """
        INSERT INTO sources (
            id, url, organization, platform, parser_type, config_json, status, detection_note
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            organization = COALESCE(excluded.organization, sources.organization),
            platform = excluded.platform,
            parser_type = excluded.parser_type,
            config_json = excluded.config_json,
            status = excluded.status,
            detection_note = excluded.detection_note,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            source_id,
            clean_url,
            organization,
            detection.platform,
            detection.parser_type,
            json.dumps(detection.config),
            status,
            detection.note,
        ),
    )

    row = execute("SELECT * FROM sources WHERE url = ?", (clean_url,))[0]
    return StoredSource(
        id=row["id"],
        url=row["url"],
        organization=row["organization"],
        platform=row["platform"],
        parser_type=row["parser_type"],
        config=json.loads(row["config_json"] or "{}"),
        status=row["status"],
        detection_note=row["detection_note"],
    )


def list_sources() -> list[StoredSource]:
    init_db()
    rows = execute("SELECT * FROM sources ORDER BY created_at, url")
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


def set_source_needs_review(source_id: str) -> None:
    execute(
        "UPDATE sources SET status = 'needs_review', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (source_id,),
    )


def mark_manual_checked(source_id: str) -> None:
    init_db()
    row = execute("SELECT * FROM sources WHERE id = ?", (source_id,))
    if not row:
        return
    source = row[0]
    execute(
        """
        INSERT INTO source_health (
            source_id, platform, parser_type, last_checked_at, error_status,
            manual_review_needed, likely_broken_url
        )
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, NULL, 0, 0)
        ON CONFLICT(source_id) DO UPDATE SET
            last_checked_at = CURRENT_TIMESTAMP,
            error_status = NULL,
            manual_review_needed = 0,
            likely_broken_url = 0
        """,
        (source_id, source["platform"], source["parser_type"]),
    )
