from job_radar.ingestion.models import ScrapedJob
from job_radar.scoring.deterministic import location_decision, score_job
from job_radar.scoring.rubric import ScoringRubric


def test_scores_fit_against_declared_strategy():
    rubric = ScoringRubric(
        target_locations=["Brussels"],
        preferred_industries=["energy security"],
        role_types=["policy"],
        seniority=["senior"],
        positive_keywords=["industrial decarbonization"],
    )
    job = ScrapedJob(
        title="Senior Policy Analyst",
        organization="Example",
        location="Brussels",
        source_url="https://example.org/job/1",
        raw_description="Work on energy security and industrial decarbonization.",
    )

    result = score_job(job, rubric)

    assert result.score == 100.0
    assert "matched location: Brussels" in result.matched
    assert "matched keyword: industrial decarbonization" in result.matched
    assert result.is_excluded is False


def test_dealbreaker_excludes_without_hiding_reason():
    rubric = ScoringRubric(dealbreakers=["requires native German"])
    job = ScrapedJob(
        title="Policy Manager",
        organization="Example",
        source_url="https://example.org/job/2",
        raw_description="This role requires native German.",
    )

    result = score_job(job, rubric)

    assert result.score == 0.0
    assert result.is_excluded is True
    assert result.excluded == ["excluded because: requires native German"]


def test_negative_keywords_downgrade_score():
    rubric = ScoringRubric(
        role_types=["policy"],
        negative_keywords=["sales"],
    )
    job = ScrapedJob(
        title="Policy Sales Associate",
        organization="Example",
        source_url="https://example.org/job/3",
        raw_description="A sales-heavy public policy role.",
    )

    result = score_job(job, rubric)

    assert result.score < 100
    assert "downgraded because: sales" in result.downgraded


def test_location_decision_flexible_keeps_non_target():
    rubric = ScoringRubric(target_locations=["Brussels"], location_policy="flexible")
    job = ScrapedJob(title="Policy Manager", organization="Example", location="New York", source_url="https://example.org")

    decision = location_decision(job, rubric)

    assert decision.decision == "keep"
    assert decision.reason == "location_not_targeted"


def test_location_decision_prefer_downgrades_non_target():
    rubric = ScoringRubric(target_locations=["Brussels"], location_policy="prefer")
    job = ScrapedJob(title="Policy Manager", organization="Example", location="New York", source_url="https://example.org")

    decision = location_decision(job, rubric)

    assert decision.decision == "keep"
    assert decision.downgrade > 0


def test_strict_location_policy_excludes_non_target():
    rubric = ScoringRubric(target_locations=["Brussels"], location_policy="strict")
    job = ScrapedJob(title="Policy Manager", organization="Example", location="New York", source_url="https://example.org")

    result = score_job(job, rubric)

    assert result.is_excluded is True
    assert result.excluded == ["excluded because: strict_location_mismatch"]


def test_strict_location_policy_keeps_target_location():
    rubric = ScoringRubric(target_locations=["London"], location_policy="strict")
    job = ScrapedJob(title="Policy Manager", organization="Example", location="New York / London", source_url="https://example.org")

    result = score_job(job, rubric)

    assert result.is_excluded is False
    assert "matched location: London" in result.matched


def test_plain_remote_allowed_only_when_policy_allows_it():
    job = ScrapedJob(title="Policy Manager", organization="Example", location="Remote", source_url="https://example.org")

    allowed = score_job(job, ScoringRubric(location_policy="strict", remote_policy="any_remote"))
    blocked = score_job(job, ScoringRubric(location_policy="strict", remote_policy="target_region_remote"))

    assert allowed.is_excluded is False
    assert blocked.is_excluded is True
    assert blocked.excluded == ["excluded because: remote_policy_mismatch"]


def test_no_remote_only_policy_excludes_plain_remote_even_when_location_flexible():
    rubric = ScoringRubric(location_policy="flexible", remote_policy="no_remote_only")
    job = ScrapedJob(title="Policy Manager", organization="Example", location="Remote", source_url="https://example.org")

    result = score_job(job, rubric)

    assert result.is_excluded is True
    assert result.excluded == ["excluded because: remote_only_excluded"]


def test_unknown_location_policy_review_downgrades_but_keeps():
    rubric = ScoringRubric(unknown_location_policy="review")
    job = ScrapedJob(title="Policy Manager", organization="Example", location=None, source_url="https://example.org")

    result = score_job(job, rubric)

    assert result.is_excluded is False
    assert "needs review: unknown_location_review" in result.downgraded


def test_unknown_location_policy_exclude_blocks_job():
    rubric = ScoringRubric(unknown_location_policy="exclude")
    job = ScrapedJob(title="Policy Manager", organization="Example", location=None, source_url="https://example.org")

    result = score_job(job, rubric)

    assert result.is_excluded is True
    assert result.excluded == ["excluded because: unknown_location_excluded"]
