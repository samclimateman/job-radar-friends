# Job Radar 2.0 Feedback And Roadmap

## Product Direction

For 2.0, the goal should be less "add more AI" and more "turn the useful local prototype into a polished desktop product that feels trustworthy, installable, and calm."

The strongest positioning is:

> Job Radar is a local-first desktop app for monitoring fragmented career ecosystems. It helps users track selected organizations, detect new opportunities, rank jobs against a personal strategy, and understand why each role matters.

Avoid positioning it as an AI job search bot. Better language:

- A calm career radar for serious job searches.
- A local-first opportunity radar for fragmented professional ecosystems.
- A strategic monitoring tool for career pages you actually care about.

## 2.0 Priorities

### 1. Desktop Packaging

This is the biggest unlock. The app should stop feeling like a Python project and start feeling like a real product.

Target experience:

```text
Download Job Radar.dmg
Drag to Applications
Open Job Radar
Local app opens
```

Recommended path:

- Keep Python backend and SQLite core.
- Add a Tauri desktop shell.
- Bundle the local server behind the desktop app.
- Keep local app data in a predictable app directory.
- Add a simple hosted docs/download page later.

Avoid Electron unless there is a strong reason. Tauri should feel lighter and more native.

2.0 should include:

- macOS `.dmg`
- no terminal for normal users
- no visible Python environment
- app icon and proper app name
- signed app if feasible
- auto-update later, not required for 2.0
- Windows installer later

### 2. Professional Onboarding Wizard

The first-run flow should become:

```text
Welcome -> Choose ecosystem -> Add sources -> Define strategy -> Review rubric -> First scan -> Dashboard
```

Ask the minimum needed:

- What kinds of roles are you looking for?
- Where are you willing to work?
- What seniority range?
- What sectors or themes?
- What should be excluded?
- What counts as a stretch role?
- What organizations do you already care about?

Then show the generated rubric in plain English before saving:

```text
Your Radar will prioritize:
Policy, strategy, and research roles in Brussels, Berlin, London, and remote Europe.

It will downgrade:
Junior admin, sales, fundraising, and roles requiring native German.

It will flag as stretch:
Director-level roles, defence-adjacent roles, and roles requiring 8+ years.
```

This makes the product feel intelligent without making LLM reasoning the scoring engine.

### 3. Curated Ecosystem Packs

This is probably the highest-value product insight. The value is not only scraping. It is curated ecosystem monitoring.

Starter packs could include:

- Brussels Policy Pack
- DC Think Tank Pack
- Climate & Energy Pack
- International Affairs Pack
- Industrial Strategy Pack
- Tech Policy Pack
- User-defined Pack

Each source entry should include:

- organization name
- career page URL
- detected platform
- expected source type
- tags
- last verified date
- confidence level

Better user flow:

```text
Choose Brussels Policy Pack
Add 35 sources
Remove irrelevant ones
Add my own sources
Start scan
```

This is dramatically better than starting with a blank URL box.

### 4. Trust And Reliability Layer

Trust matters more than flashy AI.

Make these first-class:

- Source Health Center
- Job provenance
- Scan reports
- Broken source warnings
- Manual-watch queue
- Parser confidence
- Last successful scan

After every scan, show:

```text
42 sources checked
119 jobs found
12 new jobs
9 stale jobs
4 sources need review
2 sources failed
```

Every job card should show:

```text
Found from: E3G Careers
Platform: Greenhouse
First seen: 2026-05-29
Last checked: 2026-05-29
Source status: Live
```

Keep the non-negotiables:

- no fabricated jobs
- every job tied to source URL/source job ID/scrape run
- source failures visible
- excluded jobs inspectable
- scores explainable and adjustable

### 5. Polished Dashboard And Workflow

The 2.0 dashboard should feel like a calm workspace.

Better job cards:

```text
Senior Policy Manager, Industrial Strategy
European Climate Foundation - Brussels / Hybrid
Fit: 84

Matched: industrial policy, EU climate, senior policy, Brussels
Concern: may require deeper EU institutional network
Status: Shortlisted
```

Saved views:

- Best matches
- New since last scan
- Closing soon
- Stretch roles
- Needs review
- Excluded roles
- By organization
- By location
- By theme

Application pipeline:

```text
New -> Shortlisted -> Reviewing -> Applied -> Interviewing -> Rejected / Archived
```

Do not build a full ATS. Build just enough to replace a messy spreadsheet.

## What Not To Prioritize Yet

Avoid these until the product is trusted and easy to install:

- auto-applying
- resume generation
- cover-letter generation
- complex LLM agents
- browser automation as the default
- team/collaboration features
- cloud sync
- accounts/login
- heavy analytics
- complicated scoring models

These make the product harder to trust and harder to ship.

## Recommended 2.0 Roadmap

1. Desktop packaging
   - macOS app bundle / DMG
   - normal users do not need terminal
   - local SQLite data
   - one-click launch

2. First-run onboarding wizard
   - choose ecosystem
   - add/import sources
   - define search strategy
   - generate editable rubric
   - run first scan

3. Curated ecosystem packs
   - preloaded source lists
   - tags and categories
   - source confidence
   - last verified date

4. Source Health Center
   - source status
   - parser type
   - last checked
   - jobs found
   - new jobs
   - failures
   - manual review needed

5. Polished dashboard
   - ranked jobs
   - new jobs
   - closing soon
   - excluded/stale jobs
   - saved views
   - calm card-based UI

6. Lightweight application workflow
   - shortlist
   - reviewing
   - applied
   - interviewing
   - rejected
   - archived

7. Import/export
   - export user data
   - export source packs
   - export jobs as CSV
   - backup and restore local database

## Final Judgment

The current app is close to a useful v0.1 alpha for technical friends. The 2.0 leap is not mainly about making it smarter. It is about making it feel safe, reliable, and productized:

1. installable
2. clear onboarding
3. curated starter packs
4. visible source health
5. polished ranked workflow
6. simple application tracking
7. strong backup/export

That combination makes Job Radar feel like a serious local desktop product without turning it into a bloated SaaS or unreliable AI agent.

