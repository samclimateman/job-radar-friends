"""Explainable deterministic scoring against a user rubric."""

from __future__ import annotations

from dataclasses import dataclass, field

from job_radar.ingestion.models import ScrapedJob
from job_radar.scoring.rubric import ScoringRubric


@dataclass(frozen=True)
class ScoreResult:
    score: float
    matched: list[str] = field(default_factory=list)
    downgraded: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)

    @property
    def is_excluded(self) -> bool:
        return bool(self.excluded)


def _contains_any(text: str, needles: list[str]) -> list[str]:
    lower = text.lower()
    return [needle for needle in needles if needle and needle.lower() in lower]


def score_job(job: ScrapedJob, rubric: ScoringRubric) -> ScoreResult:
    haystack = " ".join(
        p for p in [job.title, job.organization or "", job.location or "", job.raw_description] if p
    )

    dealbreakers = _contains_any(haystack, rubric.dealbreakers)
    if dealbreakers:
        return ScoreResult(
            score=0.0,
            excluded=[f"excluded because: {item}" for item in dealbreakers],
        )

    weights = rubric.weights
    total_weight = sum(
        [weights.location, weights.role_type, weights.industry, weights.seniority, weights.keyword_fit]
    ) or 1.0
    raw = 0.0
    matched: list[str] = []
    downgraded: list[str] = []

    location_matches = _contains_any(job.location or "", rubric.target_locations)
    if location_matches:
        raw += weights.location
        matched.extend(f"matched location: {item}" for item in location_matches)

    role_matches = _contains_any(job.title, rubric.role_types)
    if role_matches:
        raw += weights.role_type
        matched.extend(f"matched role type: {item}" for item in role_matches)

    industry_matches = _contains_any(haystack, rubric.preferred_industries)
    if industry_matches:
        raw += weights.industry
        matched.extend(f"matched industry: {item}" for item in industry_matches)

    seniority_matches = _contains_any(job.title, rubric.seniority)
    if seniority_matches:
        raw += weights.seniority
        matched.extend(f"matched seniority: {item}" for item in seniority_matches)

    keyword_matches = _contains_any(haystack, rubric.positive_keywords)
    if keyword_matches:
        raw += weights.keyword_fit
        matched.extend(f"matched keyword: {item}" for item in keyword_matches)

    negative_matches = _contains_any(haystack, rubric.negative_keywords)
    penalty = min(0.35, 0.1 * len(negative_matches))
    if negative_matches:
        downgraded.extend(f"downgraded because: {item}" for item in negative_matches)

    normalized = max(0.0, min(100.0, ((raw / total_weight) - penalty) * 100))
    return ScoreResult(score=round(normalized, 1), matched=matched, downgraded=downgraded)
