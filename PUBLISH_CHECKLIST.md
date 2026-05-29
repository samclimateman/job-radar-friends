# Job Radar Publish Checklist

This checklist is for getting Job Radar from local prototype to a GitHub repo that tech-comfortable friends can try without hand-holding.

## Current Readiness

Job Radar is close to a shareable alpha, not yet a polished public product.

Good enough for:

- a private GitHub repo
- technically comfortable friends
- macOS users willing to run a command file or a few terminal commands
- testing 10-50 career-page URLs
- validating the core loop and UX

Not yet good enough for:

- non-technical users
- public launch
- signed one-click install
- guaranteed scraping across arbitrary career pages
- Windows users
- browser-heavy scraping by default

## Before Publishing To GitHub

Required:

- Confirm repo name: `job-radar` or `job-radar-friends`.
- Keep the repo private at first.
- Decide license before making the repo public.
- Add all source files, tests, docs, and command launchers.
- Do not commit `.venv`, `.DS_Store`, caches, local databases, or `~/.job-radar`.
- Run the full test suite.
- Run ruff.
- Confirm GitHub Actions CI passes.
- Run `job-radar doctor`.
- Run the macOS app installer from a clean checkout path.
- Confirm `~/Applications/Job Radar.app` points to the current checkout path.
- Confirm the app opens the dashboard.
- Add 5-10 real sources and run a refresh.
- Check Source Health after refresh.
- Export CSV and database backup once.

Recommended:

- Create a short demo source list for friends to test safely.
- Add screenshots to the README.
- Add a known limitations section.
- Add a troubleshooting section for macOS security prompts.
- Add a release tag such as `v0.1.0-alpha`.
- Add GitHub issues for known next work instead of hiding gaps.

## QC Matrix

### Install

- Fresh clone works on macOS.
- `Install Job Radar.command` is executable.
- Command file creates `.venv` when missing.
- Command file installs dependencies.
- Command file installs `~/Applications/Job Radar.app`.
- App launcher writes failures to `~/.job-radar/launcher.log`.
- App launcher does not point at an old local path.

### App Startup

- `job-radar setup` initializes local data.
- `job-radar doctor` reports expected paths.
- `job-radar start` opens local dashboard.
- Dock app launches local dashboard.
- If port is already in use, the failure is understandable.

### First-Run UX

- User can paste multiple URLs.
- User can preview source detection before saving.
- User can save URLs.
- User can save strategy/rubric from the UI.
- User can optionally save OpenAI, Anthropic, or Ollama settings.
- User can run first refresh.
- Empty states are calm and clear.

### Ingestion

- Greenhouse works.
- Lever works.
- Workable works.
- SmartRecruiters works.
- Ashby works.
- Personio works.
- Unknown URLs degrade to needs review or manual watch.
- Workday degrades to manual watch for now.
- Failed sources do not crash the full run.
- No scraper fabricates jobs.

### Scoring

- Saved strategy is active.
- Ingested jobs receive deterministic scores.
- Score explanations cite matched rules.
- Dealbreakers exclude without hiding the job.
- Negative keywords downgrade.
- Excluded/stale jobs remain inspectable.

### Source Health

- Each source shows platform, parser, status, last checked, jobs found, new jobs, and error status.
- Retry one source works.
- Mark manual watch checked works.
- Broken URLs are visibly flagged.

### Data

- Jobs trace to source URL and scrape run.
- CSV export works.
- Source export works.
- Database backup works.
- Local data stays under `~/.job-radar`.
- API keys are saved only to local `.env`.

### Tests

Run:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
```

Expected before sharing:

```text
30 passed
All checks passed!
```

## GitHub Publish Steps

1. Review `git status --short`.
2. Stage only intended files.
3. Commit as `Initial Job Radar alpha`.
4. Create a private GitHub repo.
5. Push `main`.
6. Add a README screenshot and short install instructions.
7. Create release tag `v0.1.0-alpha`.
8. Invite 2-3 testers.

## Known Alpha Limitations

- macOS only for the friend-friendly path.
- Not code signed or notarized.
- Not a true DMG installer yet.
- No auto-update.
- Browser/Playwright scraping is not enabled by default.
- Workday is manual-watch/deferred.
- LLM setup exists, but scoring is intentionally deterministic.
- Source packs are not built yet.
- No restore UI for backups yet.

## Ship Criteria For Friend Alpha

Ship privately when:

- Fresh clone/install works.
- Dashboard opens from `Job Radar.app`.
- At least six platform scrapers pass tests.
- Real-world refresh works on a small source set.
- Source failures are visible and non-fatal.
- Backup/export works.
- README and friend install docs are clear.
