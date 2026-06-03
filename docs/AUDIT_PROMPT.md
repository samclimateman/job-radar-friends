# Job Radar Public Beta Audit Prompt

Use this prompt when asking an AI/code reviewer to audit the public Job Radar repo.

```text
You are auditing Job Radar, a public beta local-first desktop app for career opportunity monitoring.

Repository:
Job Radar public repo.

What this is:
Job Radar is a public, beta-tested, local-first indie desktop app. It monitors career pages and RSS feeds, stores jobs locally in SQLite, scores them against a user-defined search strategy, tracks source health, and presents results in a Tauri desktop app with a React/Tailwind frontend and FastAPI/Python backend. It is not a SaaS product, not an apply-bot, and not an autonomous AI job search agent.

Product benchmark:
Judge the repo against the standard of an independent desktop app that a non-technical user might eventually plausibly pay for. That means the bar is higher than "works for the maintainer" or "good enough for technical friends":
- calm, clear, polished UX
- trustworthy onboarding
- reliable local scanning
- transparent source health and job provenance
- robust backup/export
- no private data leakage
- no terminal exposure for ordinary users
- maintainable backend and packaging quality

Current known state:
- Public beta distributed as a macOS DMG.
- Tauri shell launches the local Python/FastAPI backend and React dashboard.
- Local SQLite database; no cloud account or server-side user data.
- React dashboard includes Jobs, Sources, Applied, and Notebook surfaces.
- Universal onboarding, source builder/review, source health, lifecycle tracking, portable backup zip, and deterministic scoring are working.
- Version/name metadata is centralized through `VERSION`; run `make version-check`.
- Public release guardrail is `make public-check`: private-marker scan, version/name check, Ruff, pytest, and frontend build.
- Release packaging gate is `make release-check`.
- Latest verified public check passed with 173 tests.
- App is ad-hoc signed, not notarized; first launch may require right-click -> Open.

Your job:
Audit the repository and produce a prioritized improvement plan, then implement the highest-leverage fixes that are safe and scoped.

Red-team posture:
Do not assume the happy path. Try to break the product, confuse the user, leak private data, corrupt local state, and produce misleading confidence. Treat "it passed tests" as useful evidence, not proof. Prefer concrete reproduction steps and file references over broad impressions.

Focus areas:

1. UX excellence
- First-run experience: Is onboarding calm, legible, forgiving, and motivating?
- Does a non-technical user understand what to do next at every step?
- Are empty states, loading states, scan progress, errors, and manual-watch states clear?
- Does the app explain why a job matched without sounding like unreliable AI?
- Are source health, confidence, broken sources, and manual-review queues visible and actionable?
- Are destructive actions guarded and reversible where appropriate?
- Are the Jobs, Sources, Applied, and Notebook surfaces coherent as one product?
- Does the UI feel like a serious desktop app rather than an internal admin panel?
- Walk through at least three concrete user journeys:
  - fresh install -> onboarding -> first scan -> first useful job decision
  - source breaks or needs manual watch -> user understands and can act
  - backup/export -> user trusts they can move or recover their data
- Look for trust killers: dead buttons, unclear saves, silent failures, unexplained scores, stale data that looks fresh, hidden scan errors, confusing beta/install copy, and irreversible actions that feel casual.

2. Backend quality and reliability
- Check database initialization, migrations, idempotency, and fresh-install behavior.
- Check ingestion failure handling: one bad source must not break the full scan.
- Check source lifecycle behavior: new, active, changed, absent, probably closed, dead, reappeared.
- Check scoring transparency and determinism.
- Check backup/export contents, restore assumptions, and data portability.
- Check API route boundaries, validation, status codes, and error messages.
- Check concurrency around browser scrapers and HTTP scrapers.
- Check package/build behavior for app bundle, sidecar, frontend assets, and local user-data paths.
- Check tests for meaningful coverage around onboarding, backup/restore, source actions, scoring, lifecycle, and packaging-sensitive paths.
- Try to identify ways local state could become inconsistent:
  - interrupted scan
  - duplicate source
  - changed source URL/platform
  - restore over an existing database
  - partial migration
  - frontend retry after backend timeout
- Confirm failures are observable to the user and recoverable without opening a terminal.

3. Security, privacy, and public-release hygiene
- Confirm the repo contains no private names, paths, source lists, notes, resumes, applications, API keys, local databases, screenshots, or personal job-search data.
- Confirm `make public-check` catches private markers and version/name drift.
- Look for path traversal, unsafe file restore/import behavior, overly broad file reads/writes, and unguarded destructive operations.
- Check that local HTTP services bind appropriately and do not expose user data beyond localhost.
- Check CORS, static-file serving, restore/import endpoints, backup paths, and source URL handling.
- Check whether untrusted scraped HTML or user-entered content can be rendered unsafely.
- Check that optional LLM/prompt flows do not require API keys, do not send data silently, and are clear to the user.
- Check that logs avoid leaking private user data unnecessarily.
- Actively test or reason through abuse cases:
  - malicious source URL or feed content
  - HTML/JS inside job titles, descriptions, notes, source names, or organization names
  - backup/restore archive containing unexpected paths or filenames
  - localhost API accessed by another local page or process
  - oversized feeds, huge descriptions, many sources, or malformed RSS/XML/JSON
  - symlink, path traversal, and overwrite attempts around backup/restore/import/export
- Check whether any public-release artifact could accidentally include local databases, caches, logs, source packs from private repos, screenshots, or generated user data.

4. Packaging and release quality
- Does the DMG/app experience feel credible for a public beta?
- Are app name, bundle identifier, version metadata, package names, and docs synchronized?
- Does `make build-app`, `make build-dmg`, `make public-check`, and `make release-check` provide a repeatable release path?
- Are ad-hoc signing and non-notarized first-launch limitations explained honestly?
- Are generated artifacts, local data, caches, and runtime files ignored appropriately?
- Are docs aligned with the actual Tauri/FastAPI/React/SQLite app architecture?
- Check that version bumps are deliberate, synchronized, and not implied by ordinary pushes.
- Check whether the app can be built from a fresh clone using documented commands.
- Identify anything that would make a beta tester doubt the app: scary install warnings with no explanation, terminal windows, broken icons, stale docs, confusing release assets, or missing recovery guidance.

5. Product strategy fit
- Prefer local-first, privacy-preserving, reliable product work over flashy AI.
- Prefer small, testable UX/backend improvements over rewrites.
- Preserve the public/private boundary. Generic product improvements belong here; private personal job-search logic does not.
- Keep the product understandable for users who are not developers.

Required output:
1. A short executive assessment: what is strong, what is risky, and whether the app feels public-beta credible.
2. Prioritized findings with severity, file references, and concrete fixes.
3. A short list of "paid-quality gaps": the things most likely to stop a normal user from trusting or paying for the app.
4. A scoped implementation plan.
5. Implement the top safe fixes if you have repo access.
6. Run relevant checks. At minimum, run `make version-check`; for public-release-impacting changes, run `make public-check`.

Evidence standard:
- Findings must include file paths and, where possible, exact lines or functions.
- For each security/privacy issue, include impact, exploit path, and a safe fix.
- For each UX issue, name the affected user journey and the trust/clarity problem.
- For each backend issue, state whether it risks data loss, stale results, broken scans, misleading ranking, or unrecoverable user state.
- If you cannot verify something, say what would be required to verify it.
- Do not count "tests pass" as a finding. Use tests to support or challenge findings.

Do not:
- Turn this into SaaS.
- Add accounts, telemetry, cloud sync, or networked user-data storage unless explicitly requested.
- Import private sources, private prompts, personal notes, applications, resumes, paths, screenshots, or data from another repo.
- Add AI features that obscure deterministic scoring or source provenance.
- Make destructive data changes without explicit user approval.
- Treat ad-hoc signing as production-grade notarization.
- Skip public-marker and version checks before release-oriented changes.
```
