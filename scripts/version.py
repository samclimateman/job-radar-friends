#!/usr/bin/env python3
"""Keep app names and versions synchronized across Python, Tauri, and frontend metadata."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"

EXPECTED = {
    "python_name": "job-radar",
    "rust_name": "job-radar",
    "rust_lib_name": "job_radar_lib",
    "tauri_product_name": "Job Radar",
    "tauri_identifier": "com.jobradar.desktop",
    "frontend_name": "job-radar-frontend",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def canonical_version() -> str:
    version = read_text(VERSION_FILE).strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"VERSION must be semantic x.y.z, got: {version!r}")
    return version


def load_metadata() -> dict[str, str]:
    pyproject = tomllib.loads(read_text(ROOT / "pyproject.toml"))
    cargo = tomllib.loads(read_text(ROOT / "src-tauri" / "Cargo.toml"))
    cargo_lock = tomllib.loads(read_text(ROOT / "src-tauri" / "Cargo.lock"))
    tauri = json.loads(read_text(ROOT / "src-tauri" / "tauri.conf.json"))
    frontend = json.loads(read_text(ROOT / "frontend" / "package.json"))
    frontend_lock = json.loads(read_text(ROOT / "frontend" / "package-lock.json"))
    frontend_app = read_text(ROOT / "frontend" / "src" / "App.tsx")
    current_version_match = re.search(r"const CURRENT_VERSION = '([^']+)'", frontend_app)
    if not current_version_match:
        raise SystemExit("Could not find CURRENT_VERSION in frontend/src/App.tsx")
    cargo_lock_package = next(
        package for package in cargo_lock["package"] if package["name"] == EXPECTED["rust_name"]
    )

    return {
        "VERSION": canonical_version(),
        "pyproject.name": pyproject["project"]["name"],
        "pyproject.version": pyproject["project"]["version"],
        "cargo.name": cargo["package"]["name"],
        "cargo.version": cargo["package"]["version"],
        "cargo.lib.name": cargo["lib"]["name"],
        "cargo.lock.version": cargo_lock_package["version"],
        "tauri.productName": tauri["productName"],
        "tauri.version": tauri["version"],
        "tauri.identifier": tauri["identifier"],
        "frontend.name": frontend["name"],
        "frontend.version": frontend["version"],
        "frontend.currentVersion": current_version_match.group(1),
        "frontend.lock.name": frontend_lock["name"],
        "frontend.lock.version": frontend_lock["version"],
        "frontend.lock.root.name": frontend_lock["packages"][""]["name"],
        "frontend.lock.root.version": frontend_lock["packages"][""]["version"],
    }


def validate() -> int:
    metadata = load_metadata()
    version = metadata["VERSION"]
    expected = {
        "pyproject.name": EXPECTED["python_name"],
        "cargo.name": EXPECTED["rust_name"],
        "cargo.lib.name": EXPECTED["rust_lib_name"],
        "tauri.productName": EXPECTED["tauri_product_name"],
        "tauri.identifier": EXPECTED["tauri_identifier"],
        "frontend.name": EXPECTED["frontend_name"],
        "frontend.lock.name": EXPECTED["frontend_name"],
        "frontend.lock.root.name": EXPECTED["frontend_name"],
        "pyproject.version": version,
        "cargo.version": version,
        "cargo.lock.version": version,
        "tauri.version": version,
        "frontend.version": version,
        "frontend.currentVersion": version,
        "frontend.lock.version": version,
        "frontend.lock.root.version": version,
    }

    failures = []
    for key, want in expected.items():
        got = metadata[key]
        if got != want:
            failures.append((key, got, want))

    if failures:
        print("Version/name check failed:")
        for key, got, want in failures:
            print(f"  {key}: got {got!r}, expected {want!r}")
        return 1

    print(f"Version/name check passed: {version}")
    return 0


def show() -> int:
    for key, value in load_metadata().items():
        print(f"{key}: {value}")
    return 0


def replace_version_line(path: Path, prefix: str, version: str) -> None:
    text = read_text(path)
    updated, count = re.subn(
        rf'^({re.escape(prefix)}\s*=\s*")[^"]+(")$',
        rf"\g<1>{version}\2",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise SystemExit(f"Could not update {prefix!r} in {path.relative_to(ROOT)}")
    write_text(path, updated)


def update_json(path: Path, updates: dict[str, str]) -> None:
    data = json.loads(read_text(path))
    data.update(updates)
    write_text(path, json.dumps(data, indent=2) + "\n")


def update_cargo_lock(version: str) -> None:
    path = ROOT / "src-tauri" / "Cargo.lock"
    lines = read_text(path).splitlines()
    in_target_package = False
    updated = False
    for index, line in enumerate(lines):
        if line == "[[package]]":
            in_target_package = False
        elif line == f'name = "{EXPECTED["rust_name"]}"':
            in_target_package = True
        elif in_target_package and line.startswith("version = "):
            lines[index] = f'version = "{version}"'
            updated = True
            break
    if not updated:
        raise SystemExit("Could not update root package version in src-tauri/Cargo.lock")
    write_text(path, "\n".join(lines) + "\n")


def set_version(version: str) -> int:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"Version must be semantic x.y.z, got: {version!r}")

    write_text(VERSION_FILE, f"{version}\n")
    replace_version_line(ROOT / "pyproject.toml", "version", version)
    replace_version_line(ROOT / "src-tauri" / "Cargo.toml", "version", version)
    update_cargo_lock(version)
    update_json(ROOT / "src-tauri" / "tauri.conf.json", {"version": version})
    update_json(
        ROOT / "frontend" / "package.json",
        {"name": EXPECTED["frontend_name"], "version": version},
    )
    frontend_app_path = ROOT / "frontend" / "src" / "App.tsx"
    frontend_app, count = re.subn(
        r"const CURRENT_VERSION = '[^']+'",
        f"const CURRENT_VERSION = '{version}'",
        read_text(frontend_app_path),
        count=1,
    )
    if count != 1:
        raise SystemExit("Could not update CURRENT_VERSION in frontend/src/App.tsx")
    write_text(frontend_app_path, frontend_app)
    frontend_lock_path = ROOT / "frontend" / "package-lock.json"
    frontend_lock = json.loads(read_text(frontend_lock_path))
    frontend_lock["name"] = EXPECTED["frontend_name"]
    frontend_lock["version"] = version
    frontend_lock["packages"][""]["name"] = EXPECTED["frontend_name"]
    frontend_lock["packages"][""]["version"] = version
    write_text(frontend_lock_path, json.dumps(frontend_lock, indent=2) + "\n")
    return validate()


def bump(part: str) -> int:
    major, minor, patch = [int(piece) for piece in canonical_version().split(".")]
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    elif part == "patch":
        patch += 1
    else:
        raise SystemExit("Usage: scripts/version.py bump major|minor|patch")
    return set_version(f"{major}.{minor}.{patch}")


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "check"
    if command == "check":
        return validate()
    if command == "show":
        return show()
    if command == "set" and len(argv) == 3:
        return set_version(argv[2])
    if command == "bump" and len(argv) == 3:
        return bump(argv[2])
    print("Usage: scripts/version.py [check|show|set x.y.z|bump major|minor|patch]")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
