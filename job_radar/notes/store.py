"""Notes data access layer.

Free-form, locally-stored notes linkable to jobs, sources, organizations,
and other app entities.  All SQL lives here — never in HTML rendering functions.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from job_radar.db.client import execute

NOTE_TYPES = frozenset({
    "general", "strategy", "goal", "organization",
    "job", "source", "application", "contact", "brainstorm",
})

LINKED_ENTITY_TYPES = frozenset({
    "job", "source", "organization", "application", "contact",
})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _derive_title(title: str | None, body: str) -> str:
    if title and title.strip():
        return title.strip()
    first_line = body.strip().splitlines()[0] if body.strip() else ""
    return first_line[:60] or "Untitled"


def _validate_note_type(note_type: str) -> str:
    t = (note_type or "").strip().lower()
    return t if t in NOTE_TYPES else "general"


def _validate_entity_type(entity_type: str | None) -> str | None:
    if not entity_type:
        return None
    t = entity_type.strip().lower()
    return t if t in LINKED_ENTITY_TYPES else None


def _serialize_tags(tags: list[str] | None) -> str:
    if not tags:
        return "[]"
    return json.dumps([str(t).strip() for t in tags if t])


def _deserialize_tags(tags_json: str) -> list[str]:
    try:
        return json.loads(tags_json or "[]")
    except (json.JSONDecodeError, TypeError):
        return []


def _row_to_dict(row: dict) -> dict:
    out = dict(row)
    out["tags"] = _deserialize_tags(out.pop("tags_json", "[]"))
    return out


# ── CRUD ──────────────────────────────────────────────────────────────────────

def create_note(
    body: str = "",
    title: str | None = None,
    note_type: str = "general",
    linked_entity_type: str | None = None,
    linked_entity_id: str | None = None,
    tags: list[str] | None = None,
    pinned: bool = False,
) -> dict:
    if not body.strip() and not (title and title.strip()):
        raise ValueError("Note must have either a title or a body.")

    note_id = str(uuid4())
    now = _now()
    derived_title = _derive_title(title, body)
    note_type = _validate_note_type(note_type)
    entity_type = _validate_entity_type(linked_entity_type)
    entity_id = linked_entity_id if entity_type else None

    execute(
        """
        INSERT INTO notes
          (id, title, body_markdown, note_type, linked_entity_type, linked_entity_id,
           tags_json, pinned, archived, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            note_id, derived_title, body, note_type,
            entity_type, entity_id,
            _serialize_tags(tags),
            1 if pinned else 0,
            now, now,
        ),
    )
    return get_note(note_id)


def get_note(note_id: str) -> dict | None:
    rows = execute(
        "SELECT * FROM notes WHERE id = ? AND deleted_at IS NULL",
        (note_id,),
    )
    return _row_to_dict(rows[0]) if rows else None


def update_note(note_id: str, **patch) -> dict | None:
    allowed = {"title", "body_markdown", "note_type", "linked_entity_type",
               "linked_entity_id", "tags", "pinned", "archived"}
    if not patch:
        return get_note(note_id)

    sets = []
    params = []

    if "note_type" in patch:
        patch["note_type"] = _validate_note_type(patch["note_type"])
    if "linked_entity_type" in patch:
        patch["linked_entity_type"] = _validate_entity_type(patch["linked_entity_type"])
    if "tags" in patch:
        sets.append("tags_json = ?")
        params.append(_serialize_tags(patch.pop("tags")))
    if "pinned" in patch:
        sets.append("pinned = ?")
        params.append(1 if patch.pop("pinned") else 0)
    if "archived" in patch:
        sets.append("archived = ?")
        params.append(1 if patch.pop("archived") else 0)

    for key, val in patch.items():
        if key in allowed:
            sets.append(f"{key} = ?")
            params.append(val)

    if not sets:
        return get_note(note_id)

    sets.append("updated_at = ?")
    params.append(_now())
    params.append(note_id)

    execute(f"UPDATE notes SET {', '.join(sets)} WHERE id = ?", tuple(params))
    return get_note(note_id)


def archive_note(note_id: str) -> None:
    execute(
        "UPDATE notes SET archived = 1, updated_at = ? WHERE id = ?",
        (_now(), note_id),
    )


