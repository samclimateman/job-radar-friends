"""Notes CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from job_radar.notes.store import (
    archive_note,
    create_note,
    get_note,
    list_deleted_notes,
    list_notes,
    list_pinned_notes,
    restore_note,
    soft_delete_note,
    update_note,
)

router = APIRouter(prefix="/notes", tags=["notes"])


class NoteCreate(BaseModel):
    body: str = ""
    title: str | None = None
    note_type: str = "general"
    tags: list[str] = []
    pinned: bool = False


class NoteUpdate(BaseModel):
    title: str | None = None
    body_markdown: str | None = None
    note_type: str | None = None
    tags: list[str] | None = None
    pinned: bool | None = None


@router.get("")
def get_notes(note_type: str | None = None, limit: int = 100):
    return list_notes(note_type=note_type, limit=limit)


@router.get("/pinned")
def get_pinned():
    return list_pinned_notes(limit=10)


@router.get("/trash")
def get_trash(limit: int = 100):
    return list_deleted_notes(limit=limit)


@router.post("", status_code=201)
def post_note(body: NoteCreate):
    try:
        return create_note(
            body=body.body, title=body.title,
            note_type=body.note_type, tags=body.tags, pinned=body.pinned,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/{note_id}")
def patch_note(note_id: str, body: NoteUpdate):
    note = get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    update_note(
        note_id,
        title=body.title,
        body_markdown=body.body_markdown,
        note_type=body.note_type,
        tags=body.tags,
        pinned=body.pinned,
    )
    return get_note(note_id)


@router.post("/{note_id}/archive")
def do_archive(note_id: str):
    archive_note(note_id)
    return {"ok": True}


@router.delete("/{note_id}")
def delete_note(note_id: str):
    soft_delete_note(note_id)
    return {"ok": True}


@router.post("/{note_id}/restore")
def do_restore(note_id: str):
    restore_note(note_id)
    return {"ok": True}
