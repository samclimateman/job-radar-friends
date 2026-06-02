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
- **Job search** — text input below view tabs, filters by title/org/location via `?q=` param; limit raised 25→200
- **Compact "why matched" column** — shows top 3 matched values (e.g. `Brussels · policy · climate`), excluded jobs get red pill, concerns shown as muted `(1 concern)` note

### What's next (prioritised plan)
1. **Split `server.py`** (1927 lines) into `handlers/` — routing only in server.py; unblocks all future work
2. **Source packs UI** — browser page + import button (YAMLs + loader.py already exist, just need UI wiring)
3. **Wire source packs into onboarding wizard** step
4. **Scan report** shown after refresh — N sources, N new, N failed
5. **Source Health Center** — zero-jobs vs error distinction, per-source actions
6. **Score verbal labels** — strong / good / possible / weak
7. **Rubric editor with preview-score** input
8. Tests: description visibility regression, notes/status survive rescan, zero-vs-error source distinction

### Known issues / debt
- `requires_browser = True` must be set manually on any scraper calling `sync_playwright()` directly (not via `PlaywrightBaseScraper`) — runner uses this to throttle to 2 concurrent browser sessions
- Build not notarised — first-launch requires right-click → Open
