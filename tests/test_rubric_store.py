from job_radar.config.env_file import load_api_env, save_api_env
from job_radar.config.settings import get_settings
from job_radar.scoring.store import active_rubric, save_rubric


def test_save_rubric_sets_active_strategy(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))

    save_rubric(
        strategy_narrative="Strategy roles in London",
        target_locations="London\nBerlin",
        location_policy="prefer",
        remote_policy="no_remote_only",
        unknown_location_policy="exclude",
        role_types="strategy, policy",
        dealbreakers="unpaid",
    )

    loaded = active_rubric()
    assert loaded is not None
    _, rubric = loaded
    assert rubric.strategy_narrative == "Strategy roles in London"
    assert rubric.target_locations == ["London", "Berlin"]
    assert rubric.location_policy == "prefer"
    assert rubric.remote_policy == "no_remote_only"
    assert rubric.unknown_location_policy == "exclude"
    assert rubric.role_types == ["strategy", "policy"]
    assert rubric.dealbreakers == ["unpaid"]
    get_settings.cache_clear()


def test_save_api_env_writes_local_env(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))

    save_api_env({"LLM_PROVIDER": "ollama", "OLLAMA_BASE_URL": "http://localhost:11434"})

    assert load_api_env()["LLM_PROVIDER"] == "ollama"
    assert (tmp_path / ".env").exists()
    get_settings.cache_clear()
