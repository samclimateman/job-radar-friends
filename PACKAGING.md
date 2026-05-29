# Job Radar Packaging Plan

Phase 6 has two tracks: a near-term DMG for testing and a proper Tauri desktop shell for 2.0.

## Track A: Current App DMG Prototype

This creates a DMG around the current `~/Applications/Job Radar.app` wrapper.

Use it for:

- local visual testing
- sharing with one very technical tester
- validating icon, app name, and Finder flow

Do not treat it as the final installer. The current app wrapper still points at a local checkout and expects Python/dependencies to exist or be installable.

Build:

```bash
scripts/build_dmg_prototype.sh
```

Output:

```text
dist/Job Radar Prototype.dmg
```

## Track B: Tauri 2.0 App

Target user experience:

```text
Download Job Radar.dmg
Drag Job Radar to Applications
Open Job Radar
First-run wizard starts
No terminal required
```

Recommended architecture:

- Python backend remains the source of truth for scraping, SQLite, scoring, and exports.
- Tauri shell owns the desktop window, menus, app lifecycle, and packaging.
- Tauri launches the local Python backend as a sidecar or bundled executable.
- The UI initially continues to use the existing local web app.
- Later, the frontend can move into a Tauri-native webview app.

## Work Needed For Real 2.0 Packaging

1. Decide bundling strategy:
   - PyInstaller Python backend sidecar
   - or a self-contained Python runtime plus package

2. Add Tauri shell:
   - app name
   - icon
   - window sizing
   - launch local backend
   - open local URL in webview

3. Add macOS build:
   - `.app`
   - `.dmg`
   - app icon
   - minimum macOS version

4. Add trust:
   - Apple Developer ID
   - code signing
   - notarization
   - hardened runtime

5. Add installer checks:
   - app data directory created
   - database migrations run
   - first-run wizard opens
   - backend exits when app closes
   - friendly failure dialog if backend cannot start

## Phase 6 Done Criteria

- DMG opens cleanly.
- App launches without terminal.
- Normal users do not see Python.
- First-run wizard appears on a clean machine.
- Source health and backup/export still work.
- Signed/notarized build avoids alarming macOS prompts.

