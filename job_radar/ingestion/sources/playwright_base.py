"""Base class for Playwright-backed scrapers.

Playwright is optional in v0.1, but future browser scrapers should inherit from
this class so the ingestion runner can throttle Chromium sessions.
"""

from __future__ import annotations


class PlaywrightBaseScraper:
    requires_browser = True
