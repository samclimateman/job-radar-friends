# Security Audit - 2026-06-04

## Scope

Repository: `Job Radar 4 Friends`

Focus areas:

- Local FastAPI and legacy HTML server exposure
- Source URL validation and SSRF protections
- Backup, restore, export, and diagnostics handling
- Tauri command surface and app security config
- Secret leakage and public-release hygiene
- Python, npm, and Rust dependency posture where tooling was available

## Summary

No critical vulnerabilities were found in this pass. The app has several good foundations:

- Servers bind to `127.0.0.1`.
- Browser mutation endpoints reject cross-site requests.
- User-entered source URLs reject literal localhost, private IP, file/FTP, and credential-bearing URLs.
- Diagnostics are redacted by default.
- `.env`, local databases, logs, cache files, build artifacts, and Tauri targets are not tracked.
- `npm audit` found zero vulnerabilities.
- Focused security tests and Rust compile checks passed.

The main risks are beta-hardening items rather than emergency blockers:

1. Tauri CSP is disabled.
2. Source URL validation does not resolve DNS before fetch, leaving a DNS-rebinding/host-to-private-IP gap.
3. Restore accepts arbitrary local `.zip`, `.sqlite`, or `.db` paths through the localhost API.
4. Local API read/export endpoints are intentionally unauthenticated, so any local process running as the user can read/export data while the app is running.
5. A Tauri startup warning uses `eval` with partial escaping.

## Remediation Update

Implemented after the initial audit:

- Fixed: Tauri now has an explicit CSP in `src-tauri/tauri.conf.json`.
- Fixed: source URL validation can resolve DNS and reject hostnames that resolve to private, loopback, link-local, reserved, multicast, or unspecified IPs. User-facing source add/update and ingestion paths use the DNS-aware validation path.
- Fixed: restore now stages candidate databases, runs SQLite integrity/schema validation, creates an automatic pre-restore backup, and only then replaces the active database.
- Fixed: the Tauri startup warning no longer uses `win.eval`; fallback startup warnings are passed through a URL query parameter and rendered by React.
- Considered and deferred: per-launch local API token. A useful version requires a secure bootstrap channel from Tauri/backend to React. A public token endpoint or simple cookie-only token would not stop same-user local processes, which are the actual remaining risk. Keep this as a packaging/Tauri integration task rather than a superficial API change.

## Threat Model

Primary assets:

- Local SQLite database with jobs, sources, notes, applications, status, and scoring state.
- Optional API keys in `~/.job-radar/.env`.
- Source URLs and diagnostics metadata.
- Backup ZIPs and exported CSV/JSON files.

Realistic attackers:

- A malicious webpage attempting browser-based requests to the local API.
- A malicious or compromised local process running as the same macOS user.
- A malicious source URL intended to make the app fetch local/private-network resources.
- A compromised dependency or frontend XSS path.
- Accidental public release of private data or generated artifacts.

Out of scope for this pass:

- macOS code-signing/notarization trust.
- Full binary reverse engineering.
- Dynamic fuzzing.
- Full dependency advisory scan for Python/Rust because `pip-audit` and `cargo-audit` were not installed.

## Findings

### P1 - Tauri CSP is disabled

Severity: Medium
Status: Fixed after initial audit

Original evidence:

- `src-tauri/tauri.conf.json` previously set `csp` to `null`.
- `src-tauri/tauri.conf.json` previously set `dangerousDisableAssetCspModification` to `true`.

Impact:

If user-entered content, scraped content, or a frontend dependency ever creates an XSS path, there is no CSP defense-in-depth. The current React app mostly renders text safely, but this is still an avoidable hardening gap for a desktop app handling personal data.

Remediation:

- Added an explicit CSP in `src-tauri/tauri.conf.json`.
- Removed `dangerousDisableAssetCspModification`.
- `cargo check`, frontend build, and `make public-check` passed. Packaged `.app` testing is still recommended.

### P1 - Source URL validation does not resolve DNS

Severity: Medium
Status: Fixed after initial audit

Original evidence:

- `job_radar/ingestion/source_detection.py` blocked localhost-style hostnames.
- `job_radar/ingestion/source_detection.py` only applied IP checks when the hostname itself was an IP literal.

Impact:

A malicious public hostname could resolve to a private, loopback, or link-local address at fetch time. That could let a source URL probe local/private services despite the literal-IP protections.

Remediation:

- Added DNS-aware validation for user-facing add/update paths and ingestion-time checks.
- Added mocked tests for hostnames resolving to private and public IPs.
- Redirect-time checks remain recommended for future arbitrary-URL scrapers.

### P1 - Restore accepts arbitrary local database paths

Severity: Medium
Status: Partly fixed after initial audit

Evidence:

- job_radar/api/routers/data.py:75 exposes `/api/data/restore`.
- job_radar/app/handlers/export.py:92 accepts a user-supplied path.
- job_radar/app/handlers/export.py:116 copies raw `.sqlite` or `.db` files into the app database location.

Impact:

The app is local-first, so this is not remotely exposed. However, any local process able to reach the localhost API can ask the app to replace its database with another local file. That can cause data loss or corrupted state.

Remediation:

