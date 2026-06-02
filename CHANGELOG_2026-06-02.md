# Job Radar — Development Session Summary
**Date:** 2026-06-02

This session moved the universal Job Radar first-run experience from product vision into a working v2 implementation.

## 1. Fixed Fresh Database Initialization

**Problem:** `init_db()` ran additive migrations before the base schema existed. Fresh databases failed with:

```text
sqlite3.OperationalError: no such table: sources
```

**Fix:** `job_radar/db/client.py` now:
- Detects whether base tables exist before running additive migrations.
- Creates the base schema first for fresh databases.
- Runs additive migrations after schema creation as a safe second pass.
- Uses `_table_exists()` guards so partial databases do not crash migration checks.

## 2. Universal Onboarding API

Added `job_radar/api/routers/onboarding.py` and mounted it under `/api/onboarding`.

Capabilities:
- Persist onboarding progress in local SQLite `app_state`.
- Save user name and resume from last completed step.
- Save final search strategy into the existing deterministic rubric store.
- Save source URLs through existing platform detection.
- Save source notes into `sources.notes`.
- Save LLM-suggested unverified sources as `needs_review`.
- Merge onboarding block filters into the existing local blocklist.

No cloud account, SaaS state, or required LLM API was introduced.

## 3. React Onboarding v1

Added a first-run wizard to the React app for users with zero sources.

Screens:
- Welcome
- Name your Radar
- Setup expectations
- Current role
- Ideal role
- Locations
- Search criteria
- Add core organizations
- Review strategy
- Start first scan

The app title updates locally to `[Name]'s Job Radar` after the user enters a name.

## 4. React Onboarding v2

Added the first useful expansion layer without making setup depend on an LLM API.

New v2 capabilities:
- Optional LLM organization expansion prompt.
- Copy prompt button.
- Paste LLM results into the app.
- Lightweight parser for pasted organization lists/tables.
- LLM-suggested sources marked as needing manual check by default.
- Source review table with organization, URL, priority, status, open link, and mark checked action.
- Verified/manual-check metadata persisted in onboarding state.

The core app still works without ChatGPT, Claude, Gemini, Ollama, or an API key.

## 5. Setup Quality Banner

After onboarding, the React dashboard now shows a setup quality summary:
- Radar setup: Partial / Good / Strong
- Sources added
- Verified sources
- Sources needing manual check
- Block filter status
- Scan status

This gives the user a gentle calibration signal without blocking normal app use.

## 6. Tests And Verification

Added `tests/test_onboarding_api.py`.

Verification run:

```bash
.venv/bin/pytest
# 149 passed

cd frontend && npm run build
# passed
```

## Files Changed

| File | Change |
|---|---|
| `job_radar/db/client.py` | Fixed fresh DB initialization/migration order |
| `job_radar/api/main.py` | Mounted onboarding router |
| `job_radar/api/routers/onboarding.py` | New onboarding persistence/completion API |
| `frontend/src/api.ts` | Added onboarding API types and client methods |
| `frontend/src/App.tsx` | Added onboarding v1/v2 UI and setup quality banner |
| `tests/test_onboarding_api.py` | Added onboarding persistence/completion regression tests |
| `CLAUDE.md` | Updated current state, roadmap, known issues |

## Known Follow-Up

The production frontend currently hardcodes `http://127.0.0.1:8766/api`. That is correct for the packaged Tauri path, but it makes alternate-port smoke testing awkward because a second server still talks to the canonical app API.
