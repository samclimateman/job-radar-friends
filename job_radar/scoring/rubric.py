"""Structured search rubric."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RubricWeights(BaseModel):
    location: float = 0.2
    role_type: float = 0.25
    industry: float = 0.25
    seniority: float = 0.15
    keyword_fit: float = 0.15

    @field_validator("*")
    @classmethod
    def weight_must_be_non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("weights must be non-negative")
        return value


class ScoringRubric(BaseModel):
    strategy_narrative: str = ""
    target_locations: list[str] = Field(default_factory=list)
    location_policy: Literal["flexible", "prefer", "strict"] = "flexible"
    remote_policy: Literal["any_remote", "target_region_remote", "no_remote_only"] = "any_remote"
    unknown_location_policy: Literal["keep", "review", "exclude"] = "keep"
    preferred_industries: list[str] = Field(default_factory=list)
    role_types: list[str] = Field(default_factory=list)
    seniority: list[str] = Field(default_factory=list)
    positive_keywords: list[str] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list)
    dealbreakers: list[str] = Field(default_factory=list)
    weights: RubricWeights = Field(default_factory=RubricWeights)


def split_terms(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value.replace(",", "\n")
    return [item.strip() for item in normalized.splitlines() if item.strip()]