- Restore now creates an automatic pre-restore backup.
- Restore now stages candidate files and validates SQLite integrity plus required schema before replacement.
- Restore now cleans old SQLite sidecar files around replacement.
- A Tauri file picker/token flow remains recommended instead of free-text paths.

### P2 - Local API has no app-session authentication

Severity: Low to Medium

Evidence:

- job_radar/cli.py:104 runs FastAPI on `127.0.0.1`.
- job_radar/security/local_requests.py:36 intentionally allows non-browser local clients that omit `Origin` and `Referer`.
- job_radar/api/routers/data.py:49 exposes backup/export downloads.

Impact:

Cross-site browser mutation risk is reduced by origin checks. But any local process running as the same user can still call the API while the app is running and read/export local data or mutate state.

Recommendation:

- Generate a random per-launch API token and require it for state-changing endpoints and sensitive exports.
- Pass the token to the Tauri frontend through a controlled channel or local server bootstrap.
- Keep browser cross-site checks as defense-in-depth.

### P2 - Tauri startup warning uses `eval`

Severity: Low
Status: Fixed after initial audit

Original evidence:

- `src-tauri/src/lib.rs` previously injected a warning banner with `win.eval(...)`.

Impact:

The warning string is partially escaped for backslashes, double quotes, and newlines, but it is inserted into a single-quoted JavaScript string. A path or message containing a single quote could break the script. This is a low-probability path because the message is generated locally during startup failure, but avoiding `eval` is still better desktop hardening.

Remediation:

- Removed the `win.eval` path.
- Startup warnings now pass through the fallback app URL as an encoded query parameter and render through React.

## Positive Controls Observed

- Local servers bind to `127.0.0.1`, not `0.0.0.0`.
- CORS allows only expected localhost/Tauri origins.
- Unsafe browser mutation requests are rejected.
- Source URL validation rejects:
  - non-HTTP(S) schemes
  - missing hostnames
  - credentials in URLs
  - localhost-style names
  - literal private, loopback, link-local, reserved, multicast, and unspecified IPs
- Diagnostics omit secrets and private job-search content by default.
- Public release scan excludes private markers and found no private marker issues in the latest `make public-check`.
- No tracked `.env`, database, runtime log, node_modules, or Tauri target artifacts were found.

## Tool Results

Commands run:

```bash
npm audit --audit-level=moderate
.venv/bin/ruff check .
.venv/bin/pytest tests/test_source_detection.py tests/test_local_request_protection.py tests/test_data_api.py -q
$HOME/.cargo/bin/cargo check
git ls-files | rg -n "(^|/)(\\.env|.*\\.sqlite|.*\\.db|.*\\.log|data/|src-tauri/target/|frontend/node_modules/)"
rg -n "(sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]+|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|EC|PRIVATE) KEY|password\\s*=\\s*['\\\"][^'\\\"]+|api[_-]?key\\s*=\\s*['\\\"][^'\\\"]+|token\\s*=\\s*['\\\"][^'\\\"]+)" --glob "!src-tauri/target/**" --glob "!frontend/node_modules/**" --glob "!.venv/**" .
```

Results:

- `npm audit`: `found 0 vulnerabilities`
- `ruff`: passed
- focused security tests: `27 passed`
- `cargo check`: passed
- Packaged `.app` CSP smoke test: passed after app lifecycle cleanup; sidecar releases port `8766` on macOS quit.
- tracked sensitive artifact scan: no matches
- regex secret scan: no matches

Limitations:

- `pip-audit` was not installed.
- `cargo-audit` was not installed.
- This was a code and tooling audit, not a full dynamic penetration test.

## Security Tooling Judgment

The proposed open-source security stack makes sense for this repo, with sequencing:

- Do now: Dependabot for Python, npm, Cargo, and GitHub Actions. This repo has `pyproject.toml`, `frontend/package-lock.json`, and `src-tauri/Cargo.lock`, so automated dependency update PRs are a strong fit with low maintenance cost.
- Done next: Gitleaks for secret detection, OSV-Scanner for dependency vulnerability scanning, and Semgrep Community Edition for Python/TypeScript/Rust static analysis are configured in GitHub Actions.
- Defer: Trivy until the repo has a container/image/IaC surface or a pinned/action-hardened CI plan. OSV is a cleaner first dependency scanner for this app.
- Defer: osquery/FleetDM. Useful for developer-machine visibility, but it is endpoint management rather than app hardening and does not belong in the public app repo.
- Keep in mind: GitHub Actions themselves are supply-chain dependencies. Add scanners deliberately, restrict workflow permissions, and prefer pinned action SHAs once the workflow set stabilizes.

## Recommended Next Fix Order

1. Add redirect-time checks for any future scraper that follows arbitrary user-supplied URLs.
2. Design a real per-launch local API token with secure Tauri-to-React bootstrap.
3. Watch the first Gitleaks, OSV-Scanner, and Semgrep CI runs and tune only real false positives.
4. Add `pip-audit` and `cargo-audit` to the repeatable local security checklist.
5. Consider a Tauri file picker/token flow for restore instead of free-text paths.

## Release Readiness Judgment

This is acceptable for a small friend beta if users understand it is local-first beta software. Before wider public beta or any donation/payment framing, re-test the packaged `.app` with CSP enabled and complete the local API token design.
