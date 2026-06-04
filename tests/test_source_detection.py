import pytest

from job_radar.ingestion.source_detection import SourceUrlError, detect_source, normalize_source_url


def test_detects_greenhouse_board():
    detection = detect_source("https://job-boards.greenhouse.io/example")

    assert detection.platform == "greenhouse"
    assert detection.parser_type == "api"
    assert detection.config["board_token"] == "example"


def test_detects_lever_board():
    detection = detect_source("https://jobs.lever.co/acme")

    assert detection.platform == "lever"
    assert detection.config["company"] == "acme"


def test_detects_workable_board():
    detection = detect_source("https://apply.workable.com/acme/")

    assert detection.platform == "workable"
    assert detection.config["slug"] == "acme"


def test_detects_personio_board():
    detection = detect_source("https://acme.jobs.personio.com/")

    assert detection.platform == "personio"
    assert detection.config["slug"] == "acme"


def test_detects_ashby_board():
    detection = detect_source("https://jobs.ashbyhq.com/acme")

    assert detection.platform == "ashby"
    assert detection.config["org_slug"] == "acme"


def test_detects_smartrecruiters_board():
    detection = detect_source("https://careers.smartrecruiters.com/OECD/oecd---en")

    assert detection.platform == "smartrecruiters"
    assert detection.config["company_id"] == "OECD"


def test_workday_degrades_to_manual_watch():
    detection = detect_source("https://acme.wd1.myworkdayjobs.com/Careers")

    assert detection.platform == "workday"
    assert detection.parser_type == "manual_watch"
    assert detection.manual_review_needed is True


def test_unknown_degrades_to_static_html_review():
    detection = detect_source("https://example.org/careers")

    assert detection.platform == "generic_static"
    assert detection.parser_type == "static_html"
    assert detection.manual_review_needed is True


def test_source_url_normalizes_bare_domains():
    assert normalize_source_url("jobs.lever.co/acme") == "https://jobs.lever.co/acme"


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/jobs.xml",
        "ftp://example.org/jobs.xml",
        "http://localhost:8766/feed.xml",
        "http://127.0.0.1/feed.xml",
        "http://10.0.0.1/feed.xml",
        "https://user:pass@example.org/jobs",
    ],
)
def test_source_url_rejects_unsafe_inputs(url):
    with pytest.raises(SourceUrlError):
        normalize_source_url(url)


def test_source_url_rejects_hostname_that_resolves_private(monkeypatch):
    def fake_getaddrinfo(host, port, type=None):
        return [(None, None, None, "", ("127.0.0.1", 0))]

    monkeypatch.setattr("job_radar.ingestion.source_detection.socket.getaddrinfo", fake_getaddrinfo)

    with pytest.raises(SourceUrlError):
        normalize_source_url("https://careers.example.org/jobs", resolve_dns=True)


def test_source_url_allows_public_dns_resolution(monkeypatch):
    def fake_getaddrinfo(host, port, type=None):
        return [(None, None, None, "", ("93.184.216.34", 0))]

    monkeypatch.setattr("job_radar.ingestion.source_detection.socket.getaddrinfo", fake_getaddrinfo)

    assert (
        normalize_source_url("https://careers.example.org/jobs", resolve_dns=True)
        == "https://careers.example.org/jobs"
    )
