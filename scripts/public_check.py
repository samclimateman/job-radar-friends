#!/usr/bin/env python3
"""Pre-public safety and quality checks for Job Radar."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PRIVATE_MARKERS = [
    "Sam Bowers",
    "Samuel",
    "sambowers",
    "Defence /Career Program",
    "MI6",
    "MIVD",
    "draft_api_key",
    "DATABASE_URL=",
    "sources.local.yaml",
    "career-ops",
]

SCAN_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".rs",
    ".toml",
    ".tsx",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}

ALLOWLIST = {
    "CLAUDE.md",  # intentionally documents differences from career-ops.
    "PORTING.md",  # documents the private/public boundary and names private markers.
    "job_radar/ingestion/confidence.py",  # provenance note for shared confidence logic.
    "scripts/public_check.py",  # contains the marker list it scans for.
    "tests/test_confidence.py",  # provenance note for shared confidence tests.
}


def run(cmd: list[str], *, cwd: Path = ROOT) -> int:
    print(f"\n$ {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=cwd, check=False)
    return completed.returncode


def collect_files() -> list[Path]:
    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    files = []
    for rel in tracked + untracked:
        path = ROOT / rel
        if rel in ALLOWLIST:
            continue
        if path.suffix in SCAN_SUFFIXES and path.is_file():
            files.append(path)
    return files


def scan_private_markers() -> int:
    print("\nScanning for private markers...")
    findings: list[tuple[str, int, str]] = []
    for path in collect_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(ROOT)
        for lineno, line in enumerate(lines, start=1):
            for marker in PRIVATE_MARKERS:
                if marker in line:
                    findings.append((str(rel), lineno, marker))

    if not findings:
        print("No private markers found.")
        return 0

    print("Private marker scan failed:")
    for rel, lineno, marker in findings:
        print(f"  {rel}:{lineno}: {marker}")
    return 1


def main() -> int:
    failures = 0
    failures += scan_private_markers()

    checks = [
        [".venv/bin/ruff", "check", "."],
        [".venv/bin/pytest"],
        ["npm", "run", "build"],
    ]
    for cmd in checks:
        cwd = ROOT / "frontend" if cmd[:3] == ["npm", "run", "build"] else ROOT
        if run(cmd, cwd=cwd) != 0:
            failures += 1

    if failures:
        print(f"\nPublic check failed: {failures} issue(s).")
        return 1

    print("\nPublic check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
