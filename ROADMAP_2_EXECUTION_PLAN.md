# Job Radar 2.0 Execution Plan

Execute 2.0 in six phases. Each phase should produce something testable.

## Phase 1: Product Hardening

Goal: make the current alpha reliable enough to build on.

- Run a fresh-clone install test.
- Test 30-50 real URLs across UK, Germany, and the US.
- Record scraper success/failure by platform.
- Fix obvious source detection and ingestion failures.
- Add scan summary after refresh.
- Add clearer empty and error states.
- Add backup restore.
- Add README screenshots.
- Publish private GitHub alpha.

Exit criteria: a tech-comfortable friend can install, add sources, refresh, and understand failures without a live explanation.

## Phase 2: First-Run Wizard

Goal: replace the current empty-dashboard start with a guided setup.

Flow:

```text
Welcome -> Choose ecosystem -> Add/import sources -> Define strategy -> Review rubric -> First scan -> Dashboard
```

Build this in the existing local web UI first. Do not jump to Tauri before the flow stabilizes.

Key features:

- onboarding progress indicator
- source preview before save
- strategy narrative form
- editable rubric
- optional AI setup
- first scan summary
- skip paths
- persistent onboarding completion state

Exit criteria: a new user lands in a guided setup, not an empty dashboard.

## Phase 3: Source Packs

Goal: make Job Radar valuable before users paste anything.

Add bundled source packs:

- Brussels Policy Pack
- DC Think Tank Pack
- Climate & Energy Pack
- International Affairs Pack
- Tech Policy Pack

Each source should include:

- organization name
- career page URL
- platform hint
- tags
- region
- last verified date
- confidence
- notes

Exit criteria: user can choose a pack and start with useful sources in under two minutes.

## Phase 4: Trust Layer

Upgrade Source Health into a proper center with working sources, broken sources, zero-job sources, manual-watch sources, last successful scan, parser type, platform detected, jobs found over time, retry/edit/disable actions, and scan reports.

## Phase 5: Polished Dashboard Workflow

Add saved views, better job cards, main concern, source health indicator, quick actions, and a simple application pipeline.

## Phase 6: Desktop Packaging

Add a Tauri shell, app bundle, DMG, and eventually signing/notarization. Keep the CLI for power users.

## Immediate Sprint

1. Add scan summary after refresh.
2. Add backup restore.
3. Add onboarding completion state.
4. Create first wizard route.
5. Add one starter source pack.
6. Add source-pack preview/import UI.
7. Test with real sources.
8. Push private GitHub alpha.

## Current Execution Status

Completed in the current local app:

- scan summary after refresh
- backup restore
- onboarding completion state
- first wizard route
- Brussels Policy starter pack
- source-pack preview/import UI
- Source Health Center
- source retry, edit, disable, enable, and manual-check actions
- saved dashboard views
- polished job cards with match/concern/source status
- packaging plan
- DMG prototype script for the current app wrapper

Still not completed:

- live test with 20 real sources
- private GitHub alpha push
- real Tauri desktop shell
- signed/notarized DMG
