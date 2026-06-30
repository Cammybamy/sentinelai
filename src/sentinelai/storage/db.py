from __future__ import annotations

import json
import sqlite3
from pathlib import Path

_DB_PATH = Path.home() / ".sentinelai" / "audit.db"

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp        TEXT    NOT NULL,
    command          TEXT    NOT NULL,
    risk_level       TEXT    NOT NULL,
    verdict_source   TEXT    NOT NULL,
    explanation      TEXT    NOT NULL,
    dangerous_elements TEXT  NOT NULL DEFAULT '[]',
    rule_ids         TEXT    NOT NULL DEFAULT '[]',
    llm_confidence   REAL,
    user_decision    TEXT    NOT NULL,
    shell            TEXT    NOT NULL DEFAULT 'unknown',
    source           TEXT    NOT NULL DEFAULT 'clipboard'
);
"""


def get_connection() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(_CREATE_SQL)
    return conn
