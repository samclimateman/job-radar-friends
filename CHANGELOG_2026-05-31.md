# Job Radar — Development Session Summary

> Historical note: this changelog records an earlier Datasette-era implementation. The current public beta architecture is Tauri + React/Tailwind + FastAPI/Python + SQLite.
**Date:** 2026-05-31

This document summarises the improvements built in this session. Written for the generic (friends) version of the tool — all changes below are platform-agnostic and can be ported across.

---

## 1. Geo Config Refactor — Single Source of Truth

**Problem:** City/country scoring was hardcoded in two separate files (`scoring.py` and `filters.py`). Adding a new target city required editing both in the right way.

**Fix:** Extracted all geographic scores to `config/geo_config.py`. Both the scoring engine and the geographic exclusion filter now import from this single file.

**How it works:**
- `GEO_SCORES` dict in `config/geo_config.py` — hardcoded base scores for ~80 cities and regions
- `data/geo_local.yaml` — optional user-additions file, merged at runtime on top of the base scores
- `load_geo_scores()` — merges both; used by `ingestion/scoring.py`
- `build_european_pattern()` — auto-generates the European allowlist regex from positive-scored entries; used by `ingestion/filters.py`

**Score guide (positive = target, negative = excluded):**
```
+30  Brussels
+25  Berlin
+20  The Hague
+18  Amsterdam, Munich, Netherlands, Germany
+15  London, Paris, Vienna, Zurich, Geneva, Frankfurt, Hamburg
+10  Warsaw, Rome, Madrid, Austria, Switzerland
-40  US cities, Singapore, Gulf, China
```

**To add a new city:** edit `config/geo_config.py` directly, or use the Geo Targets UI (see §3).

---

## 2. Geo Targets UI in Source Admin

**New page:** `http://127.0.0.1:8765/geo-targets`

