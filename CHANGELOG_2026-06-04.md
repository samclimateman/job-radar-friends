# Job Radar Beta Changelog — 2026-06-04

## Trust, Safety, And Support

- Added a React Settings `Data` section with backup, jobs export, sources export, notes export, restore from local backup path, and local data folder/database path.
- Added restore confirmation before replacing the local database.
- Added a React Settings `Privacy & Security` section that explains the local-first model, external source scans, source URL safety, and API-key expectations.
- Added a React Settings `Support / Beta Feedback` section with a feedback link and diagnostics download.
- Added redacted diagnostics export with app metadata, local path metadata, aggregate counts, source health summaries, and recent scan run summaries.
- Diagnostics intentionally omit API keys, environment values, source URLs, raw job descriptions, notes, applications, and private job-search text by default.
- Added API tests for data location, backup zip download, jobs export, restore rejection, and diagnostics redaction.
