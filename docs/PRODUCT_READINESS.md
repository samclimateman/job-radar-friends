# Product Readiness Plan

Job Radar is public and in beta. The next benchmark is not just "works on my machine"; it is whether a non-technical user can install it, set up a useful search, trust the results, recover from failure, and feel comfortable supporting it financially through a donation or indie-app purchase.

This document captures what needs to be true before Job Radar feels pay-worthy.

## Product Promise

Job Radar should be a local-first job-search assistant that helps users track organizations, scan job boards, score roles against their own strategy, and understand why each role is or is not worth attention.

The product should feel:

- trustworthy with personal career data
- calm and understandable during setup
- reliable when sources fail
- transparent about scoring and exclusions
- useful without requiring technical knowledge

## Pay-Worthy Benchmark

A user should be able to:

1. Install Job Radar without developer tools.
2. Complete onboarding in one sitting.
3. Define the locations, roles, themes, and blockers that matter to them.
4. Add or accept a useful set of sources.
5. Run a scan and understand what happened.
6. Open job links reliably.
7. See why a job matched, was downgraded, or was excluded.
8. Recover from broken sources or failed scans.
9. Back up, restore, or export their data.
10. Understand what data stays local and what data leaves the machine.

## Readiness Areas

### 1. Install And Update Flow

Current users should not need to understand Git, Python, Node, or Tauri.

Needed:

- DMG or equivalent install artifact.
- Clear first-launch instructions for unsigned builds until signing exists.
- Version visible in-app.
- Public changelog tied to releases.
- Update notice that tells users what changed and where to download.
- Rollback path if a release breaks.

### 2. First-Run Setup

Onboarding is the product's first trust moment.

Needed:

- Better explanation of local-first data handling.
- A location policy users can define themselves.
- Clear source setup: suggested sources, user-added sources, and "needs review" sources.
- AI setup that explains local model vs API key tradeoffs.
- A final review screen that shows the user's strategy before first scan.

### 3. Location Policy

Public Job Radar must not hardcode Sam's preferences. Users should decide where they are willing to work.

Recommended model:

- `Flexible`: locations affect score only.
- `Prefer`: target locations rank higher; unknown locations remain visible.
- `Strict`: only target locations, mixed target locations, and approved remote policies stay active.

Remote policy should be explicit:

- `Any remote`
- `Only remote in target region`
- `No remote-only roles`

Unknown-location policy should be explicit:

- `Keep unknown`
- `Review unknown`
- `Exclude unknown`

This keeps the public product configurable while allowing strict users to say, for example, "I only want London, Berlin, Brussels, or remote UK/EU."

Implemented in beta:

- Users can choose `Flexible`, `Prefer`, or `Strict`.
- Users can choose `Any remote`, `Target-region remote`, or `No remote-only`.
- Users can choose whether unknown locations are kept, reviewed, or excluded.
- `No remote-only` excludes plain remote roles regardless of location strictness.
- Existing users default to `Flexible`, `Any remote`, and `Keep unknown` so old behavior is preserved.
- Scoring explanations include matched, downgraded, review, or exclusion reasons.

### 4. Source Reliability

Users will forgive broken sources if the app explains what happened and offers a path forward.

Needed:

- Source health summary on the main screen.
- Clear error state for each failed source.
- Retry and disable controls.
- "Needs review" queue for sources that parse poorly.
- Last successful scan timestamp per source.
- Scan progress that does not look frozen.

### 5. Scoring Transparency

The app should explain its decisions in plain language.

Needed:

- "Why this matched" on each job.
- "Why this was excluded" for excluded jobs.
- Distinguish hard blockers from soft downgrades.
- Show location, role, theme, seniority, and keyword contributions.
- Let users preview a sample job against their strategy.

### 6. Data Safety

Job search data is personal and stressful. Users need confidence that they will not lose it.

Needed:

- Backup and restore exposed clearly in the UI.
- Export jobs, applications, notes, and sources.
- Import or restore workflow tested from packaged app.
- Trash behavior for notes and possibly dismissed jobs.
- No accidental destructive actions without confirmation.

### 7. Privacy And Security

The product should be explicit about data boundaries.

Needed:

- Local-first privacy note in onboarding and README.
- Explain which actions contact external job boards.
- Explain AI behavior: local model vs remote API.
- Never include secrets in diagnostics or logs.
- Continue safe-source URL protections.
- Diagnostics bundle should redact personal data by default.

### 8. Support Loop

Beta users need an easy way to report confusion.

Needed:

- Feedback link or issue template.
- Diagnostics export for support.
- Beta feedback questions in the app or docs.
- Known issues section.
- Small changelog per beta release.

### 9. Payment Or Donation

Do not overbuild licensing early.

Good first step:

- Ko-fi, GitHub Sponsors, Gumroad, or Buy Me a Coffee link.
- Simple wording: "If this saves you time, support development."
- No feature gating until there is clear demand.

Later:

- Paid build or license key only if users ask for a more polished supported version.

## What Can Be Done Today

Highest-leverage actions that are realistic now:

1. Add a configurable location policy to onboarding/settings. [done]
2. Make scoring/exclusion explanations clearer in the job detail panel.
3. Add a privacy/local-first panel to onboarding.
4. Add a diagnostics/feedback link for beta users.
5. Tighten source-health UX so failed scans are obvious and actionable.
6. Update README and FRIEND_INSTALL with a beta-support/donation section.
7. Create a release checklist for public beta builds.

## Suggested Next Sprint

1. Implement location policy fields in the rubric model. [done]
2. Surface those fields in onboarding and settings. [done]
3. Apply location policy during scoring and exclusion. [done]
4. Add tests for flexible/prefer/strict modes. [done]
5. Improve job detail explanations so users can see how location policy affected the result.
6. Update docs and beta feedback prompts.
