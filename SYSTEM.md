# Job Radar System Notes

## Browser Scraper Rule

Any scraper that launches Playwright/Chromium must set `requires_browser = True` as a class attribute.

Scrapers inheriting from `PlaywrightBaseScraper` get this automatically. Scrapers that call `sync_playwright()` directly, for example Workday-style or custom site-specific browser scrapers, must set it manually on the scraper class.

This flag is read by `job_radar.ingestion.runner._fetch_jobs()` to throttle concurrent browser sessions via:

```python
_browser_sem = threading.Semaphore(2)
```

The reason: multiple scrapers may run in a `ThreadPoolExecutor` later. HTTP scrapers can run freely in parallel, but Chromium instances contend heavily for CPU and memory. The runner should allow at most two concurrent browser sessions while leaving HTTP scrapers unaffected.

Implementation checklist for future browser scrapers:

1. Prefer inheriting from `PlaywrightBaseScraper`.
2. If calling `sync_playwright()` directly, add `requires_browser = True` manually.
3. Do not bypass `_fetch_jobs()` when running sources from the ingestion runner.
4. Keep scraper failures non-fatal so manual refresh still returns source-health errors rather than breaking the full run.
