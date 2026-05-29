"""Core ingestion models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceDetection:
    platform: str
    parser_type: str
    note: str
    config: dict[str, str] = field(default_factory=dict)
    manual_review_needed: bool = False


@dataclass(frozen=True)
class ScrapedJob:
    title: str
    organization: str | None
    source_url: str
    raw_description: str = ""
    location: str | None = None
    remote_status: str | None = None
    source_job_id: str | None = None
    deadline: str | None = None
    raw_payload: dict | None = None
