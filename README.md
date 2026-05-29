# Job Radar

Local-first career opportunity monitoring and explainable fit scoring.

Job Radar is not an apply-bot. It tracks career pages, stores scraped jobs locally,
and ranks opportunities against a user-defined search strategy.

## v0.1 Core Loop

career-page URLs -> source detection -> ingestion -> SQLite storage -> deterministic scoring -> explainable dashboard -> source health visibility

## Quick Start

For local testing on macOS, double-click:

```text
Install Job Radar.command
```

That creates or repairs the local virtual environment, installs Job Radar, creates
`~/Applications/Job Radar.app`, and opens it. After that, use:

```text
Open Job Radar.command
```

or open `~/Applications/Job Radar.app` from Finder and keep it in the Dock.

Manual equivalent:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/job-radar setup
.venv/bin/job-radar doctor
.venv/bin/job-radar install-app
.venv/bin/job-radar start
```

The app stores data in `~/.job-radar` by default. It uses SQLite, so there is no
database server to install.

`job-radar install-app` creates `~/Applications/Job Radar.app`, which can be
kept in the Dock like any other Mac app. Launcher logs are written to
`~/.job-radar/launcher.log` if the app fails to open.

## Current v0.1 Flow

1. Start Job Radar.
2. Paste career-page URLs.
3. Save a search strategy/rubric.
4. Optionally save API provider settings in the local `.env`.
5. Refresh sources.
6. Review ranked jobs and source health.

Supported API/static sources:

- Greenhouse
- Lever
- Workable
- SmartRecruiters
- Ashby
- Personio

Deferred/manual-watch sources:

- Workday
- login-only portals
- brittle client-side pages
- unknown generic pages

## Non-Negotiables

- The app must never generate, infer, or fabricate jobs.
- Every job must trace back to a source URL and scrape run.
- Scores are fit scores against a declared strategy, not qualification judgments.
- Unknown sources degrade to manual watch or needs review.
- Scraper failures are visible and non-fatal.
- Excluded and stale jobs stay inspectable.
- User data stays local by default.

## Useful Commands

```bash
job-radar setup
job-radar start
job-radar sources add https://jobs.lever.co/example
job-radar sources list
job-radar ingest
job-radar backup
job-radar install-app
```

## Release Planning

- [Publish checklist](PUBLISH_CHECKLIST.md)
- [2.0 roadmap](ROADMAP_2_0.md)
- [2.0 execution plan](ROADMAP_2_EXECUTION_PLAN.md)
- [Packaging plan](PACKAGING.md)
