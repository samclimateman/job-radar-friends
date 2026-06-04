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


@dataclass(frozen=True)
class LocationDecision:
    decision: str
    matched: list[str] = field(default_factory=list)
    reason: str = ""
    downgrade: float = 0.0


def _contains_any(text: str, needles: list[str]) -> list[str]:
    lower = text.lower()
    return [needle for needle in needles if needle and needle.lower() in lower]


def _is_remote_only(location: str) -> bool:
    lower = location.lower().strip()
    if not lower:
        return False
    remote_markers = ("remote", "work from home", "wfh", "anywhere")
    if not any(marker in lower for marker in remote_markers):
        return False
    office_markers = ("hybrid", "/", ",", " in ", "based")
    return not any(marker in lower for marker in office_markers)


def location_decision(job: ScrapedJob, rubric: ScoringRubric) -> LocationDecision:
    location = job.location or ""
    target_matches = _contains_any(location, rubric.target_locations)
    remote_only = _is_remote_only(location)
    unknown = not location.strip() or location.strip().lower() in {
        "multiple locations", "various", "various locations", "global", "worldwide"
    } or location.strip().lower().endswith(" locations")

    if target_matches:
        return LocationDecision(
            decision="keep",
            matched=target_matches,
            reason="target_location",
        )

    if remote_only:
        if rubric.remote_policy == "any_remote":
            return LocationDecision(decision="keep", reason="plain_remote_allowed")
        if rubric.remote_policy == "no_remote_only":
            return LocationDecision(decision="exclude", reason="remote_only_excluded")
        if rubric.location_policy == "flexible":
            return LocationDecision(decision="keep", reason="remote_policy_mismatch", downgrade=0.05)
        return LocationDecision(decision="exclude", reason="remote_policy_mismatch")

    if unknown:
        if rubric.unknown_location_policy == "exclude":
            return LocationDecision(decision="exclude", reason="unknown_location_excluded")
        if rubric.unknown_location_policy == "review":
            return LocationDecision(decision="review", reason="unknown_location_review", downgrade=0.1)
        if rubric.location_policy == "strict":
            return LocationDecision(decision="review", reason="strict_unknown_location", downgrade=0.1)
        return LocationDecision(decision="keep", reason="unknown_location_kept")

    if rubric.location_policy == "strict":
        return LocationDecision(decision="exclude", reason="strict_location_mismatch")
    if rubric.location_policy == "prefer":
        return LocationDecision(decision="keep", reason="location_outside_target", downgrade=0.15)
    return LocationDecision(decision="keep", reason="location_not_targeted")


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

    loc = location_decision(job, rubric)
    if loc.decision == "exclude":
        return ScoreResult(
            score=0.0,
            excluded=[f"excluded because: {loc.reason}"],
        )
    if loc.matched:
        raw += weights.location
        matched.extend(f"matched location: {item}" for item in loc.matched)
    elif loc.reason:
        if loc.decision == "review":
            downgraded.append(f"needs review: {loc.reason}")
        elif loc.downgrade:
            downgraded.append(f"downgraded because: {loc.reason}")

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
    penalty = min(0.35, 0.1 * len(negative_matches) + loc.downgrade)
    if negative_matches:
        downgraded.extend(f"downgraded because: {item}" for item in negative_matches)

    normalized = max(0.0, min(100.0, ((raw / total_weight) - penalty) * 100))
    return ScoreResult(score=round(normalized, 1), matched=matched, downgraded=downgraded)
