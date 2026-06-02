"""Blocked phrases API."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/blocklist", tags=["blocklist"])

_PATH = Path(__file__).parent.parent.parent.parent / "data" / "blocked_phrases.json"


def _load() -> list[str]:
    if not _PATH.exists():
        return []
    try:
        return json.loads(_PATH.read_text())
    except Exception:
        return []


def _save(phrases: list[str]) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(sorted({p.strip() for p in phrases if p.strip()}), indent=2))


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
