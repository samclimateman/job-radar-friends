# Job Radar

Local-first career opportunity monitoring for any niche.

Job Radar tracks career pages, stores scraped jobs locally in SQLite, and ranks opportunities against a user-defined search strategy. It does not apply for jobs, generate fabricated listings, or send your data anywhere.

**Public beta — actively being tested.** The long-term benchmark is a polished local-first indie desktop app that people could reasonably choose to pay for: trustworthy install, calm onboarding, reliable scans, clear source health, useful ranking, and strong backup/export.

---

## What it does

1. Add career-page URLs or RSS/Atom feeds.
2. Job Radar detects the platform (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Personio, RSS) and configures the right connector automatically.
3. Refresh sources on demand. Jobs are stored locally with source provenance.
4. Define a search strategy (locations, role types, industries, keywords). Jobs are scored against your rubric.
5. Review ranked results in the local dashboard. Shortlist, reject, apply, snooze.
6. Source health is tracked — broken, degrading, and manual-watch sources are surfaced clearly.

---

## Download public beta (macOS)

The current public beta is distributed as a GitHub Release DMG:

https://github.com/samclimateman/job-radar-friends/releases

Download `Job.Radar.dmg`, open it, drag **Job Radar.app** to **Applications**, then launch the app. This beta is ad-hoc signed, not Apple Developer ID notarized, so macOS may require right-click → **Open** on first launch.

The repo is public so beta users, testers, and future contributors can inspect the project. It is not a SaaS product and does not currently charge users, but product decisions should be judged against the standard of an app someone might eventually pay for as an independent desktop tool.

## Beta feedback

If you are testing Job Radar, please use [BETA_FEEDBACK.md](BETA_FEEDBACK.md) for the most useful test path and copy/paste report format. GitHub issue templates are available for bug reports and product feedback.

## Developer quick start (macOS)

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
job-radar backup                   # Create a portable backup zip
job-radar doctor                   # Check local runtime
```

---

## Versioning

Version metadata is centralized through `VERSION` and checked across Python, Tauri/Rust, and frontend metadata:

```bash
make version              # show synchronized names and versions
make version-check        # fail if names or versions drift
make version-bump-patch   # bump VERSION and all app metadata, e.g. 0.1.0 -> 0.1.1
make version-bump-minor
make version-bump-major
```

`make public-check` runs the version/name check before Ruff, tests, and the frontend build.

For a deeper product/code review, use [docs/AUDIT_PROMPT.md](docs/AUDIT_PROMPT.md). It is tuned for the public beta benchmark: excellent UX, backend quality, security/privacy, packaging trust, and public-release hygiene.

---

## Desktop app build (macOS, beta)

A Tauri-based desktop wrapper is included. It spawns the Python server and opens the dashboard in a native window.

**Build the Python sidecar:**

```bash
make build-sidecar   # requires PyInstaller: pip install pyinstaller
```

**Build the .app:**

```bash
make build-app
```

**Build the local DMG:**

```bash
make build-dmg
```

The resulting `Job Radar.app` lives in `src-tauri/target/release/bundle/macos/`; the DMG is written to `dist/Job Radar.dmg`.

---

## Data

All data is stored in `~/.job-radar/` by default. Override with `JOB_RADAR_DATA_DIR`.

```
~/.job-radar/
  job-radar.sqlite  SQLite database
  .env              Optional API keys if configured manually
```

Back up the database and user exports from the dashboard (Ranked Jobs → Backup ZIP) or via CLI:

```bash
job-radar backup
```

The backup zip includes the SQLite database, jobs CSV, sources JSON, notes JSON/CSV/Markdown, and metadata.

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
| Tauri desktop shell | Beta (ad-hoc signed DMG) |
| HTTP caching (ETag/Last-Modified) | Planned |
| Full backup zip (database + jobs/sources/notes exports) | Working |
| Developer ID notarized DMG | Planned |
