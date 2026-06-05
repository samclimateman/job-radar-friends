# OSV Rust/Tauri Advisory Triage - 2026-06-05

## Summary

Status: triaged, no emergency app release needed.

The latest OSV Scanner run reported 17 Rust advisories from `src-tauri/Cargo.lock`: 0 critical, 0 high, 1 medium, 0 low, and 16 unknown/informational. These findings are real lockfile findings, but most are not direct runtime exposure for the current downloadable macOS beta.

Key conclusion: the packaged macOS app builds through Tauri's Cocoa/WebKit path. The GTK3/glib advisories are present in the cross-platform lockfile through Tauri/Wry Linux support, but `cargo tree` for the current macOS target does not include `gtk`, `glib`, or `proc-macro-error`.

## Latest OSV Run

- Run: `27001001658`, push to `main`, commit `e86dcaf`
- Result: success because OSV is configured as report-only with `fail-on-vuln: false`
- OSV summary: `Total 17 packages affected by 17 known vulnerabilities (0 Critical, 0 High, 1 Medium, 0 Low, 16 Unknown) from 1 ecosystem.`
- Fixability: OSV says `1 vulnerability can be fixed`, but `cargo update -p glib --dry-run --manifest-path src-tauri/Cargo.toml` could not move `glib` within current dependency constraints.

## Advisory Groups

| Group | Packages | Advisory type | Exposure for current macOS beta | Decision |
| --- | --- | --- | --- | --- |
| GTK3 bindings unmaintained | `atk`, `atk-sys`, `gdk`, `gdk-sys`, `gdkwayland-sys`, `gdkx11`, `gdkx11-sys`, `gtk`, `gtk-sys`, `gtk3-macros` | RustSec informational/unmaintained | Low for the current macOS DMG. These appear in the lockfile for Linux/WebKitGTK support, not the packaged macOS target. | Accept temporarily; monitor Tauri/Wry updates. |
| `glib` unsound iterator implementation | `glib` `0.18.5`, fixed in `0.20.0` | RustSec/GHSA, CVSS 6.9 medium | Low for current macOS DMG because `glib` is not in the macOS target tree. Potentially relevant for future Linux builds. | Do not force override; wait for upstream compatible upgrade. |
| `proc-macro-error` unmaintained | `proc-macro-error` `1.0.4` | RustSec informational/unmaintained | Low. Not in current macOS target tree; build-time/proc-macro ecosystem issue. | Accept temporarily; monitor upstream. |
| `unic-*` unmaintained | `unic-char-property`, `unic-char-range`, `unic-common`, `unic-ucd-ident`, `unic-ucd-version` | RustSec informational/unmaintained | Moderate-low. `unic-ucd-ident` enters through `urlpattern -> tauri-utils`; this is a Tauri utility dependency rather than app-authored code. | Track upstream Tauri/urlpattern migration; no local fork now. |

## Evidence

Commands run:

```bash
gh run view 27001001658 --log
/Users/sambowers/.cargo/bin/cargo search tauri --limit 3
/Users/sambowers/.cargo/bin/cargo update --dry-run --manifest-path src-tauri/Cargo.toml
/Users/sambowers/.cargo/bin/cargo update -p glib --dry-run --manifest-path src-tauri/Cargo.toml
/Users/sambowers/.cargo/bin/cargo tree --manifest-path src-tauri/Cargo.toml
/Users/sambowers/.cargo/bin/cargo tree -i glib --manifest-path src-tauri/Cargo.toml
/Users/sambowers/.cargo/bin/cargo tree -i gtk --manifest-path src-tauri/Cargo.toml
/Users/sambowers/.cargo/bin/cargo tree -i proc-macro-error --manifest-path src-tauri/Cargo.toml
/Users/sambowers/.cargo/bin/cargo tree -i unic-ucd-ident --manifest-path src-tauri/Cargo.toml
```

Results:

- `cargo search tauri --limit 3` shows `tauri = "2.11.2"`, matching the lockfile. Tauri is already current.
- General dry-run update only offered routine compatible patches: `bitflags`, `chrono`, `log`, `serde_with`, `serde_with_macros`, `unicode-segmentation`, and `yoke`. It did not upgrade Tauri or the affected advisory groups.
- `cargo update -p glib --dry-run` reported `Locking 0 packages`; current constraints do not allow the fixed `glib >= 0.20.0`.
- Current-target inverse trees for `glib`, `gtk`, and `proc-macro-error` printed nothing, meaning they are not part of the current macOS target resolution.
- `unic-ucd-ident` is present through `urlpattern -> tauri-utils`, which is upstream Tauri surface rather than direct application code.

The `--target all` dependency tree probes attempted to download additional non-macOS platform crates and failed under sandbox DNS restrictions. That probe is not required for the current macOS beta decision because OSV already scans the full lockfile, and the current-target tree is enough to identify packaged-app exposure.

## Recommendation

Do now:

- Keep OSV Scanner as report-only while these are upstream/transitive findings.
- Keep Dependabot enabled for Cargo so Tauri/Wry/tauri-utils updates arrive automatically.
- Do not add local dependency overrides for GTK/glib/unic unless a concrete exploit path appears or Linux packaging becomes a release target.
- Re-run this triage when a Tauri/Wry update lands or before introducing Linux builds.

Do later:

- If shipping Linux, treat GTK/glib as real runtime surface and revisit whether the platform stack has moved from GTK3/glib `0.18` to maintained/fixed crates.
- Consider adding a short allowlist/triage note to the OSV workflow only if code scanning noise starts hiding more important findings.

