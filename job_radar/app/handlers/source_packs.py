"""Source pack browsing and import."""

from __future__ import annotations

from job_radar.app.common import _esc, _page
from job_radar.ingestion.source_detection import detect_source
from job_radar.ingestion.source_store import add_source
from job_radar.source_packs.loader import get_source_pack, list_source_packs


def render_source_packs() -> str:
    packs = list_source_packs()
    sections = []
    for pack in packs:
        rows = []
        for entry in pack.entries:
            detection = detect_source(entry.url)
            tags = ", ".join(entry.tags)
            rows.append(f"""
            <tr>
              <td>
                <label class="jr-check-row">
                  <input type="checkbox" name="source_url" value="{_esc(entry.url)}" checked>
                  <span><strong>{_esc(entry.organization)}</strong><br><span class="muted">{_esc(entry.url)}</span></span>
                </label>
              </td>
              <td>{_esc(entry.region)}</td>
              <td>{_esc(detection.platform)}</td>
              <td>{_esc(entry.confidence)}</td>
              <td class="muted">{_esc(tags)}</td>
            </tr>
            """)
        sections.append(f"""
        <section class="jr-band" id="{_esc(pack.id)}">
          <div class="jr-band-heading">
            <div>
              <h2>{_esc(pack.name)}</h2>
              <p class="jr-help">{_esc(pack.description)}</p>
            </div>
          </div>
          <form method="post" action="/source-packs/import">
            <input type="hidden" name="pack_id" value="{_esc(pack.id)}">
            <div class="jr-table-wrap">
              <table>
                <thead><tr><th>Source</th><th>Region</th><th>Detected</th><th>Confidence</th><th>Tags</th></tr></thead>
                <tbody>{''.join(rows)}</tbody>
              </table>
            </div>
            <button class="jr-button" type="submit">Import Selected Sources</button>
          </form>
        </section>
        """)
    return _page("Source Packs", "".join(sections) or '<p class="jr-help">No source packs bundled yet.</p>')


def import_source_pack(pack_id: str, selected_urls: set[str] | None = None) -> int:
    pack = get_source_pack(pack_id)
    if not pack:
        return 0
    selected = selected_urls or {entry.url for entry in pack.entries}
    count = 0
    for entry in pack.entries:
        if entry.url not in selected:
            continue
        add_source(entry.url, organization=entry.organization)
        count += 1
    return count
