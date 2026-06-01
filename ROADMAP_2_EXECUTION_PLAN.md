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

Also see this feedback on this plan, then update the roadmap to a verison 3


This is a strong document. Here are the gaps — things genuinely not covered that would materially improve the product:

1. Keyboard-driven navigation
The entire UX spec is mouse-only. For daily use, keyboard shortcuts are the difference between the app feeling fast and feeling like work. A minimal set: j/k to move between jobs, s to shortlist, r to reject, o to open link, / to search. This costs almost nothing to implement against the existing card layout and dramatically changes how the app feels after a week of use.

2. Snooze / revisit later
The pipeline is New → Shortlisted → Applied → ... — all forward-moving. There's no time-based holding state. Sometimes a job is interesting but the timing is wrong, or you want to check back after a deadline passes. A Snoozed (revisit YYYY-MM-DD) status prevents good opportunities getting lost in review limbo. This would appear in a dedicated "Revisit" view when the date passes.

3. Score breakdown as a first-class UI element
The feedback says scores should be "explainable and adjustable" but doesn't specify the design. Suggesting: a single-click expand on each job card showing four rows — Strategy match / Role type / Geography / Organisation priority — each with a score and 2–3 matched/missed keywords. No LLM required, purely derived from the existing scoring engine. This directly addresses user trust ("why am I being shown this?") without any new backend work.

4. Org-level notes and awareness layer
The feedback covers job-level notes but nothing about org-level context. Users want to record "I know someone at E3G — email them before applying" or "This org is on a hiring freeze until Q3." An org notes field (attached to sources.yaml entries, surfaced in job cards) is qualitatively different from job notes and would persist across scraping cycles.

5. Background scrape service / menu bar presence
The scheduling problem is unaddressed. A desktop app where the user must remember to click "Refresh Now" is still a manual tool. The right 2.0 experience is a menu bar icon with a badge count ("3 new jobs") that runs a quiet background scan on a schedule. On macOS this is a launchd plist + a menubar item — achievable without full Tauri. If Tauri is the shell anyway, this is a natural extension of it. Worth calling out explicitly because it changes the product from "useful when I remember to open it" to "actively surfaces opportunities."

6. Inline reading pane
The feedback assumes "Open" always launches a browser tab. For rapid triage, a slide-in or side-split reading pane showing the raw job description inside the app would let users make shortlist/reject decisions without context-switching. Browser tab switching is a serious interruption rhythm at 20+ jobs per session.

7. Bulk source import
The onboarding wizard proposes adding sources via single URL form. But ecosystem packs contain 30–50 sources. There should be a YAML or CSV drop target in the onboarding flow: "Import a pack file" → validates, detects platforms, lets you toggle sources on/off before saving. This is also the export format for sharing packs between users, which the feedback mentions but doesn't connect to an import mechanism.

8. Notification / digest
Nowhere in the document is there a push signal. The app is entirely pull ("I'll open it and see"). A daily digest (local system notification on macOS, or a plain HTML email if a mail relay is available) showing "8 new jobs since yesterday, 2 closing in 3 days" changes engagement fundamentally. Without this, the app competes with user memory.

Two things I'd push back on from the doc itself:

Tauri as the only path: Tauri is right for the end-state, but the build pipeline (Rust toolchain, code signing) adds weeks. A py2app or briefcase bundle with a menu bar wrapper might be a faster intermediate step for getting to .dmg quickly without the Tauri architecture commitment.

The cover letter exclusion for 2.0: The doc correctly defers AI features for the generic product. But the framing "do not build cover letter generation" probably shouldn't apply to Sam's version of the app, where the drafting flow is already built and working. Worth keeping that distinction explicit so these roadmaps don't accidentally collapse into each other.

explain and suggest options: Tauri as the only path: Tauri is right for the end-state, but the build pipeline (Rust toolchain, code signing) adds weeks. A py2app or briefcase bundle with a menu bar wrapper might be a faster intermediate step for getting to .dmg quickly without the Tauri architecture commitment.
The core problem
The app is Python + a local web server + Datasette. You need to turn that into a .dmg that someone can drag to Applications and double-click without seeing a terminal. There are three layers to this:

