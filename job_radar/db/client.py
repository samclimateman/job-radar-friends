"""Tiny SQLite client for Job Radar."""

from __future__ import annotations

import json
import sqlite3
from importlib.resources import files
from pathlib import Path
from typing import Any

from job_radar.config.settings import get_settings


def ensure_data_dir() -> Path:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = path or get_settings().db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path | None = None) -> Path:
    ensure_data_dir()
    db_path = path or get_settings().db_path
    schema = files("job_radar.db").joinpath("schema.sql").read_text()
    with connect(db_path) as conn:
        conn.executescript(schema)
        _ensure_columns(conn)
        _backfill_source_config(conn)
    return db_path


def execute(sql: str, params: tuple[Any, ...] = (), path: Path | None = None) -> list[dict[str, Any]]:
    with connect(path) as conn:
        cur = conn.execute(sql, params)
        if cur.description is None:
            return []
        return [dict(row) for row in cur.fetchall()]


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Apply tiny compatibility migrations for existing local v0.1 databases."""
    source_columns = {row["name"] for row in conn.execute("PRAGMA table_info(sources)").fetchall()}
    if "config_json" not in source_columns:
        conn.execute("ALTER TABLE sources ADD COLUMN config_json TEXT NOT NULL DEFAULT '{}'")


def _backfill_source_config(conn: sqlite3.Connection) -> None:
    """Populate detection config for sources created before config_json existed."""
    from job_radar.ingestion.source_detection import detect_source

    rows = conn.execute("SELECT id, url, config_json FROM sources").fetchall()
    for row in rows:
        if row["config_json"] and row["config_json"] != "{}":
            continue
        detection = detect_source(row["url"])
        conn.execute(
            """
            UPDATE sources
            SET platform = ?,
                parser_type = ?,
                config_json = ?,
                detection_note = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                detection.platform,
                detection.parser_type,
                json.dumps(detection.config),
                detection.note,
                row["id"],
            ),
        )
