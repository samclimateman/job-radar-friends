"""Blocked phrases API."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from job_radar.config.settings import get_settings

router = APIRouter(prefix="/blocklist", tags=["blocklist"])


def _path():
    return get_settings().data_dir / "blocked_phrases.json"


def _load() -> list[str]:
    path = _path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


def _save(phrases: list[str]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted({p.strip() for p in phrases if p.strip()}), indent=2))


class PhraseBody(BaseModel):
    phrase: str


@router.get("")
def get_blocklist() -> list[str]:
    return _load()


@router.post("", status_code=201)
def add_phrase(body: PhraseBody) -> list[str]:
    phrase = body.phrase.strip()
    if not phrase:
        raise HTTPException(status_code=422, detail="Phrase cannot be empty")
    phrases = _load()
    if phrase.lower() not in [p.lower() for p in phrases]:
        phrases.append(phrase)
        _save(phrases)
    return _load()


@router.delete("/{phrase}")
def remove_phrase(phrase: str) -> list[str]:
    phrases = [p for p in _load() if p.lower() != phrase.lower()]
    _save(phrases)
    return _load()
