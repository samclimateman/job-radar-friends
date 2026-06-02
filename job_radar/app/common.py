"""Shared HTML helpers and DB utilities used across all dashboard handlers."""

from __future__ import annotations

import html
import socket

from job_radar.db.client import execute


def _stats() -> dict[str, int]:
    jobs = execute("SELECT COUNT(*) AS n FROM jobs")
    sources = execute("SELECT COUNT(*) AS n FROM sources")
    issues = execute(
        """
        SELECT COUNT(*) AS n
        FROM source_health
        WHERE error_status IS NOT NULL OR manual_review_needed = 1 OR likely_broken_url = 1
        """
    )
    return {
        "jobs": jobs[0]["n"] if jobs else 0,
        "sources": sources[0]["n"] if sources else 0,
        "issues": issues[0]["n"] if issues else 0,
    }


def _esc(value: str | None) -> str:
    return html.escape(value or "")


def _empty_row(text: str, columns: int) -> str:
    return f'<tr><td colspan="{columns}" class="empty">{html.escape(text)}</td></tr>'


def _split_urls(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.replace(",", "\n").splitlines() if part.strip()]


def _first(form: dict[str, list[str]], key: str) -> str | None:
    values = form.get(key)
    return values[0].strip() if values else None


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _find_free_port(start: int) -> int:
    port = start
    while _port_open(port):
        port += 1
    return port


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_esc(title)} - Job Radar</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <header class="jr-header compact">
    <div class="jr-title-wrap">
      <img class="jr-logo" src="/static/logo.png" alt="" width="76" height="76">
      <div><h1>Job Radar</h1><p class="jr-subtitle">Local opportunity monitoring</p></div>
    </div>
  </header>
  <main>{body}</main>
</body>
</html>"""


def _provider(name: str, env_name: str, url: str, link_label: str) -> str:
    return f"""
    <article class="jr-provider">
      <h3>{html.escape(name)}</h3>
      <code>{html.escape(env_name)}</code>
      <a href="{html.escape(url)}" target="_blank" rel="noreferrer">{html.escape(link_label)}</a>
    </article>
    """
