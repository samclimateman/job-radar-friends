# Job Radar System Notes

## Database Migration Rule

User data lives in `~/.job-radar/job-radar.sqlite`, which persists across app updates. The schema is initialised by `job_radar/db/schema.sql` using `CREATE TABLE IF NOT EXISTS`, so existing tables are never recreated.

**All schema changes must be additive.** The pattern is:

1. Add the new column/table to `schema.sql` with `CREATE TABLE IF NOT EXISTS` or a safe default.
2. Add a corresponding `ALTER TABLE … ADD COLUMN` guard in `_ensure_columns()` in `job_radar/db/client.py`, following the existing pattern:

```python
if "new_column" not in table_cols:
    conn.execute("ALTER TABLE some_table ADD COLUMN new_column TEXT")
```

`_ensure_columns()` is called on every startup, so it will run automatically the first time an existing user opens the updated app.

**Never do any of the following in a release:**

- `DROP TABLE` or `DROP COLUMN`
- `ALTER TABLE … RENAME COLUMN` (without an additive alias first)
- Changing a column's type or `NOT NULL` constraint on existing data
- Removing a `DEFAULT` that existing rows rely on
- Rewriting a table via `CREATE TABLE new … INSERT … DROP TABLE old … ALTER TABLE new RENAME TO old`

Any of these will break existing user databases on update. If a destructive change is truly necessary, it requires an explicit migration path tested against a real `~/.job-radar/` database before shipping.

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
