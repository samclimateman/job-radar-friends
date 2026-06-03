# Job Radar 4 Friends — Claude Context

> This file is auto-loaded by Claude Code. Update the **Current State** section at the end of each working session.

## What this is

A public beta of the universal, distributable version of Job Radar for non-technical users. Packaged as a macOS `.dmg` via Tauri. Users install it like a normal app — no terminal, no Python environment visible. Local SQLite, local Python backend, React/Tailwind dashboard.

The product benchmark is not "works for friends" anymore. Treat this as an early independent desktop app that should eventually feel good enough for people to pay for: trustworthy install, calm onboarding, reliable scans, transparent source health, useful ranking, backup/export, and no private-data leakage.

Full system notes (browser scraper rules, concurrency model) in [SYSTEM.md](SYSTEM.md). Roadmap and product direction in [ROADMAP_2_0.md](ROADMAP_2_0.md). Public beta audit prompt in [docs/AUDIT_PROMPT.md](docs/AUDIT_PROMPT.md).

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

### What changed 2026-06-03
- Onboarding: copy edits steps 0/1/2, gate bug fixed, sidebar step nav + autosave, live first-scan progress
- Settings tab: full post-onboarding editor for name, criteria, themes, strategy
- Polish pass: undo dismiss toast, source delete confirmation, note save error, server error banner, clickable issues badge, empty states, setup banner improvements
- Update banner: checks latest-version.json on GitHub, shows amber banner if newer version available
- Port conflict: Tauri kills stale impostor process on launch (subsequently reverted from lib.rs — shows warning instead)
- Source detection and export improvements (from diff)

### What's next (prioritised plan)
1. **Ship DMG to first beta user** — bump latest-version.json to 0.2.0, send the DMG
2. **Settings editor** — done ✓
3. **Live scan progress** — done ✓
4. **Port conflict** — kill_port reverted from lib.rs; shows warning banner again if port conflict occurs
5. **Source packs in React onboarding** — skipped by design (users too different)
6. **Further polish** — based on beta user feedback

### Known issues / debt
- `requires_browser = True` must be set manually on any scraper calling `sync_playwright()` directly (not via `PlaywrightBaseScraper`) — runner uses this to throttle to 2 concurrent browser sessions
- **Schema changes must be additive** — user databases at `~/.job-radar/job-radar.sqlite` persist across updates; never DROP, RENAME, or retype columns. New columns go in `schema.sql` + `_ensure_columns()` in `db/client.py`. Full rules in SYSTEM.md.
- Build not notarised — first-launch requires right-click → Open
- DMG launch was smoke-tested under automation: React shell, onboarding API, onboarding completion with blockers, needs-review source persistence, and blocklist persistence all passed. A full manual double-click/install test is still needed for window lifecycle, first scan with real URLs, and Gatekeeper behavior.
- Keep `README.md`, `SYSTEM.md`, and `CLAUDE.md` manually aligned after behavior changes; avoid dynamic counts unless they are verified during the session.
