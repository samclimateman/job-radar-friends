from job_radar.ingestion.models import ScrapedJob
from job_radar.scoring.deterministic import score_job
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
