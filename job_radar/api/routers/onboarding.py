"""First-run onboarding persistence and completion endpoints."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from job_radar.api.routers.blocklist import _load as load_blocklist
from job_radar.api.routers.blocklist import _save as save_blocklist
from job_radar.app.state import get_state, set_state
from job_radar.db.client import execute
from job_radar.ingestion.source_detection import SourceUrlError
from job_radar.ingestion.source_store import add_source, set_source_needs_review
from job_radar.scoring.store import save_rubric

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingSource(BaseModel):
    organization: str = ""
    url: str = ""
    notes: str = ""
    priority: int | None = None
    verified: bool = False
    llm_suggested: bool = False
    review_status: str = ""


class OnboardingAnswers(BaseModel):
    name: str = ""
    current_role: str = ""
    ideal_role: str = ""
    locations: list[str] = Field(default_factory=list)
    location_policy: Literal["flexible", "prefer", "strict"] = "flexible"
    remote_policy: Literal["any_remote", "target_region_remote", "no_remote_only"] = "any_remote"
    unknown_location_policy: Literal["keep", "review", "exclude"] = "keep"
    avoid_constraints: str = ""
    target_titles: str = ""
    themes: list[str] = Field(default_factory=list)
    custom_themes: str = ""
    blocked_terms: str = ""
    role_types_to_avoid: list[str] = Field(default_factory=list)
    sources: list[OnboardingSource] = Field(default_factory=list)
    strategy_summary: str = ""


class OnboardingState(BaseModel):
    completed: bool = False
    partial: bool = False
    last_step: int = 0
    answers: OnboardingAnswers = Field(default_factory=OnboardingAnswers)


class OnboardingPatch(BaseModel):
    partial: bool | None = None
    last_step: int | None = None
    answers: OnboardingAnswers | None = None


def _load_state() -> OnboardingState:
    raw = get_state("onboarding", {})
    if not isinstance(raw, dict):
        return OnboardingState()
    return OnboardingState.model_validate(raw)


def _save_state(state: OnboardingState) -> None:
    set_state("onboarding", state.model_dump())
    set_state("onboarding_complete", state.completed)
    if state.answers.name.strip():
        set_state("user_name", state.answers.name.strip())


@router.get("")
def get_onboarding() -> OnboardingState:
    return _load_state()


@router.patch("")
def update_onboarding(body: OnboardingPatch) -> OnboardingState:
    state = _load_state()
    if body.partial is not None:
        state.partial = body.partial
    if body.last_step is not None:
        state.last_step = body.last_step
    if body.answers is not None:
        state.answers = body.answers
    _save_state(state)
    return state


@router.post("/complete")
def complete_onboarding(answers: OnboardingAnswers) -> dict[str, Any]:
    saved_sources = []
    for item in answers.sources:
        url = item.url.strip()
        if not url:
            continue
        try:
            source = add_source(url, organization=item.organization.strip() or None, resolve_dns=True)
        except SourceUrlError:
            continue
        notes = item.notes.strip()
        if notes:
            execute(
                "UPDATE sources SET notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (notes, source.id),
            )
        if item.llm_suggested and not item.verified:
            set_source_needs_review(source.id)
        saved_sources.append({
            "id": source.id,
            "organization": source.organization,
            "url": source.url,
            "platform": source.platform,
            "status": "needs_review" if item.llm_suggested and not item.verified else source.status,
            "note": source.detection_note,
        })

    themes = [*answers.themes]
    if answers.custom_themes.strip():
        themes.extend(_split_lines(answers.custom_themes))

    blocked_terms = _split_lines(answers.blocked_terms)
    role_avoid = answers.role_types_to_avoid
    if blocked_terms or role_avoid:
        save_blocklist([*load_blocklist(), *blocked_terms, *role_avoid])

    strategy = answers.strategy_summary.strip() or _strategy_summary(answers)
    save_rubric(
        strategy_narrative=strategy,
        target_locations="\n".join(answers.locations),
        location_policy=answers.location_policy,
        remote_policy=answers.remote_policy,
        unknown_location_policy=answers.unknown_location_policy,
        role_types=answers.target_titles,
        positive_keywords="\n".join(themes),
        negative_keywords="\n".join([*blocked_terms, *role_avoid]),
        dealbreakers=answers.avoid_constraints,
    )

    state = OnboardingState(
        completed=True,
        partial=len(saved_sources) < 3,
        last_step=11,
        answers=answers,
    )
    state.answers.strategy_summary = strategy
    _save_state(state)

    return {
        "ok": True,
        "sources_added": len(saved_sources),
        "sources": saved_sources,
        "partial": state.partial,
    }


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.replace(",", "\n").splitlines() if line.strip()]


def _strategy_summary(answers: OnboardingAnswers) -> str:
    titles = _split_lines(answers.target_titles)
    themes = [*answers.themes, *_split_lines(answers.custom_themes)]
    blockers = [*_split_lines(answers.blocked_terms), *answers.role_types_to_avoid]

    prioritize = ", ".join([*titles[:6], *themes[:8]]) or "roles matching the search criteria"
    locations = ", ".join(answers.locations) or "the selected geographies"
    downgrade = ", ".join(blockers[:10]) or "roles outside the stated criteria"

    return (
        f"Prioritize {prioritize} in {locations}. "
        f"Downgrade or flag {downgrade}. "
        "Monitor verified career pages first, keep uncertain sources visible in source health, "
        "and keep excluded jobs inspectable."
    )