Shows all positively-scored target cities in a table (with scores and whether they're from base config or user-added). A simple form at the bottom allows adding new cities (name + aliases + score) — writes to `data/geo_local.yaml`.

**Datasette nav button:** "Geo Targets" added to the top nav bar for quick access.

**Note:** Cities added via the UI take effect on the next ingest (Refresh Now or CLI).

---

## 3. Menu Bar App — Replaces Terminal Launcher

**Problem:** The app opened a terminal window (via `osascript` hack), showed a Dock icon, and required manual ingest every time.

**Fix:** New `scripts/menubar.py` using [rumps](https://github.com/jaredks/rumps) (macOS menu bar Python library).

**What changed:**
- `Sam's Job Finder.app` now launches `menubar.py` instead of `launch.py`
- `LSUIElement = true` in `Info.plist` — no Dock icon; app lives in menu bar only
- No terminal window — runs silently as a background process

**Menu bar behaviour:**
```
◉           → idle / up to date
◉ 3         → 3 new jobs found in last scan (clears when dashboard is opened)
↻           → scan in progress
⚠           → last scan failed
```

**Menu items:**
- Scan status + last scan timestamp (non-clickable info rows)
- Open Dashboard → opens Datasette in browser
- ↻ Refresh Now → triggers ingest in background
- Quit Job Radar → terminates Datasette + source_admin cleanly

**Auto-scan on open:** Checks if last scan was >2 hours ago. If so, scans automatically in the background when the app opens. Fires a macOS notification on completion with new-job count.

This replaces the previous GitHub Actions cron job (which was failing on scheduled runs when the laptop was closed).

**Install:**
```bash
.venv/bin/python scripts/install_dock_app.py
```

---

## 4. Datasette UI — Score Breakdown

**What it does:** Click any fit score badge (e.g. `84.2 strong`) in the title column to expand an inline score breakdown panel.

**Panel shows:**
- **Strategy** — narrative keyword match score (0–100), bar chart
- **Role type** — policy/role classification score (0–100), bar chart
- **Geography** — raw geo score with +/- sign and location label
- **Org weight** — org priority (1–10) normalised, bar chart
- **Formula** — `84.2 · S×40% + R×30% + G×15% + O×15%` with tier bonus / quality penalty notes

**Implementation:** Pure JS/CSS — reads from hidden columns already present in the DOM. Zero backend changes.

---

## 5. Datasette UI — Keyboard Navigation

**What it does:** Full keyboard-driven workflow for daily triage.

| Key | Action |
|---|---|
| `j` / `↓` | Move to next job |
| `k` / `↑` | Move to previous job |
| `o` / `Enter` | Open job URL in new tab |
| `p` | Toggle reading pane (inline description) |
| `x` | Expand/collapse score breakdown |
| `s` | Shortlist |
| `r` | Reject |
| `a` | Mark applied |
| `d` | Open draft cover letter |
| `Esc` | Close pane → close help → deselect |
| `?` | Show keyboard shortcut reference |

**Focused row** gets a blue left border highlight.

**"⌨ Shortcuts" button** added to the top nav bar — opens the keyboard reference modal.

**Implementation:** Pure JS event listener on `keydown`. Skips when user is typing in an input field. No backend changes.

---

## 6. Datasette UI — Inline Reading Pane

**What it does:** Press `p` on a focused row to slide in a 400px description panel from the right side — no new browser tab, no context switch.

**Panel shows:**
- Job title, organisation, location in the header
- Full raw job description in a scrollable body

**Close:** `Esc` key or the `✕` button.

**Implementation:** Reads `col-raw_description` from the hidden DOM column. Pure JS/CSS, no extra requests. The pane is created once and reused across all rows.

---

## What's Still To Build (Sam's Version)

| # | Feature | Effort | Notes |
|---|---|---|---|
| 5 | **Snooze / revisit later** | Medium | New `snoozed` status + `snooze_until` date column + DB migration + source_admin endpoint + Datasette "Revisit" view |
| 6 | **Org-level notes** | Small | `notes:` field already in `sources.yaml` for many entries — needs surfacing in job card via export and JS |

---

## Technical Debt / Known Gaps

- `launch.py` still works as a terminal fallback (unchanged)
- `GB Energy` scraper is active: false — URL `gbe.gov.uk/careers-0` returns 404 to HTTP requests; likely JS-rendered, needs Playwright scraper or manual URL verification
- 14 orgs in the "needs manual URL verification" list (WTO, UNCTAD, ITC, ETH Zurich CSS, foraus, ZHAW, NIC, DESNZ, DBT, Cabinet Office, South Pole, ICRC, WBCSD, Swiss Re) — awaiting user-provided careers page URLs
- `rumps` added as a macOS-only dependency (`sys_platform == 'darwin'`) — does not affect non-macOS environments

---

## Files Changed (this session)

| File | Change |
|---|---|
| `config/geo_config.py` | New — single source of truth for geo scores |
| `ingestion/scoring.py` | Imports `load_geo_scores()` from geo_config |
| `ingestion/filters.py` | Imports `build_european_pattern()` from geo_config |
| `scripts/source_admin.py` | `/geo-targets` GET + POST endpoints |
| `scripts/menubar.py` | New — rumps menu bar app |
| `scripts/install_dock_app.py` | Uses menubar.py + `LSUIElement=true` |
| `pyproject.toml` | Adds `rumps>=0.4` (macOS only) |
| `data/templates/base.html` | Score breakdown + keyboard nav + reading pane + nav buttons |
| `config/sources.yaml` | 15 new sources (UK + Swiss/Geneva track) + Ditchley |
| `ingestion/sources/custom/mpp.py` | New — Mission Possible Partnership scraper |
| `ingestion/sources/custom/geneva_association.py` | New — Geneva Association inline scraper |
| `ingestion/runner.py` | Registers MPP + GenevaAssociation scrapers |
| `PROFILE.md` | New — job search strategy reference doc |
| `SWISS_EXPANSION.md` | New — Swiss/Geneva org expansion reference doc |
