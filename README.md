# Job Radar

Local-first career opportunity monitoring for any niche.

Job Radar tracks career pages, stores scraped jobs locally in SQLite, and ranks opportunities against a user-defined search strategy. It does not apply for jobs, generate fabricated listings, or send your data anywhere.

**Alpha — expect rough edges.**

---

## What it does

1. Add career-page URLs or RSS/Atom feeds.
2. Job Radar detects the platform (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Personio, RSS) and configures the right connector automatically.
3. Refresh sources on demand. Jobs are stored locally with source provenance.
4. Define a search strategy (locations, role types, industries, keywords). Jobs are scored against your rubric.
5. Review ranked results in the local dashboard. Shortlist, reject, apply, snooze.
6. Source health is tracked — broken, degrading, and manual-watch sources are surfaced clearly.

---

## Quick start (macOS)

**Install:**

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/job-radar setup
```

**Run:**

```bash
.venv/bin/job-radar start
```

Opens `http://127.0.0.1:8766` in your browser. Or use the Makefile:

```bash
make dev
```

**First run:**
1. Open the Onboarding Wizard or paste career-page URLs directly.
2. Use Source Builder (`/source-builder`) to test any URL before saving it.
3. Save a search strategy under Strategy.
4. Hit **Refresh Now** to run the first scan.
5. Review ranked results in Today's Radar.

---

## Supported source types

| Platform | Type | Notes |
|---|---|---|
| Greenhouse | API | Stable, reliable |
| Lever | API | Stable, reliable |
| Ashby | API | Stable, reliable |
| Workable | API | Stable, reliable |
| SmartRecruiters | API | Stable, reliable |
| Personio | XML | Stable |
| RSS / Atom | Feed | Mixed feeds filtered by keyword |
| Workday | Manual watch | Too dynamic for automation |
| Generic HTML | Manual watch | Flagged for manual review |

---

## Starter source packs

The **Brussels Policy Pack** is bundled and available from the Source Packs page. It covers EU policy, climate, security, and international affairs organizations.

To add sources in bulk, use Source Builder or the onboarding wizard.

---

## CLI reference

```bash
job-radar setup            # Initialize database and data directory
job-radar start            # Start the local dashboard (default port 8766)
job-radar start --port 8080 --no-open
job-radar ingest           # Run ingestion from the command line
job-radar ingest --source-id <id>  # Ingest a single source
job-radar sources add <url>        # Add a source by URL
job-radar sources list
job-radar detect <url>             # Show platform detection for a URL
job-radar backup                   # Copy the SQLite database to a backup file
job-radar doctor                   # Check local runtime
```

---

## Desktop app (macOS, alpha)

A Tauri-based desktop wrapper is included. It spawns the Python server and opens the dashboard in a native window.

**Build the Python sidecar:**

```bash
make build-sidecar   # requires PyInstaller: pip install pyinstaller
```

**Build the .app:**

```bash
make build-app
```

The resulting `Job Radar.app` in `src-tauri/target/release/bundle/macos/` can be moved to your Applications folder. Icons are placeholder — replace `src-tauri/icons/` before distributing.

---

## Data

All data is stored in `~/.job-radar/` by default. Override with `JOB_RADAR_DATA_DIR`.

```
~/.job-radar/
  job-radar.db      SQLite database
  .env              Optional API keys (LLM classification)
```

Back up the database from the dashboard (Ranked Jobs → Backup DB) or via CLI:

```bash
job-radar backup
```

---

## Developer setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/ruff check job_radar/
```

Tests do not require network access. All scraper tests use fixtures.

---

## Non-negotiables

- Every job traces to a source URL, source ID, and scrape run. No fabricated listings.
- User data stays local. No telemetry, no cloud sync, no accounts.
- Scores are fit scores against your declared strategy, not qualification judgments.
- Source failures are visible and non-fatal.
- Excluded and stale jobs remain inspectable.

---

## Status

| Area | State |
|---|---|
| ATS connectors (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Personio) | Working |
| RSS / Atom feeds | Working |
| Source confidence labels | Working |
| Lifecycle tracking (new → active → probably_closed → dead → reappeared) | Working |
| Delta classification (skip rescoring unchanged jobs) | Working |
| Today's Radar view | Working |
| Source Builder | Working |
| Source packs | Alpha (Brussels Policy Pack bundled) |
| Tauri desktop shell | Alpha (unsigned) |
| HTTP caching (ETag/Last-Modified) | Planned |
| Full backup zip (config + CSV) | Planned |
| Signed / notarized DMG | Planned |
