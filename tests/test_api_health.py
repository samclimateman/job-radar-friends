from job_radar.api.main import health


def test_health_identifies_job_radar_api():
    assert health() == {
        "ok": True,
        "app": "job-radar",
        "version": "0.1.0",
    }
