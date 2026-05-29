"""Persistence helpers for search strategy and job scores."""

from __future__ import annotations

import json
from uuid import uuid4

from job_radar.db.client import execute, init_db
from job_radar.scoring.rubric import ScoringRubric, split_terms

DEFAULT_PROFILE_ID = "default"


def save_rubric(
    *,
    strategy_narrative: str = "",
    target_locations: str = "",
    preferred_industries: str = "",
    role_types: str = "",
    seniority: str = "",
    positive_keywords: str = "",
    negative_keywords: str = "",
    dealbreakers: str = "",
) -> str:
    init_db()
    execute(
        """
        INSERT INTO user_profile (id, label, notes)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            notes = excluded.notes,
            updated_at = CURRENT_TIMESTAMP
        """,
        (DEFAULT_PROFILE_ID, "Default search", strategy_narrative.strip()),
    )
    execute("UPDATE scoring_rubric SET active = 0 WHERE active = 1")
    rubric = ScoringRubric(
        strategy_narrative=strategy_narrative.strip(),
        target_locations=split_terms(target_locations),
        preferred_industries=split_terms(preferred_industries),
        role_types=split_terms(role_types),
        seniority=split_terms(seniority),
        positive_keywords=split_terms(positive_keywords),
        negative_keywords=split_terms(negative_keywords),
        dealbreakers=split_terms(dealbreakers),
    )
    rubric_id = str(uuid4())
    execute(
        """
        INSERT INTO scoring_rubric (id, profile_id, rubric_json, active)
        VALUES (?, ?, ?, 1)
        """,
        (rubric_id, DEFAULT_PROFILE_ID, rubric.model_dump_json()),
    )
    return rubric_id


def active_rubric() -> tuple[str, ScoringRubric] | None:
    init_db()
    rows = execute(
        """
        SELECT id, rubric_json
        FROM scoring_rubric
        WHERE active = 1
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    if not rows:
        return None
    return rows[0]["id"], ScoringRubric.model_validate_json(rows[0]["rubric_json"])


def active_rubric_values() -> dict[str, str]:
    loaded = active_rubric()
    if not loaded:
        return {}
    _, rubric = loaded
    return {
        "strategy_narrative": rubric.strategy_narrative,
        "target_locations": "\n".join(rubric.target_locations),
        "preferred_industries": "\n".join(rubric.preferred_industries),
        "role_types": "\n".join(rubric.role_types),
        "seniority": "\n".join(rubric.seniority),
        "positive_keywords": "\n".join(rubric.positive_keywords),
        "negative_keywords": "\n".join(rubric.negative_keywords),
        "dealbreakers": "\n".join(rubric.dealbreakers),
    }


def save_job_score(
    *,
    job_id: str,
    rubric_id: str,
    score: float,
    explanation: dict,
) -> None:
    execute(
        """
        INSERT INTO job_scores (job_id, rubric_id, score, explanation_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET
            rubric_id = excluded.rubric_id,
            score = excluded.score,
            explanation_json = excluded.explanation_json,
            scored_at = CURRENT_TIMESTAMP
        """,
        (job_id, rubric_id, score, json.dumps(explanation)),
    )
