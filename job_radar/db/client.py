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
    conn.execute("PRAGMA journal_mode = WAL")
    # Checkpoint on every connection close so the main .db file is always current
    # for file-level backups.  The runner additionally calls PRAGMA wal_checkpoint
    # (TRUNCATE) after each full scan as an explicit sync point.
    conn.execute("PRAGMA wal_autocheckpoint = 1")
    return conn


def init_db(path: Path | None = None) -> Path:
    ensure_data_dir()
    db_path = path or get_settings().db_path
    schema = files("job_radar.db").joinpath("schema.sql").read_text()
    with connect(db_path) as conn:
        # Existing databases may need additive columns before schema indexes are
        # created, but fresh databases need the base tables first.
        if _table_exists(conn, "sources"):
            _ensure_columns(conn)
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
    """Apply additive column migrations for existing local databases."""
    if not _table_exists(conn, "sources"):
        return

    source_cols = {r["name"] for r in conn.execute("PRAGMA table_info(sources)").fetchall()}
    if "config_json" not in source_cols:
        conn.execute("ALTER TABLE sources ADD COLUMN config_json TEXT NOT NULL DEFAULT '{}'")
    if "notes" not in source_cols:
        conn.execute("ALTER TABLE sources ADD COLUMN notes TEXT")

    if not _table_exists(conn, "jobs"):
        return
    job_cols = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    if "description_hash" not in job_cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN description_hash TEXT")
    if "last_changed_at" not in job_cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN last_changed_at TEXT")
    if "times_seen" not in job_cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN times_seen INTEGER NOT NULL DEFAULT 1")
    if "missed_scans" not in job_cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN missed_scans INTEGER NOT NULL DEFAULT 0")
    if "lifecycle_status" not in job_cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN lifecycle_status TEXT NOT NULL DEFAULT 'active'")

    job_extra_cols = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    if "notes" not in job_extra_cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN notes TEXT")

    if not _table_exists(conn, "source_runs"):
        return
    sr_cols = {r["name"] for r in conn.execute("PRAGMA table_info(source_runs)").fetchall()}
    if "jobs_changed" not in sr_cols:
        conn.execute("ALTER TABLE source_runs ADD COLUMN jobs_changed INTEGER NOT NULL DEFAULT 0")
    if "jobs_unchanged" not in sr_cols:
        conn.execute("ALTER TABLE source_runs ADD COLUMN jobs_unchanged INTEGER NOT NULL DEFAULT 0")
    if "fetch_ms" not in sr_cols:
        conn.execute("ALTER TABLE source_runs ADD COLUMN fetch_ms INTEGER")
    if "upsert_ms" not in sr_cols:
        conn.execute("ALTER TABLE source_runs ADD COLUMN upsert_ms INTEGER")
    if "total_ms" not in sr_cols:
        conn.execute("ALTER TABLE source_runs ADD COLUMN total_ms INTEGER")

    if not _table_exists(conn, "source_health"):
        return
    sh_cols = {r["name"] for r in conn.execute("PRAGMA table_info(source_health)").fetchall()}
    if "confidence_label" not in sh_cols:
        conn.execute("ALTER TABLE source_health ADD COLUMN confidence_label TEXT NOT NULL DEFAULT 'unknown'")
    if "confidence_score" not in sh_cols:
        conn.execute("ALTER TABLE source_health ADD COLUMN confidence_score INTEGER NOT NULL DEFAULT 0")
    if "confidence_note" not in sh_cols:
        conn.execute("ALTER TABLE source_health ADD COLUMN confidence_note TEXT")


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


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
