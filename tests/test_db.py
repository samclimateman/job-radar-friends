from job_radar.db.client import execute, init_db


def test_init_db_creates_core_tables(tmp_path):
    db_path = tmp_path / "job-radar.sqlite"

    init_db(db_path)
    rows = execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name",
        path=db_path,
    )
    names = {row["name"] for row in rows}

    assert "sources" in names
    assert "jobs" in names
    assert "source_health" in names
    assert "job_scores" in names
