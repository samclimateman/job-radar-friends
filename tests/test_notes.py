"""Tests for the notes data layer."""

import json

import pytest

from job_radar.config.settings import get_settings
from job_radar.db.client import execute, init_db
from job_radar.notes.store import (
    archive_note,
    create_note,
    export_notes_csv,
    export_notes_json,
    export_notes_markdown,
    get_note,
    list_notes,
    list_notes_for_entity,
    list_pinned_notes,
    list_recent_notes,
    search_notes,
    soft_delete_note,
    update_note,
)


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JOB_RADAR_DATA_DIR", str(tmp_path))
    init_db()
    yield
    get_settings.cache_clear()


# ── Migration ─────────────────────────────────────────────────────────────────

def test_migration_creates_notes_table():
    rows = execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='notes'"
    )
    assert rows, "notes table not found"


def test_migration_creates_indexes():
    rows = execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_notes_%'"
    )
    names = {r["name"] for r in rows}
    assert "idx_notes_note_type" in names
    assert "idx_notes_linked_entity" in names
    assert "idx_notes_updated_at" in names


# ── Create ────────────────────────────────────────────────────────────────────

def test_create_note_basic():
    note = create_note(body="Think about EU policy track.", title="Strategy note")
    assert note["title"] == "Strategy note"
    assert note["body_markdown"] == "Think about EU policy track."
    assert note["note_type"] == "general"
    assert note["archived"] == 0
    assert note["pinned"] == 0


def test_create_note_derives_title_from_body():
    note = create_note(body="Follow up with Chatham House contact by Friday.")
    assert "Follow up with Chatham House" in note["title"]


def test_create_note_truncates_derived_title():
    note = create_note(body="A" * 100)
    assert len(note["title"]) <= 60


def test_create_note_with_all_fields():
    note = create_note(
        body="Strong advisory fit.",
        title="Flint Global",
        note_type="organization",
        linked_entity_type="organization",
        linked_entity_id="flint-global",
        tags=["advisory", "strategy"],
        pinned=True,
    )
    assert note["note_type"] == "organization"
    assert note["linked_entity_type"] == "organization"
    assert note["linked_entity_id"] == "flint-global"
    assert "advisory" in note["tags"]
    assert note["pinned"] == 1


def test_create_note_normalises_unknown_type():
    note = create_note(body="Test", note_type="unknown_type")
    assert note["note_type"] == "general"


def test_create_note_rejects_empty_body_and_title():
    with pytest.raises(ValueError):
        create_note(body="", title="")


def test_create_note_allows_empty_body_with_title():
    note = create_note(body="", title="Just a title")
    assert note["title"] == "Just a title"


# ── Read ──────────────────────────────────────────────────────────────────────

def test_get_note_returns_none_for_missing():
    assert get_note("nonexistent-id") is None


def test_get_note_returns_none_for_soft_deleted():
    note = create_note(body="Deleted note")
    soft_delete_note(note["id"])
    assert get_note(note["id"]) is None


# ── Update ────────────────────────────────────────────────────────────────────

def test_update_note_body():
    note = create_note(body="Original body")
    updated = update_note(note["id"], body_markdown="Updated body")
    assert updated["body_markdown"] == "Updated body"


def test_update_note_updated_at_changes():
    note = create_note(body="Test")
    original_ts = note["updated_at"]
    import time; time.sleep(1.01)
    updated = update_note(note["id"], title="New title")
    assert updated["updated_at"] >= original_ts


def test_update_note_tags():
    note = create_note(body="Test", tags=["old"])
    updated = update_note(note["id"], tags=["new", "tags"])
    assert updated["tags"] == ["new", "tags"]


def test_update_note_pin():
    note = create_note(body="Test")
    assert note["pinned"] == 0
    update_note(note["id"], pinned=True)
    assert get_note(note["id"])["pinned"] == 1


# ── Archive ───────────────────────────────────────────────────────────────────

def test_archive_note():
    note = create_note(body="Archive me")
    archive_note(note["id"])
    assert get_note(note["id"])["archived"] == 1


def test_archived_notes_excluded_from_default_list():
    n1 = create_note(body="Active")
    n2 = create_note(body="Archived")
    archive_note(n2["id"])
    ids = [n["id"] for n in list_notes()]
    assert n1["id"] in ids
    assert n2["id"] not in ids


