import json

from job_radar.api.routers.blocklist import PhraseBody, add_phrase, get_blocklist
from job_radar.config.settings import get_settings


def test_blocklist_persists_in_user_data_dir(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))

    add_phrase(PhraseBody(phrase="intern"))

    path = tmp_path / "blocked_phrases.json"
    assert path.exists()
    assert json.loads(path.read_text()) == ["intern"]
    assert get_blocklist() == ["intern"]
    get_settings.cache_clear()
