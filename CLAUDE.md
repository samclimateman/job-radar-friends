# Job Radar 4 Friends — Claude Context

> This file is auto-loaded by Claude Code. Update the **Current State** section at the end of each working session.

## What this is

A distributable version of career-ops for non-technical friends. Packaged as a macOS `.dmg` via Tauri. Users install it like a normal app — no terminal, no Python environment visible. Local SQLite, local Python backend, React/Tailwind dashboard.

Full system notes (browser scraper rules, concurrency model) in [SYSTEM.md](SYSTEM.md). Roadmap and product direction in [ROADMAP_2_0.md](ROADMAP_2_0.md).

## Key differences from career-ops (Sam's version)

- **SQLite** not PostgreSQL — simpler, no service to manage
- **Tauri desktop shell** — wraps the Python server, no terminal for users
- **RSS connector** — additional scraper type (`ingestion/sources/rss.py`)
- **SmartRecruiters scraper** — additional platform (`ingestion/sources/smartrecruiters.py`)
- **No Datasette** — React dashboard only (FastAPI backend)
- **No Ollama/AI classification** — scoring is deterministic only
- **No personal profile/scoring tuning** — generic ecosystem packs instead

## Stack

- Python backend + SQLite via `job_radar/` package
- FastAPI HTTP layer
- React/Tailwind frontend (`frontend/`)
- Tauri shell (`src-tauri/`)
- Platform scrapers: Greenhouse, Lever, Personio, Ashby, Workable, RSS, SmartRecruiters + PlaywrightBaseScraper for JS-rendered sites

## Building and packaging

```bash
make build        # build DMG
make test         # run test suite (40 tests, offline)
```

Signing: ad-hoc signing in Makefile. Not notarised — friends need to right-click → Open on first launch.

---

## Current State (update each session)

**Last updated:** 2026-06-02

### Phase history
- **Sprint 1–3:** Tauri shell, RSS connector, lifecycle tracking, confidence scoring, dashboard surfaces, source packs
- **Phase 1 (May 2026):** Schema, data layer, SQLite export, 32 tests
- **Phase 2 (May 2026):** Notebook UI, CRUD routes, 8 new tests

### What's working
- Full ingestion pipeline: fetch → filter → score → upsert → stale detection
- Platform scrapers: Greenhouse, Lever, Personio, Ashby, Workable, RSS, SmartRecruiters
- Tauri desktop shell — opens React dashboard, no terminal visible
- Notebook/notes UI with CRUD routes
- Source health view in dashboard
- Confidence scoring + lifecycle tracking (discovered → reviewing → applied etc.)
- macOS DMG build with ad-hoc signing

### What's next (from ROADMAP_2_0.md)
1. **Onboarding wizard** — choose ecosystem, add sources, define strategy, generate rubric, first scan
2. **Curated ecosystem packs** — Brussels Policy, DC Think Tank, Climate & Energy etc. (preloaded source lists with tags + last-verified dates)
3. **Source Health Center** — per-source status, parser type, last checked, failures visible
4. **Polished dashboard** — ranked cards, new-since-last-scan, closing soon, calm card UI
5. **Lightweight application workflow** — shortlist → reviewing → applied → interviewing → rejected
6. **Import/export** — CSV export, backup/restore, source pack sharing

### Known issues / debt
- `requires_browser = True` must be set manually on any scraper calling `sync_playwright()` directly (not via `PlaywrightBaseScraper`) — runner uses this to throttle to 2 concurrent browser sessions
- Build not notarised — first-launch requires right-click → Open