def test_archived_notes_included_when_requested():
    note = create_note(body="Archived")
    archive_note(note["id"])
    ids = [n["id"] for n in list_notes(archived=True)]
    assert note["id"] in ids


# ── Soft delete ───────────────────────────────────────────────────────────────

def test_soft_delete_hides_from_all_queries():
    note = create_note(body="Delete me")
    soft_delete_note(note["id"])
    assert get_note(note["id"]) is None
    assert all(n["id"] != note["id"] for n in list_notes())
    assert all(n["id"] != note["id"] for n in list_notes(archived=True))


# ── List / queries ────────────────────────────────────────────────────────────

def test_list_recent_notes_returns_both():
    n1 = create_note(body="First note")
    n2 = create_note(body="Second note")
    recent = list_recent_notes(limit=5)
    ids = {n["id"] for n in recent}
    assert n1["id"] in ids
    assert n2["id"] in ids


def test_list_pinned_notes():
    n1 = create_note(body="Not pinned")
    n2 = create_note(body="Pinned", pinned=True)
    pinned_ids = [n["id"] for n in list_pinned_notes()]
    assert n2["id"] in pinned_ids
    assert n1["id"] not in pinned_ids


def test_list_notes_filter_by_type():
    create_note(body="General note")
    create_note(body="Strategy note", note_type="strategy")
    strategy = list_notes(note_type="strategy")
    assert all(n["note_type"] == "strategy" for n in strategy)
    assert len(strategy) == 1


def test_list_notes_for_entity():
    n_linked = create_note(
        body="Job note",
        note_type="job",
        linked_entity_type="job",
        linked_entity_id="job-123",
    )
    n_other = create_note(body="Other note")
    results = list_notes_for_entity("job", "job-123")
    ids = [n["id"] for n in results]
    assert n_linked["id"] in ids
    assert n_other["id"] not in ids


# ── Search ────────────────────────────────────────────────────────────────────

def test_search_notes_by_title():
    create_note(body="Test", title="Flint Global fit")
    create_note(body="Test", title="Unrelated note")
    results = search_notes("Flint")
    assert any("Flint" in n["title"] for n in results)
    assert all("Flint" in n["title"] or "Flint" in n["body_markdown"] or
               any("Flint" in t for t in n["tags"])
               for n in results)


def test_search_notes_by_body():
    create_note(body="Brussels networking contact", title="Note A")
    create_note(body="Unrelated content", title="Note B")
    results = search_notes("Brussels")
    assert len(results) == 1
    assert "Brussels" in results[0]["body_markdown"]


def test_search_notes_by_tag():
    create_note(body="Test", tags=["energy-security"])
    create_note(body="Other")
    results = search_notes("energy-security")
    assert len(results) == 1


def test_search_notes_excludes_archived():
    note = create_note(body="Searchable content")
    archive_note(note["id"])
    results = search_notes("Searchable")
    assert all(n["id"] != note["id"] for n in results)


# ── Export ────────────────────────────────────────────────────────────────────

def test_export_notes_json():
    create_note(body="Export test", title="My Note", note_type="strategy")
    data = json.loads(export_notes_json())
    assert isinstance(data, list)
    assert any(n["title"] == "My Note" for n in data)


def test_export_notes_csv():
    create_note(body="CSV test", title="CSV Note")
    csv_data = export_notes_csv()
    assert "CSV Note" in csv_data
    assert "title" in csv_data  # header row


def test_export_notes_markdown():
    create_note(body="# Strategy\nFocus on EU policy.", title="EU Strategy",
                note_type="strategy", tags=["eu", "policy"])
    files = export_notes_markdown()
    assert files, "no markdown files generated"
    path = next(iter(files))
    content = files[path]
    assert "strategy/" in path
    assert "title: EU Strategy" in content
    assert "# Strategy" in content


def test_export_notes_json_includes_archived():
    note = create_note(body="Archived but exportable")
    archive_note(note["id"])
    data = json.loads(export_notes_json())
    assert any(n["id"] == note["id"] for n in data)


def test_export_notes_json_excludes_soft_deleted():
    note = create_note(body="Soft deleted")
    soft_delete_note(note["id"])
    data = json.loads(export_notes_json())
    assert all(n["id"] != note["id"] for n in data)
