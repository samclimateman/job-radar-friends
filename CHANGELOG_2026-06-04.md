# Job Radar Beta Changelog — 2026-06-04

## Trust, Safety, And Support

- Added a React Settings `Data` section with backup, jobs export, sources export, notes export, restore from local backup path, and local data folder/database path.
- Added restore confirmation before replacing the local database.
- Added a React Settings `Privacy & Security` section that explains the local-first model, external source scans, source URL safety, and API-key expectations.
- Added a React Settings `Support / Beta Feedback` section with a feedback link and diagnostics download.
- Added redacted diagnostics export with app metadata, local path metadata, aggregate counts, source health summaries, and recent scan run summaries.
- Diagnostics intentionally omit API keys, environment values, source URLs, raw job descriptions, notes, applications, and private job-search text by default.
- Added API tests for data location, backup zip download, jobs export, restore rejection, and diagnostics redaction.

## Security Hardening

- Added an explicit Tauri CSP.
- Removed Tauri startup-warning `eval`; fallback warnings now render through React.
- Added DNS-resolution checks for user-facing source URL add/update and ingestion paths.
- Hardened restore with staged database validation, SQLite integrity/schema checks, and automatic pre-restore backup.
- Considered per-launch local API token and deferred the implementation until there is a secure Tauri-to-React bootstrap path.

## v0.1.3 Public Beta Refresh

- Published a fresh downloadable macOS DMG at `https://github.com/samclimateman/job-radar-friends/releases/tag/v0.1.3`.
- Added Gitleaks, OSV Scanner, Semgrep, and Dependabot coverage for public-repo security hygiene.
- Hardened Personio XML parsing with `defusedxml`.
- Switched description-change hashes from SHA1 to SHA-256.
- Triage status: OSV and Semgrep are intentionally report-only while the initial dependency/static-analysis backlog is reviewed.
- Current feedback ask: install friction, onboarding clarity, source setup, scan trust, ranking quality, backup/export confidence, and anything that would stop a non-technical beta user from trusting the app.
