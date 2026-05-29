"""Small key/value app state helpers."""

from __future__ import annotations

import json
from typing import Any

from job_radar.db.client import execute, init_db


def get_state(key: str, default: Any = None) -> Any:
    init_db()
    rows = execute("SELECT value FROM app_state WHERE key = ?", (key,))
    if not rows:
        return default
    try:
        return json.loads(rows[0]["value"])
    except json.JSONDecodeError:
        return default


def set_state(key: str, value: Any) -> None:
    init_db()
    execute(
        """
        INSERT INTO app_state (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (key, json.dumps(value)),
    )
