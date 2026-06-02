"""Notebook rendering."""

from __future__ import annotations

from job_radar.app.common import _esc, _page
from job_radar.notes.store import NOTE_TYPES


def render_notebook(filter_type: str = "", flash: str = "") -> str:
    from job_radar.notes.store import list_notes, list_pinned_notes

    active_type = filter_type if filter_type in NOTE_TYPES else ""
    pinned = list_pinned_notes(limit=10) if not active_type else []
    notes = list_notes(note_type=active_type or None, limit=100)

    flash_html = ""
    if flash == "created":
        flash_html = '<p class="jr-flash jr-flash-ok">Note saved.</p>'

    type_tabs = [("", "All")] + [(t, t.replace("_", " ").title()) for t in sorted(NOTE_TYPES)]
    tab_links = "".join(
        f'<a class="{"active" if active_type == key else ""}" href="/notebook{"?type=" + key if key else ""}">{_esc(label)}</a>'
        for key, label in type_tabs
    )

    pinned_items = ""
    if pinned:
        cards = "".join(_note_card(n) for n in pinned)
        pinned_items = f'<h3 class="jr-note-section-heading">Pinned</h3><div class="jr-note-grid">{cards}</div>'

    note_cards = "".join(_note_card(n) for n in notes) or '<p class="jr-help">No notes yet.</p>'

    create_form = f"""
    <details class="jr-create-note">
      <summary class="jr-small-link">+ New Note</summary>
      <form method="post" action="/notes/create" class="jr-note-form">
        <label>
          <span>Title <span class="muted">(optional — derived from first line if blank)</span></span>
          <input name="title" type="text" placeholder="Note title">
        </label>
        <label>
          <span>Body</span>
          <textarea name="body" rows="5" placeholder="Your note here..."></textarea>
        </label>
        <div class="jr-note-meta-row">
          <label>
            <span>Type</span>
            <select name="note_type">
              {_note_type_options("general")}
            </select>
          </label>
          <label>
            <span>Tags <span class="muted">(comma-separated)</span></span>
            <input name="tags" type="text" placeholder="strategy, eu-policy, follow-up">
          </label>
          <label class="jr-check-inline">
            <input name="pinned" type="checkbox" value="1">
            <span>Pin</span>
          </label>
        </div>
        <button class="jr-button" type="submit">Save Note</button>
      </form>
    </details>
    """

    body = f"""
    <section class="jr-band detail">
      <div class="jr-band-heading">
        <h2>Notebook</h2>
        <div class="jr-actions">
          <a class="jr-small-link" href="/export/notes.json">Export JSON</a>
          <a class="jr-small-link" href="/export/notes.csv">Export CSV</a>
          <a class="jr-small-link" href="/">Back to Dashboard</a>
        </div>
      </div>
      {flash_html}
      {create_form}
      <nav class="jr-view-tabs" aria-label="Note type filter">{tab_links}</nav>
      {pinned_items}
      {"<h3 class='jr-note-section-heading'>All Notes</h3>" if pinned and not active_type else ""}
      <div class="jr-note-grid">{note_cards}</div>
    </section>
    """
    return _page("Notebook", body)


def render_note_detail(note_id: str) -> str:
    from job_radar.notes.store import get_note

    note = get_note(note_id)
    if not note:
        return _page("Note Not Found", '<p class="jr-help">Note not found or deleted.</p>')

    tags_str = ", ".join(note.get("tags") or [])
    body = f"""
    <section class="jr-band detail">
      <div class="jr-band-heading">
        <h2>{_esc(note["title"])}</h2>
        <div class="jr-actions">
          <a class="jr-small-link" href="/notebook">Back to Notebook</a>
        </div>
      </div>
      <form method="post" action="/notes/update" class="jr-note-form">
        <input type="hidden" name="note_id" value="{_esc(note_id)}">
        <label>
          <span>Title</span>
          <input name="title" type="text" value="{_esc(note["title"])}">
        </label>
        <label>
          <span>Body</span>
          <textarea name="body" rows="12">{_esc(note["body_markdown"] or "")}</textarea>
        </label>
        <div class="jr-note-meta-row">
          <label>
            <span>Type</span>
            <select name="note_type">
              {_note_type_options(note["note_type"])}
            </select>
          </label>
          <label>
            <span>Tags <span class="muted">(comma-separated)</span></span>
            <input name="tags" type="text" value="{_esc(tags_str)}">
          </label>
          <label class="jr-check-inline">
            <input name="pinned" type="checkbox" value="1" {"checked" if note["pinned"] else ""}>
            <span>Pin</span>
          </label>
        </div>
        <div class="jr-actions">
          <button class="jr-button" type="submit">Save Changes</button>
        </div>
      </form>
      <div class="jr-note-danger-zone">
        <form method="post" action="/notes/archive">
          <input type="hidden" name="note_id" value="{_esc(note_id)}">
          <button class="jr-small-button secondary" type="submit">Archive</button>
        </form>
        <form method="post" action="/notes/delete">
          <input type="hidden" name="note_id" value="{_esc(note_id)}">
          <button class="jr-small-button danger" type="submit">Delete</button>
        </form>
      </div>
      <dl class="jr-metadata">
        <dt>Created</dt><dd>{_esc(note["created_at"] or "")}</dd>
        <dt>Updated</dt><dd>{_esc(note["updated_at"] or "")}</dd>
        <dt>Type</dt><dd>{_esc(note["note_type"])}</dd>
        {f'<dt>Linked to</dt><dd>{_esc(note["linked_entity_type"])} / {_esc(note["linked_entity_id"])}</dd>' if note.get("linked_entity_type") else ""}
      </dl>
    </section>
    """
    return _page(note["title"], body)


def _note_card(note: dict) -> str:
    tags = note.get("tags") or []
    tag_pills = "".join(f'<span class="pill neutral">{_esc(t)}</span>' for t in tags[:4])
    preview = (note.get("body_markdown") or "")[:160].strip()
    if len(note.get("body_markdown") or "") > 160:
        preview += "…"
    pin_icon = " 📌" if note.get("pinned") else ""
    return f"""
    <article class="jr-note-card">
      <div class="jr-card-topline">
        <span class="pill neutral">{_esc(note["note_type"])}</span>
        <span class="muted" style="font-size:0.75rem">{_esc(note["updated_at"][:10] if note.get("updated_at") else "")}</span>
      </div>
      <h3><a class="jr-link" href="/notebook/note?note_id={_esc(note["id"])}">{_esc(note["title"])}{pin_icon}</a></h3>
      <p class="muted">{_esc(preview)}</p>
      {f'<div class="jr-note-tags">{tag_pills}</div>' if tag_pills else ""}
      <div class="actions-cell">
        <a class="jr-small-link" href="/notebook/note?note_id={_esc(note["id"])}">Edit</a>
        <form method="post" action="/notes/archive" style="display:inline">
          <input type="hidden" name="note_id" value="{_esc(note["id"])}">
          <button class="jr-small-button secondary" type="submit">Archive</button>
        </form>
      </div>
    </article>
    """


def _note_type_options(selected: str) -> str:
    options = []
    for t in sorted(NOTE_TYPES):
        label = t.replace("_", " ").title()
        sel = ' selected' if t == selected else ''
        options.append(f'<option value="{_esc(t)}"{sel}>{_esc(label)}</option>')
    return "".join(options)
