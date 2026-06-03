# Job Radar Public Beta Publish Checklist

This checklist is for shipping the public `job-radar-friends` repo as a macOS beta DMG. The benchmark is no longer "technical friends can run it from a checkout"; it is "a normal beta tester can install, understand, trust, and recover from mistakes."

## Release Gate

Run before every release candidate:

```bash
make release-check
```

Expected:

- version/name metadata is synchronized
- private-marker scan passes
- Ruff passes
- pytest passes
- frontend production build passes

If the release changes app identity or version, run a deliberate bump first:

```bash
make version-bump-patch
make version-check
```

Normal commits and pushes do not bump versions automatically.

## Build

```bash
make build-dmg
```

Confirm these artifacts exist:

```text
src-tauri/target/release/bundle/macos/Job Radar.app
dist/Job Radar.dmg
```

## Public Repo Hygiene

- Repo is public intentionally.
- License and README are present.
- README says this is a local-first public beta, not SaaS.
- README explains ad-hoc signing and first-launch right-click if needed.
- No private source lists, notes, resumes, applications, cover letters, screenshots, local paths, caches, databases, API keys, or private prompts are committed.
- `latest-version.json` points to the intended GitHub Release page.
- Release notes explain beta limitations plainly.

## Manual Install QA

Use Finder and the DMG, not a terminal-only launch:

1. Open `dist/Job Radar.dmg`.
2. Drag `Job Radar.app` into `/Applications`.
3. Launch from `/Applications`.
4. Confirm the Tauri window opens without a terminal.
5. On a clean `~/.job-radar/`, confirm onboarding appears.
6. Complete onboarding with realistic criteria and sources.
7. Confirm block filters and criteria persist after restart.
8. Add a known ATS source and an RSS/feed source.
9. Run the first scan.
10. Confirm source health explains failures without breaking the full scan.
11. Triage a job through shortlist/reject/applied.
12. Create, edit, export, and archive a notebook note.
13. Create a backup ZIP.
14. Restore from a backup ZIP or raw database in a disposable data directory.
15. Quit and confirm the backend sidecar stops.

## Product Trust QA

Check the app like a beta tester:

- Onboarding has no dead ends.
- Empty states explain what changed and what action is available.
- Errors are visible, specific, and recoverable.
- Destructive actions are confirmed or undoable.
- Scores explain why a job matched without pretending to judge the user.
- Stale or failed source data does not look fresh.
- Backup/export gives the user confidence that the app is local and recoverable.

## Security And Privacy QA

- `make release-check` passes.
- Unsafe local mutation requests are rejected.
- User-entered URLs reject local/private/file/credential-bearing targets.
- Scraped/user-entered content is escaped before rendering.
- Backup/restore rejects unexpected archive formats.
- `.env`, local databases, cache files, and runtime logs are ignored.
- No private markers are present in code, docs, release notes, or screenshots.

## Release Steps

1. Decide version bump level.
2. Run `make version-bump-patch`, `make version-bump-minor`, or `make version-bump-major`.
3. Update `latest-version.json` and release notes for the intended public version.
4. Run `make release-check`.
5. Run `make build-dmg`.
6. Manually QA the DMG from `/Applications`.
7. Commit version/docs/release changes.
8. Tag the release, for example `v0.1.1`.
9. Upload `dist/Job Radar.dmg` to GitHub Releases.
10. Reopen the installed app and confirm the update banner behaves as intended.

## Known Beta Limitations

- macOS only.
- Ad-hoc signed, not notarized.
- No automatic updater.
- Browser-heavy scraping is intentionally constrained.
- Workday and highly dynamic sites may require manual watch.
- No accounts, sync, telemetry, or cloud backup.