Bundling — packaging Python + dependencies into a self-contained binary/app
Shell — what the user sees (menu bar icon, window, browser)
Distribution — .dmg + code signing so macOS doesn't block it
Why Tauri is the "right" but slow path
Tauri replaces the browser with a native WebView window and gives you a proper app shell — menu bar, dock icon, system notifications, auto-update. The Python backend would run as a sidecar process (Tauri launches it, manages its lifetime).

The problem: Tauri is a Rust project. Even if you never write Rust yourself, you need:

Rust toolchain installed
Xcode Command Line Tools
Apple Developer account + paid program ($99/yr) for notarization
A build config that wires Python sidecar + Tauri frontend
Testing on clean machines to catch bundling issues
That's a realistic 3–6 week setup for someone who hasn't done it before, before writing a single feature. It's the right architecture if this becomes a distributed product. It's overkill for "get this working for 10 friends."

The faster Python-native paths
Option A — PyInstaller + rumps (recommended for v0.1 friends distribution)
rumps is a tiny Python library specifically for macOS menu bar apps. PyInstaller bundles everything into a .app.


pip install rumps pyinstaller
You write a ~40-line wrapper:


import rumps
import threading
import subprocess

class JobRadarApp(rumps.App):
    def __init__(self):
        super().__init__("Job Radar", icon="icon.png")
        self.menu = ["Open Dashboard", "Refresh Now", None, "Quit"]

    @rumps.clicked("Open Dashboard")
    def open_dashboard(self, _):
        subprocess.Popen(["open", "http://127.0.0.1:8001"])

    @rumps.clicked("Refresh Now")
    def refresh(self, _):
        threading.Thread(target=run_ingest, daemon=True).start()
Then:


pyinstaller --windowed --onedir --add-data "..." app.py
# Output: dist/JobRadar.app
hdiutil create -volname "Job Radar" -srcfolder dist/JobRadar.app JobRadar.dmg
Result: a proper .app with a menu bar icon, no terminal visible, .dmg for distribution.

Catch: unsigned app means friends see a Gatekeeper warning on first open. They right-click → Open to bypass it once. For friends this is fine; for public distribution it isn't.

Timeline: 1–2 days if you already have the launch logic working (you do — launch.py exists).

Option B — Briefcase (BeeWare)
Briefcase is a higher-level tool designed specifically for packaging Python apps for distribution. Cleaner workflow than py2app:


pip install briefcase
briefcase new   # scaffolds the project
briefcase build macOS
briefcase package macOS  # produces .dmg
It handles the .app structure, Info.plist, icon, and .dmg creation in one command. The trade-off: it's more opinionated about project structure, so retrofitting an existing project takes more setup than PyInstaller.

Better choice if you want to also target Windows later (Briefcase supports Windows .msi and Linux .appimage from the same config). Worse choice if you just want macOS fast.

Option C — py2app (macOS only, older approach)
The original macOS Python bundler. Still works, still used, but the DX is worse than PyInstaller and it's effectively unmaintained. I'd skip it — PyInstaller handles everything py2app does and is actively maintained.

Comparison
PyInstaller + rumps	Briefcase	Tauri
Time to .dmg	1–2 days	2–4 days	3–6 weeks
New language needed	No	No	Rust (optional but real)
Menu bar support	Yes (rumps)	Partial (Toga or custom)	Yes (native)
Windows/Linux later	Yes (PyInstaller)	Yes (Briefcase)	Yes
Native-feeling UI	No (still browser)	No (still browser)	Yes (WebView)
Code signing	Manual codesign	Partial support	Full support
Auto-update	No	No	Yes
Right choice when	Friends, alpha	Friends + cross-platform plan	Product with users
What I'd actually do
Right now: PyInstaller + rumps → .dmg. It takes what already exists (launch.py, the server, Datasette) and wraps it in a proper menu bar app. No new architecture. Friends get a .dmg they can drag to Applications, a radar icon in their menu bar, and a one-click "Open Dashboard."

In parallel: get an Apple Developer account (free works for local signing, $99/yr for notarization). One codesign command removes the Gatekeeper right-click friction.

Later: if the product grows beyond friends and you want proper windowed UI (not browser), that's when Tauri becomes worth the build pipeline investment. At that point you'd replace the Datasette browser UI with a proper Tauri frontend, which is a genuine UX upgrade anyway.

The Tauri path isn't wrong — it's just a product decision, not a technical shortcut.
