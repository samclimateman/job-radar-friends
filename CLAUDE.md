# Job Radar 4 Friends — Claude Context

> This file is auto-loaded by Claude Code. Update the **Current State** section at the end of each working session.

## What this is

A public beta of the universal, distributable version of Job Radar for non-technical users. Packaged as a macOS `.dmg` via Tauri. Users install it like a normal app — no terminal, no Python environment visible. Local SQLite, local Python backend, React/Tailwind dashboard.

The product benchmark is not "works for friends" anymore. Treat this as an early independent desktop app that should eventually feel good enough for people to pay for: trustworthy install, calm onboarding, reliable scans, transparent source health, useful ranking, backup/export, and no private-data leakage.

Full system notes (browser scraper rules, concurrency model) in [SYSTEM.md](SYSTEM.md). Roadmap and product direction in [ROADMAP_2_0.md](ROADMAP_2_0.md).

## Key differences from career-ops / personal versions

- **SQLite** not PostgreSQL — simpler, no service to manage
- **Tauri desktop shell** — wraps the Python server, no terminal for users
- **RSS connector** — additional scraper type (`ingestion/sources/rss.py`)
- **SmartRecruiters scraper** — additional platform (`ingestion/sources/smartrecruiters.py`)
- **No Datasette** — React dashboard only (FastAPI backend)
- **No required LLM API** — deterministic scanning/scoring works without paid keys
- **Universal onboarding** — user-specific local setup, not Sam-specific copy or SaaS/accounts

## Stack

- Python backend + SQLite via `job_radar/` package
- FastAPI HTTP layer
- React/Tailwind frontend (`frontend/`)
- Tauri shell (`src-tauri/`)
- Platform scrapers: Greenhouse, Lever, Personio, Ashby, Workable, RSS, SmartRecruiters + PlaywrightBaseScraper for JS-rendered sites

## Building and packaging

```bash
make build-app    # build signed .app bundle
make build-dmg    # build signed .app and local DMG
make test         # run test suite (157 tests, offline)
make public-check # private-marker scan + Ruff + pytest + frontend build
```

Signing: ad-hoc signing in Makefile. Not notarised — friends need to right-click → Open on first launch.

---

## Current State (update each session)

**Last updated:** 2026-06-03

### Phase history
- **Sprint 1–3:** Tauri shell, RSS connector, lifecycle tracking, confidence scoring, dashboard surfaces, source packs
- **Phase 1 (May 2026):** Schema, data layer, SQLite export, 32 tests
- **Phase 2 (May 2026):** Notebook UI, CRUD routes, 8 new tests
- **React/FastAPI migration (June 2026):** React dashboard on FastAPI, HTML admin/settings server on companion port
- **Universal onboarding v1/v2 (June 2026):** first-run wizard, optional LLM prompt/paste expansion, source review, setup quality banner
- **Desktop packaging QA (June 2026):** React assets embedded in PyInstaller sidecar, app-only Tauri build, Makefile-owned DMG creation

### What's working
- Full ingestion pipeline: fetch → filter → score → upsert → stale detection
- Platform scrapers: Greenhouse, Lever, Personio, Ashby, Workable, RSS, SmartRecruiters
- Tauri desktop shell — starts FastAPI dashboard on `:8766` and HTML admin/settings on `:8767`
- React dashboard with Jobs, Sources, Applied, and Notebook tabs
- First-run universal onboarding for users with local persistence and resumable progress
- Optional LLM-assisted organization expansion via manual copy/paste prompt; no API key required
- Source review in onboarding: verified/manual-check flags, priority, notes, and LLM-suggested source handling
- Setup quality banner after onboarding: source count, verified count, unchecked sources, block filters, scan state
- Notebook/notes UI with CRUD routes
- Source health view in dashboard
- React source management actions: edit source details, mark checked, retry scan, enable/disable, and guarded delete
- Confidence scoring + lifecycle tracking (discovered → reviewing → applied etc.)
- macOS DMG build with ad-hoc signing
- **Job search** — text input below view tabs, filters by title/org/location via `?q=` param; limit raised 25→200
- **Compact "why matched" column** — shows top 3 matched values (e.g. `Brussels · policy · climate`), excluded jobs get red pill, concerns shown as muted `(1 concern)` note
- Fresh database initialization bug fixed: migrations no longer run against missing base tables
- Packaged sidecar includes `frontend/dist` and onboarding router; packaged `.app` serves the React onboarding UI on first launch
- Block filters persist in the user data directory, so onboarding completion works from read-only DMG/app bundles
- Portable backup zip is working from dashboard and CLI; includes SQLite DB, jobs CSV, sources JSON, notes JSON/CSV/Markdown, and metadata
- Public release guardrail: `make public-check` runs private-marker scan, Ruff, pytest, and frontend build
- Version/name metadata is centralized through `VERSION`; `make version-check` verifies Python, Tauri/Rust, and frontend metadata, and `make version-bump-patch|minor|major` updates them together

### What's next (prioritised plan)
1. **Manual human QA from the public beta DMG** — install/open the app like a beta tester would, complete onboarding through the UI, add/edit sources, and run a first scan with real URLs.
2. **Settings editor for onboarding answers** — let users revise name, criteria, source review, and strategy after first run from the React UI.
3. **Live first-scan progress in React** — show source-by-source progress and failures while onboarding scan runs.
4. **Source packs in React onboarding** — offer curated starter packs without replacing user-entered sources.
5. **Polish setup quality model** — make “Partial / Good / Strong” actionable with specific next steps.
6. **Indie-app polish pass** — tighten copy, empty states, error states, backup/restore confidence, and packaging rough edges until the app feels credible to a paying non-technical user.
7. **Make production API base dynamic** — same-origin API is now used, but alternate-port package QA still needs careful smoke testing.

### Known issues / debt
- `requires_browser = True` must be set manually on any scraper calling `sync_playwright()` directly (not via `PlaywrightBaseScraper`) — runner uses this to throttle to 2 concurrent browser sessions
- Build not notarised — first-launch requires right-click → Open
- DMG launch was smoke-tested under automation: React shell, onboarding API, onboarding completion with blockers, needs-review source persistence, and blocklist persistence all passed. A full manual double-click/install test is still needed for window lifecycle, first scan with real URLs, and Gatekeeper behavior.
- Keep `README.md`, `SYSTEM.md`, and `CLAUDE.md` manually aligned after behavior changes; avoid dynamic counts unless they are verified during the session.
