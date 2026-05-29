# Live QC Results

Date: 2026-05-29

This was an isolated live test using:

```text
JOB_RADAR_DATA_DIR=/tmp/job-radar-live-qc-network-2
```

The user's normal local Job Radar data was not touched.

## 20-Source Test Set

20 real career-page URLs were added:

- 16 API-backed active sources
- 4 generic/manual-watch sources

The generic/manual-watch sources were intentionally not ingested by v0.1 because they degrade to `needs_review`.

## Live Ingestion Result

```text
attempted: 16
succeeded: 7
failed: 9
jobs_found: 1098
new_jobs_found: 1098
total_sources: 20
manual_watch: 4
scored_jobs: 1098
```

## What Worked

- Greenhouse worked strongly.
- Successful Greenhouse boards produced real jobs and deterministic scores.
- Some Workable sources completed cleanly, including zero-job boards.
- SmartRecruiters completed after detail-fetch capping was added.
- Manual-watch/generic sources stayed visible instead of failing silently.
- Source Health recorded failures and did not crash the full run.

## Issues Found

- Some test source slugs were stale or invalid:
  - `grammarly` Greenhouse returned 404.
  - `pleo` Workable returned 404.
  - `anduril`, `ramp`, and `scaleai` Lever returned 404.
- Ashby changed or behaves differently from the previously mocked endpoint:
  - old endpoint returned 401 in live QC.
  - scraper was updated to use `posting-api/job-board/{org_slug}`.
  - one live Ashby smoke test then hit a read timeout, so Ashby should be treated as high-value but still needing more live validation.
- Very large boards can produce hundreds of jobs; this is useful but needs better UX filters and perhaps optional per-source caps.

## Fixes Made During QC

- SmartRecruiters detail fetching is now capped so large company boards cannot dominate manual refresh.
- Ashby scraper now targets the public `posting-api/job-board/{org_slug}` endpoint and supports the live `jobs` payload shape.

## Recommendation Before Wider Sharing

Private GitHub alpha is reasonable after this QC, but testers should be told:

- Greenhouse is currently the strongest live platform.
- Ashby is implemented but should be considered experimental until more boards are tested.
- Some user-pasted URLs will be stale, empty, or manual-watch.
- Source Health is expected to surface these problems rather than hide them.

