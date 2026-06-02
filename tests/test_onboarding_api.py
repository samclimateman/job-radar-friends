from job_radar.api.routers.onboarding import (
    OnboardingAnswers,
    OnboardingPatch,
    OnboardingSource,
    complete_onboarding,
    get_onboarding,
    update_onboarding,
)
from job_radar.app.state import get_state
from job_radar.config.settings import get_settings
from job_radar.db.client import execute, init_db
from job_radar.scoring.store import active_rubric


def test_onboarding_progress_persists(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    init_db()

    answers = OnboardingAnswers(name="Alex", current_role="Policy Manager")
    state = update_onboarding(OnboardingPatch(last_step=3, answers=answers))

    assert state.last_step == 3
    assert state.answers.name == "Alex"
    assert get_onboarding().answers.current_role == "Policy Manager"
    assert get_state("user_name") == "Alex"
    get_settings.cache_clear()


def test_onboarding_completion_saves_sources_and_rubric(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    init_db()

    result = complete_onboarding(OnboardingAnswers(
        name="Alex",
        current_role="Policy Manager",
        ideal_role="Strategy work on energy security.",
        locations=["Brussels", "Berlin"],
        target_titles="Policy Lead\nStrategy Manager",
        themes=["Energy security", "Industrial strategy"],
        sources=[
            OnboardingSource(
                organization="Acme",
                url="https://jobs.lever.co/acme",
                notes="Core source",
                verified=True,
            ),
            OnboardingSource(
                organization="Beta",
                url="https://example.org/careers",
                notes="LLM suggestion",
                priority=7,
                llm_suggested=True,
            ),
        ],
    ))

    assert result["ok"] is True
    assert result["sources_added"] == 2
    assert get_onboarding().completed is True

    source = execute("SELECT organization, platform, notes FROM sources WHERE organization = 'Acme'")[0]
    assert source["organization"] == "Acme"
    assert source["platform"] == "lever"
    assert source["notes"] == "Core source"

    llm_source = execute("SELECT status, notes FROM sources WHERE organization = 'Beta'")[0]
    assert llm_source["status"] == "needs_review"
    assert llm_source["notes"] == "LLM suggestion"

    loaded = active_rubric()
    assert loaded is not None
    _, rubric = loaded
    assert rubric.target_locations == ["Brussels", "Berlin"]
    assert rubric.role_types == ["Policy Lead", "Strategy Manager"]
    assert "Energy security" in rubric.positive_keywords
    get_settings.cache_clear()
