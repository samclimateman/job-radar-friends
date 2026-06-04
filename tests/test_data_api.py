import json
import zipfile

from job_radar.api.routers.data import (
    RestoreRequest,
    backup_zip,
    data_location,
    diagnostics_bundle,
    export_jobs,
    restore,
)
from job_radar.config.settings import get_settings
from job_radar.db.client import execute, init_db


def test_data_location_reports_local_paths(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    init_db()

    result = data_location()

    assert result["data_dir"] == str(tmp_path)
    assert result["database_path"].endswith("job-radar.sqlite")
    assert result["database_exists"] is True
    get_settings.cache_clear()


def test_backup_endpoint_returns_portable_zip(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    init_db()

    response = backup_zip()
    backup_path = tmp_path / "backup.zip"
    backup_path.write_bytes(response.body)

    assert response.media_type == "application/zip"
    with zipfile.ZipFile(backup_path) as zf:
        names = set(zf.namelist())
    assert "job-radar.sqlite" in names
    assert "exports/jobs.csv" in names
    assert "exports/sources.json" in names
    assert "exports/notes.json" in names
    get_settings.cache_clear()


def test_export_jobs_download_is_csv(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    init_db()

    response = export_jobs()

    assert response.media_type == "text/csv; charset=utf-8"
    assert "title,organization,location" in response.body.decode()
    get_settings.cache_clear()


def test_restore_rejects_missing_backup_path(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    init_db()

    try:
        restore(RestoreRequest(backup_path=str(tmp_path / "missing.zip")))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
        assert "Backup file not found" in getattr(exc, "detail", "")
    else:
        raise AssertionError("restore should reject missing backup paths")
    get_settings.cache_clear()


def test_diagnostics_bundle_is_redacted_by_default(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value")
    init_db()
    execute(
        "INSERT INTO sources (id, url, organization, platform, status) VALUES (?, ?, ?, ?, ?)",
        ("source-1", "https://example.org/private-careers", "Private Org", "greenhouse", "active"),
    )
    execute("INSERT INTO runs (id, status) VALUES (?, ?)", ("run-1", "success"))
    execute(
        """INSERT INTO jobs (id, source_id, run_id, title, organization, source_url, raw_description)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            "job-1",
            "source-1",
            "run-1",
            "Sensitive Role",
            "Private Org",
            "https://example.org/private-careers/1",
            "Sensitive resume-adjacent detail",
        ),
    )

    response = diagnostics_bundle()
    payload = response.body.decode()
    data = json.loads(payload)

    assert data["privacy"]["redacted_by_default"] is True
    assert data["counts"]["jobs"] == 1
    assert "sk-secret-value" not in payload
    assert "https://example.org/private-careers" not in payload
    assert "Sensitive Role" not in payload
    assert "Sensitive resume-adjacent detail" not in payload
    get_settings.cache_clear()
