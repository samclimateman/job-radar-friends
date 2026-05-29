from job_radar.ingestion.source_detection import detect_source


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
