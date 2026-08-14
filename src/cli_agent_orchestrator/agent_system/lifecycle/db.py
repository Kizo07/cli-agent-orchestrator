"""SQLite persistence for the agent-system lifecycle (plan V2 §11).

Canonical owner of task graph, handoffs, usage, and scorecard state is CAO;
this database lives under ``CAO_HOME_DIR/agent_system/``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    project_slug TEXT,
    status TEXT NOT NULL,
    policy_bundle_json TEXT NOT NULL,
    idempotency_key TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    role TEXT NOT NULL,
    provider TEXT,
    provider_family TEXT,
    model_alias TEXT,
    resolved_model TEXT,
    session_id TEXT,
    worktree_path TEXT,
    contract_path TEXT,
    contract_sha256 TEXT,
    artifact_path TEXT,
    artifact_sha256 TEXT,
    verification_status TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS handoffs (
    handoff_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    kind TEXT NOT NULL,
    sender_role TEXT,
    sender_session TEXT,
    recipient_role TEXT,
    recipient_session TEXT,
    recipient_provider_family TEXT,
    contract_sha256 TEXT,
    artifact_sha256 TEXT,
    status TEXT NOT NULL,
    findings_json TEXT,
    disposition TEXT,
    idempotency_key TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    accepted_at TEXT,
    completed_at TEXT,
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS usage (
    usage_id TEXT PRIMARY KEY,
    task_id TEXT REFERENCES tasks(task_id),
    run_id TEXT REFERENCES runs(run_id),
    provider TEXT,
    requested_model TEXT,
    resolved_model TEXT,
    role TEXT,
    pid INTEGER,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    finished_at TEXT,
    legacy_json TEXT
);

CREATE TABLE IF NOT EXISTS evaluations (
    evaluation_id TEXT PRIMARY KEY,
    usage_id TEXT NOT NULL REFERENCES usage(usage_id),
    evaluator_role TEXT NOT NULL,
    evaluator_provider_family TEXT,
    scores_json TEXT NOT NULL,
    aggregate REAL NOT NULL,
    rubric_version TEXT NOT NULL,
    weights_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    superseded_by TEXT,
    legacy_json TEXT
);

CREATE TABLE IF NOT EXISTS quirks (
    quirk_id TEXT PRIMARY KEY,
    tool TEXT,
    model TEXT,
    symptom TEXT,
    workaround TEXT,
    status TEXT,
    legacy_json TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    task_id TEXT,
    kind TEXT NOT NULL,
    payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_tasks_run ON tasks(run_id);
CREATE INDEX IF NOT EXISTS idx_handoffs_task ON handoffs(task_id);
CREATE INDEX IF NOT EXISTS idx_usage_task ON usage(task_id);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    if exists is None:
        conn.executescript(SCHEMA)
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        conn.commit()
    else:
        row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
        if row["version"] != SCHEMA_VERSION:
            raise RuntimeError(f"schema version mismatch: db={row['version']} code={SCHEMA_VERSION}")
    return conn
