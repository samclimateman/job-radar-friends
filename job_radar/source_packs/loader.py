"""Load bundled source packs."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files

import yaml


@dataclass(frozen=True)
class SourcePackEntry:
    organization: str
    url: str
    platform_hint: str
    tags: list[str]
    region: str
    last_verified: str
    confidence: str
    notes: str = ""


@dataclass(frozen=True)
class SourcePack:
    id: str
    name: str
    description: str
    entries: list[SourcePackEntry]


def list_source_packs() -> list[SourcePack]:
    root = files("job_radar.source_packs")
    packs = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.suffix not in {".yaml", ".yml"}:
            continue
        data = yaml.safe_load(path.read_text()) or {}
        entries = [
            SourcePackEntry(
                organization=str(item.get("organization", "")),
                url=str(item.get("url", "")),
                platform_hint=str(item.get("platform_hint", "")),
                tags=list(item.get("tags") or []),
                region=str(item.get("region", "")),
                last_verified=str(item.get("last_verified", "")),
                confidence=str(item.get("confidence", "")),
                notes=str(item.get("notes", "")),
            )
            for item in data.get("sources", [])
        ]
        packs.append(
            SourcePack(
                id=str(data.get("id") or path.stem),
                name=str(data.get("name") or path.stem.replace("_", " ").title()),
                description=str(data.get("description") or ""),
                entries=entries,
            )
        )
    return packs


def get_source_pack(pack_id: str) -> SourcePack | None:
    for pack in list_source_packs():
        if pack.id == pack_id:
            return pack
    return None
