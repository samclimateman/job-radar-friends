"""Tests for the RSS/Atom scraper and RSS source detection."""

from unittest.mock import patch

import feedparser
import pytest

from job_radar.ingestion.source_detection import detect_source
from job_radar.ingestion.sources.rss import RssScraper, _passes_filters, _text

# ── Fixtures ──────────────────────────────────────────────────────────────────

RSS_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Example Jobs</title>
  <item>
    <title>Policy Analyst</title>
    <link>https://example.org/jobs/1</link>
    <guid>https://example.org/jobs/1</guid>
    <description>Work on energy policy in Brussels.</description>
    <pubDate>Mon, 02 Jun 2026 09:00:00 +0000</pubDate>
  </item>
  <item>
    <title>Research Fellow</title>
    <link>https://example.org/jobs/2</link>
    <guid>https://example.org/jobs/2</guid>
    <description>A fellowship in climate research.</description>
  </item>
</channel></rss>"""

MIXED_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Mixed News</title>
  <item>
    <title>Annual Conference on Climate</title>
    <link>https://example.org/events/1</link>
    <description>Join our annual webinar series.</description>
  </item>
  <item>
    <title>Senior Analyst vacancy</title>
    <link>https://example.org/jobs/3</link>
    <description>We are hiring a Senior Analyst for our Brussels office.</description>
  </item>
  <item>
    <title>Newsletter issue 42</title>
    <link>https://example.org/newsletter/42</link>
    <description>Read our latest newsletter.</description>
  </item>
</channel></rss>"""

ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Jobs</title>
  <entry>
    <title>Data Scientist</title>
    <link href="https://example.org/jobs/atom/1"/>
    <id>https://example.org/jobs/atom/1</id>
    <summary>Data science position in Berlin.</summary>
  </entry>
</feed>"""


def _parsed(xml):
    return feedparser.parse(xml)


# ── Source detection ──────────────────────────────────────────────────────────

def test_detects_rss_by_rss_extension():
    assert detect_source("https://example.org/feed.rss").platform == "rss"


def test_detects_rss_by_xml_extension():
    assert detect_source("https://example.org/jobs.xml").platform == "rss"


def test_detects_rss_by_atom_extension():
    assert detect_source("https://example.org/feed.atom").platform == "rss"


def test_detects_rss_by_feed_path_segment():
    assert detect_source("https://example.org/feed/").platform == "rss"
    assert detect_source("https://example.org/rss/latest").platform == "rss"


def test_detects_rss_by_query_param():
    assert detect_source("https://example.org/news?format=rss").platform == "rss"


def test_normal_career_url_is_not_rss():
    assert detect_source("https://jobs.lever.co/acme").platform == "lever"
    assert detect_source("https://example.org/careers").platform == "generic_static"


def test_rss_config_contains_feed_url():
    d = detect_source("https://example.org/feed.rss")
    assert d.config["feed_url"] == "https://example.org/feed.rss"
    assert not d.manual_review_needed


# ── Scraper: basic parsing ────────────────────────────────────────────────────

def test_rss_scraper_parses_two_job_items():
    with patch("job_radar.ingestion.sources.rss.feedparser.parse", return_value=_parsed(RSS_FEED)):
        jobs = RssScraper().fetch(organization="Example Org", feed_url="https://x", apply_filters=False)
    assert len(jobs) == 2
    assert {j.title for j in jobs} == {"Policy Analyst", "Research Fellow"}


def test_rss_scraper_preserves_source_url_and_guid():
    with patch("job_radar.ingestion.sources.rss.feedparser.parse", return_value=_parsed(RSS_FEED)):
        jobs = RssScraper().fetch(organization="Org", feed_url="https://x", apply_filters=False)
    first = next(j for j in jobs if j.title == "Policy Analyst")
    assert first.source_url == "https://example.org/jobs/1"
    assert first.source_job_id == "https://example.org/jobs/1"


def test_rss_scraper_sets_organization_from_source():
    with patch("job_radar.ingestion.sources.rss.feedparser.parse", return_value=_parsed(RSS_FEED)):
        jobs = RssScraper().fetch(organization="My Org", feed_url="https://x", apply_filters=False)
    assert all(j.organization == "My Org" for j in jobs)


def test_rss_scraper_captures_description():
    with patch("job_radar.ingestion.sources.rss.feedparser.parse", return_value=_parsed(RSS_FEED)):
        jobs = RssScraper().fetch(organization="Org", feed_url="https://x", apply_filters=False)
    analyst = next(j for j in jobs if j.title == "Policy Analyst")
    assert "energy policy" in analyst.raw_description


def test_rss_scraper_parses_atom_feed():
    with patch("job_radar.ingestion.sources.rss.feedparser.parse", return_value=_parsed(ATOM_FEED)):
        jobs = RssScraper().fetch(organization="Org", feed_url="https://x", apply_filters=False)
    assert len(jobs) == 1
    assert jobs[0].title == "Data Scientist"
    assert jobs[0].source_url == "https://example.org/jobs/atom/1"


# ── Scraper: filtering ────────────────────────────────────────────────────────

def test_rss_scraper_filters_non_job_items():
    with patch("job_radar.ingestion.sources.rss.feedparser.parse", return_value=_parsed(MIXED_FEED)):
        jobs = RssScraper().fetch(organization="Org", feed_url="https://x", apply_filters=True)
    titles = {j.title for j in jobs}
    assert "Senior Analyst vacancy" in titles
    assert "Annual Conference on Climate" not in titles
    assert "Newsletter issue 42" not in titles


def test_rss_scraper_apply_filters_false_returns_all():
    with patch("job_radar.ingestion.sources.rss.feedparser.parse", return_value=_parsed(MIXED_FEED)):
        jobs = RssScraper().fetch(organization="Org", feed_url="https://x", apply_filters=False)
    assert len(jobs) == 3


def test_rss_scraper_custom_include_keywords():
    with patch("job_radar.ingestion.sources.rss.feedparser.parse", return_value=_parsed(MIXED_FEED)):
        # Include only "conference", exclude nothing — newsletter should not match
        jobs = RssScraper().fetch(
            organization="Org", feed_url="https://x",
            include_keywords=["conference"],
            exclude_keywords=[],
        )
    assert any("Conference" in j.title for j in jobs)
    assert not any("Newsletter" in j.title for j in jobs)


# ── Scraper: error cases ──────────────────────────────────────────────────────

def test_rss_scraper_raises_on_missing_feed_url():
    with pytest.raises(ValueError, match="feed_url"):
        RssScraper().fetch(organization="Org")


def test_rss_scraper_raises_on_completely_unparseable_feed():
    empty = feedparser.parse("")
    with patch("job_radar.ingestion.sources.rss.feedparser.parse", return_value=empty):
        with pytest.raises(RuntimeError, match="Failed to parse"):
            RssScraper().fetch(organization="Org", feed_url="https://bad.example")


# ── Helpers ───────────────────────────────────────────────────────────────────

def test_text_strips_html_tags():
    assert _text("<p>Hello <b>world</b></p>") == "Hello world"


def test_text_collapses_whitespace():
    assert _text("  too   many   spaces  ") == "too many spaces"


def test_passes_filters_include_match():
    assert _passes_filters("Senior job vacancy", "", ["job"], []) is True


def test_passes_filters_no_include_match():
    assert _passes_filters("Annual conference recap", "", ["job"], []) is False


def test_passes_filters_exclude_wins():
    assert _passes_filters("Job fair webinar event", "", ["job"], ["webinar"]) is False


def test_passes_filters_no_exclude_passes():
    assert _passes_filters("Policy analyst position", "", [], ["webinar"]) is True