def soft_delete_note(note_id: str) -> None:
    now = _now()
    execute(
        "UPDATE notes SET deleted_at = ?, updated_at = ? WHERE id = ?",
        (now, now, note_id),
    )


# ── Queries ───────────────────────────────────────────────────────────────────

def list_notes(
    note_type: str | None = None,
    archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    conditions = ["deleted_at IS NULL", f"archived = {1 if archived else 0}"]
    params: list[Any] = []

    if note_type:
        conditions.append("note_type = ?")
        params.append(_validate_note_type(note_type))

    where = "WHERE " + " AND ".join(conditions)
    rows = execute(
        f"SELECT * FROM notes {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    return [_row_to_dict(r) for r in rows]


def list_recent_notes(limit: int = 5) -> list[dict]:
    rows = execute(
        """
        SELECT * FROM notes
        WHERE deleted_at IS NULL AND archived = 0
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [_row_to_dict(r) for r in rows]


def list_pinned_notes(limit: int = 10) -> list[dict]:
    rows = execute(
        """
        SELECT * FROM notes
        WHERE deleted_at IS NULL AND archived = 0 AND pinned = 1
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [_row_to_dict(r) for r in rows]


def list_notes_for_entity(
    entity_type: str,
    entity_id: str,
    limit: int = 20,
) -> list[dict]:
    rows = execute(
        """
        SELECT * FROM notes
        WHERE deleted_at IS NULL
          AND linked_entity_type = ?
          AND linked_entity_id = ?
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (entity_type, entity_id, limit),
    )
    return [_row_to_dict(r) for r in rows]


def search_notes(query: str, limit: int = 50) -> list[dict]:
    if not query or not query.strip():
        return list_notes(limit=limit)
    q = f"%{query.strip()}%"
    rows = execute(
        """
        SELECT * FROM notes
        WHERE deleted_at IS NULL
          AND archived = 0
          AND (
            title LIKE ?
            OR body_markdown LIKE ?
            OR tags_json LIKE ?
          )
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (q, q, q, limit),
    )
    return [_row_to_dict(r) for r in rows]


# ── Export ────────────────────────────────────────────────────────────────────

def _all_notes_for_export() -> list[dict]:
    rows = execute(
        "SELECT * FROM notes WHERE deleted_at IS NULL ORDER BY updated_at DESC"
    )
    return [_row_to_dict(r) for r in rows]


def export_notes_json() -> str:
    return json.dumps(_all_notes_for_export(), indent=2, default=str)


def export_notes_csv() -> str:
    notes = _all_notes_for_export()
    if not notes:
        return ""
    buf = io.StringIO()
    fields = ["id", "title", "note_type", "linked_entity_type", "linked_entity_id",
              "tags", "pinned", "archived", "created_at", "updated_at", "body_markdown"]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for note in notes:
        row = dict(note)
        row["tags"] = ", ".join(note.get("tags") or [])
        writer.writerow(row)
    return buf.getvalue()


def export_notes_markdown() -> dict[str, str]:
    """Return a dict of {relative_path: content} for zip inclusion."""
    notes = _all_notes_for_export()
    files: dict[str, str] = {}
    for note in notes:
        note_type = note.get("note_type") or "general"
        title = (note.get("title") or "untitled").lower()
        safe_title = "".join(c if c.isalnum() or c in "-_ " else "-" for c in title)
        safe_title = safe_title.strip("-").replace(" ", "-")[:60] or note["id"][:8]
        path = f"notes_markdown/{note_type}/{safe_title}-{note['id'][:8]}.md"

        tags_yaml = "\n".join(f"  - {t}" for t in (note.get("tags") or []))
        frontmatter = (
            f"---\n"
            f"title: {note.get('title') or ''}\n"
            f"note_type: {note_type}\n"
            f"linked_entity_type: {note.get('linked_entity_type') or ''}\n"
            f"linked_entity_id: {note.get('linked_entity_id') or ''}\n"
            f"tags:\n{tags_yaml or '  []'}\n"
            f"pinned: {'true' if note.get('pinned') else 'false'}\n"
            f"archived: {'true' if note.get('archived') else 'false'}\n"
            f"created_at: {note.get('created_at') or ''}\n"
            f"updated_at: {note.get('updated_at') or ''}\n"
            f"---\n\n"
        )
        files[path] = frontmatter + (note.get("body_markdown") or "")

    return files
