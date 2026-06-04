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

Evidence:

- src-tauri/tauri.conf.json:25 sets `csp` to `null`.
- src-tauri/tauri.conf.json:28 sets `dangerousDisableAssetCspModification` to `true`.

Impact:

If user-entered content, scraped content, or a frontend dependency ever creates an XSS path, there is no CSP defense-in-depth. The current React app mostly renders text safely, but this is still an avoidable hardening gap for a desktop app handling personal data.

Recommendation:

- Add an explicit CSP.
- Avoid `dangerousDisableAssetCspModification` unless there is a proven need.
- Keep `script-src` tight and avoid inline script allowances where possible.
- Retest Tauri build and local backend loading after CSP changes.

### P1 - Source URL validation does not resolve DNS

Severity: Medium

Evidence:

- job_radar/ingestion/source_detection.py:35 blocks localhost-style hostnames.
- job_radar/ingestion/source_detection.py:38 only applies IP checks when the hostname itself is an IP literal.

Impact:

A malicious public hostname could resolve to a private, loopback, or link-local address at fetch time. That could let a source URL probe local/private services despite the literal-IP protections.

Recommendation:

- Resolve A/AAAA records during validation and reject any private, loopback, link-local, multicast, reserved, or unspecified result.
- Revalidate final URLs after redirects.
- Consider validating at fetch time as well as save time, because DNS can change.
- Add tests for a mocked hostname resolving to `127.0.0.1`, `10.0.0.1`, and `169.254.x.x`.

### P1 - Restore accepts arbitrary local database paths

Severity: Medium

Evidence:

- job_radar/api/routers/data.py:75 exposes `/api/data/restore`.
- job_radar/app/handlers/export.py:92 accepts a user-supplied path.
- job_radar/app/handlers/export.py:116 copies raw `.sqlite` or `.db` files into the app database location.

Impact:

The app is local-first, so this is not remotely exposed. However, any local process able to reach the localhost API can ask the app to replace its database with another local file. That can cause data loss or corrupted state.

Recommendation:

- Before restore, always create an automatic pre-restore backup.
- Validate restored SQLite files with `PRAGMA integrity_check` and expected table/schema checks before replacing the active database.
- Prefer a Tauri file picker or selected-file token over free-text paths.
- Consider requiring an app-session token on mutation endpoints.

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

Evidence:

- src-tauri/src/lib.rs:173 injects a warning banner with `win.eval(...)`.

Impact:

The warning string is partially escaped for backslashes, double quotes, and newlines, but it is inserted into a single-quoted JavaScript string. A path or message containing a single quote could break the script. This is a low-probability path because the message is generated locally during startup failure, but avoiding `eval` is still better desktop hardening.

Recommendation:

- Replace `eval` string construction with a safer frontend event/state path.
- If `eval` must stay, serialize the message with JSON string encoding rather than manual escaping.

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
- tracked sensitive artifact scan: no matches
- regex secret scan: no matches

Limitations:

- `pip-audit` was not installed.
- `cargo-audit` was not installed.
- This was a code and tooling audit, not a full dynamic penetration test.

## Recommended Next Fix Order

1. Add DNS-resolution and redirect-time checks to source URL fetching.
2. Add a Tauri/React CSP and remove disabled asset CSP modification.
3. Add automatic pre-restore backup plus SQLite integrity/schema validation.
4. Add a per-launch local API token for sensitive exports and mutations.
5. Replace startup `win.eval` with JSON-encoded injection or a safer UI path.
6. Add `pip-audit` and `cargo-audit` to the repeatable security checklist.

## Release Readiness Judgment

This is acceptable for a small friend beta if users understand it is local-first beta software. Before wider public beta or any donation/payment framing, fix the first three items above.
