# Job Radar Packaging

Job Radar is now packaged as a Tauri desktop app for macOS. The app opens a native WebView window, launches the bundled Python/FastAPI backend as a sidecar, serves the React dashboard, and stores user data locally in `~/.job-radar/`.

This is a public beta packaging flow. The app is ad-hoc signed for tester distribution, but it is not Apple Developer ID notarized yet.

## Architecture

- `src-tauri/` owns the desktop shell, window lifecycle, sidecar launch, and macOS bundle metadata.
- `frontend/` builds the React dashboard into `frontend/dist`.
- `job_radar/` remains the Python source of truth for scraping, SQLite, scoring, exports, and local API routes.
- The Tauri app serves the React/FastAPI dashboard on `127.0.0.1:8766`.
- The legacy HTML admin/settings surface runs on `127.0.0.1:8767` when needed.

## Versioning

Version metadata is centralized in `VERSION`.

Before packaging, run:

```bash
make version-check
```

To release a new version, use one of:

```bash
make version-bump-patch
make version-bump-minor
make version-bump-major
```

The version script updates and validates:

- `VERSION`
- `pyproject.toml`
- `src-tauri/Cargo.toml`
- `src-tauri/Cargo.lock`
- `src-tauri/tauri.conf.json`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/src/App.tsx` update-banner version

Normal pushes do not auto-bump the version. Version bumps are deliberate release actions.

## Build

```bash
make build-sidecar
make build-app
make build-dmg
```

Outputs:

```text
dist/job-radar-server/job-radar-server
src-tauri/target/release/bundle/macos/Job Radar.app
dist/Job Radar.dmg
```

`make build-app` runs `make version-check`, builds the React frontend, builds the Python sidecar, builds the Tauri `.app`, copies the sidecar into the bundle, and ad-hoc signs the app.

`make build-dmg` packages the signed `.app` into a drag-to-Applications DMG.

## Release Gate

Before publishing a GitHub Release:

```bash
make release-check
make build-dmg
```

`make release-check` runs the full public safety gate:

- version/name synchronization
- private-marker scan
- Ruff
- pytest
- frontend production build

## Manual QA

Run this before sending a DMG to a tester:

1. Install the DMG into `/Applications`.
2. Launch via Finder, not from the terminal.
3. Confirm first-run onboarding appears on a clean data directory.
4. Add at least one known source and one RSS/feed source.
5. Run a refresh and confirm source health is understandable.
6. Verify Jobs, Sources, Applied, Notebook, Settings, backup, and restore flows.
7. Quit the app and confirm the backend sidecar exits.
8. Relaunch and confirm existing data persists.
9. Note any Gatekeeper/right-click instructions needed by the tester.

## Not Yet Production-Grade

- No Developer ID notarization.
- No automatic updates.
- No Windows/Linux packaged installers.
- No crash reporting or telemetry by design.
- Public update banner depends on `latest-version.json` in GitHub.

These gaps are acceptable for a public beta, but they are paid-quality blockers before a wider non-technical launch.
