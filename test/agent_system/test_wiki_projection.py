"""Phase 8 gate tests: sanitized export schema + journal queue semantics."""

from __future__ import annotations

import json
import sqlite3
import stat
from pathlib import Path

import pytest

from cli_agent_orchestrator.agent_system.lifecycle import db as _db
from cli_agent_orchestrator.agent_system.wiki.export import (
    EXPORT_SCHEMA_VERSION,
    export_scorecards,
)
from cli_agent_orchestrator.agent_system.wiki.journal import (
    JournalError,
    WikiJournal,
    sanitize_event,
)


@pytest.fixture()
def conn(tmp_path):
    c = _db.connect(tmp_path / "lifecycle.db")
    c.execute(
        "INSERT INTO usage (usage_id, provider, requested_model, resolved_model, role, status)"
        " VALUES ('u1','opencode','glm-5.2','glm-5.2','implementer','completed')"
    )
    c.execute(
        "INSERT INTO evaluations (evaluation_id, usage_id, evaluator_role, scores_json, aggregate,"
        " rubric_version, weights_version) VALUES ('e1','u1','reviewer',"
        " '{\"correctness\":4}', 4.0, 'score-v1', 'score-v1')"
    )
    c.commit()
    yield c
    c.close()


def test_export_schema_and_whitelist(conn):
    payload = export_scorecards(conn)
    assert payload["schema_version"] == EXPORT_SCHEMA_VERSION
    assert payload["count"] == 1
    rec = payload["records"][0]
    assert rec["evaluation_id"] == "e1"
    assert rec["provider"] == "opencode"
    assert rec["resolved_model"] == "glm-5.2"
    # whitelist-only: no raw content classes may appear
    for forbidden in ("prompt", "response", "transcript", "notes", "environment", "legacy_json"):
        assert forbidden not in rec
    assert payload["cursor"] >= 1
    assert len(payload["export_hash"]) == 64


def test_export_incremental_cursor(conn):
    first = export_scorecards(conn)
    second = export_scorecards(conn, since_rowid=first["cursor"])
    assert second["count"] == 0  # nothing new past the cursor


def test_sanitize_event_guards():
    assert sanitize_event("  run   completed  ") == "run completed"
    with pytest.raises(JournalError):
        sanitize_event("key stored at /home/fire/.config")
    with pytest.raises(JournalError):
        sanitize_event("msg with · reserved delimiter")
    with pytest.raises(JournalError):
        sanitize_event("header Authorization: Bearer abcdef")
    # overlong input is bounded by truncation, never blocking CAO completion
    assert len(sanitize_event("x" * 500)) <= 120


def test_journal_idempotent_enqueue_and_delivery(tmp_path):
    # fake wiki CLI: records argv to a file, never through a shell
    calls = tmp_path / "calls.jsonl"
    fake = tmp_path / "fake-wiki"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"open({str(calls)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    j = WikiJournal(conn, fake, "demo-project")
    assert j.enqueue("k1", "run completed") is True
    assert j.enqueue("k1", "run completed") is False  # duplicate key no-op
    assert j.pending() == 1
    report = j.flush()
    assert report == {"delivered": 1, "failed": 0}
    assert j.pending() == 0
    argv = json.loads(calls.read_text().splitlines()[0])
    assert argv == ["log", "demo-project", "run completed"]  # argv list, not a shell string


def test_journal_failed_delivery_retries_then_marks_failed(tmp_path):
    failing = tmp_path / "fail-wiki"
    failing.write_text("#!/bin/sh\nexit 1\n")
    failing.chmod(failing.stat().st_mode | stat.S_IEXEC)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    j = WikiJournal(conn, failing, "demo")
    j.enqueue("k1", "event one")
    for _ in range(3):
        j.flush()
    row = conn.execute("SELECT status, attempts FROM projection_queue WHERE event_key='k1'").fetchone()
    assert row["status"] == "failed"
    assert row["attempts"] >= 3
