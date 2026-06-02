"""Onboarding wizard."""

from __future__ import annotations

from job_radar.app.common import _esc, _page, _stats
from job_radar.scoring.store import active_rubric_values
from job_radar.source_packs.loader import list_source_packs


def render_wizard() -> str:
    stats = _stats()
    rubric = active_rubric_values()
    packs = list_source_packs()
    pack_cards = "".join(
        f"""
        <article class="jr-pack-card">
          <h3>{_esc(pack.name)}</h3>
          <p>{_esc(pack.description)}</p>
          <p class="muted">{len(pack.entries)} sources</p>
          <a class="jr-small-link" href="/source-packs#{_esc(pack.id)}">Review Pack</a>
        </article>
        """
        for pack in packs
    )
    body = f"""
    <section class="jr-band detail">
      <div class="jr-band-heading">
        <h2>Onboarding Wizard</h2>
        <a class="jr-small-link" href="/">Back to Dashboard</a>
      </div>
      <div class="jr-steps">
        {_wizard_step("Choose sources", stats["sources"] > 0, f"{stats['sources']} saved")}
        {_wizard_step("Define strategy", bool(rubric), "rubric saved" if rubric else "needed")}
        {_wizard_step("First scan", stats["jobs"] > 0, f"{stats['jobs']} jobs")}
      </div>
      <section class="jr-wizard-section">
        <h3>1. Choose An Ecosystem</h3>
        <div class="jr-pack-grid">{pack_cards}</div>
      </section>
      <section class="jr-wizard-section">
        <h3>2. Add Custom URLs</h3>
        <form method="post" action="/sources/add" class="jr-source-form">
          <label>
            <span>Organization</span>
            <input name="organization" type="text" placeholder="Optional label">
          </label>
          <label class="wide">
            <span>Career page URLs</span>
            <textarea name="urls" rows="4" placeholder="Paste one URL per line"></textarea>
          </label>
          <button class="jr-button" type="submit">Add URLs</button>
        </form>
      </section>
      <section class="jr-wizard-section">
        <h3>3. Define Strategy</h3>
        <p class="jr-help">Use the Strategy section on the dashboard for the full rubric editor.</p>
        <a class="jr-small-link" href="/#strategy">Open Strategy Editor</a>
      </section>
      <section class="jr-wizard-section">
        <h3>4. First Scan</h3>
        <form method="post" action="/ingest">
          <button class="jr-button jr-button-refresh" type="submit">Run First Scan</button>
        </form>
      </section>
      <form method="post" action="/onboarding/complete">
        <button class="jr-button" type="submit">Mark Onboarding Complete</button>
      </form>
    </section>
    """
    return _page("Onboarding", body)


def _wizard_step(label: str, done: bool, detail: str) -> str:
    return f"""
    <div class="jr-step {'done' if done else ''}">
      <strong>{_esc(label)}</strong>
      <span>{_esc(detail)}</span>
    </div>
    """
