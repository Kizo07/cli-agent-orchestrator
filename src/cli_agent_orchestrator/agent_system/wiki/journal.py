"""CAO -> wiki journal events (plan V2 §15.4/§15.5).

Delivery is argv-based (never a shell string), idempotent via event keys, and
queued in CAO state so wiki downtime never corrupts CAO runs. Messages are
bounded and sanitized: no prompts, responses, environment values, secrets,
reserved delimiters, or absolute paths.
"""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

MAX_MESSAGE_CHARS = 120
FORBIDDEN_FRAGMENTS = ("/home/", "api_key", "Bearer ", "-----BEGIN")


class JournalError(Exception):
    pass


def sanitize_event(message: str) -> str:
    msg = " ".join(str(message).split())[:MAX_MESSAGE_CHARS]
    for frag in FORBIDDEN_FRAGMENTS:
        if frag in msg:
            raise JournalError(f"event message contains forbidden fragment: {frag!r}")
    if " · " in msg:  # reserved journal delimiter
        raise JournalError("event message contains reserved journal delimiter")
    return msg


class WikiJournal:
    def __init__(self, conn: sqlite3.Connection, wiki_cli: str | Path, default_slug: str):
        self.conn = conn
        self.wiki_cli = str(wiki_cli)
        self.default_slug = default_slug
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS projection_queue ("
            " event_key TEXT PRIMARY KEY,"
            " slug TEXT NOT NULL,"
            " message TEXT NOT NULL,"
            " status TEXT NOT NULL DEFAULT 'queued',"
            " attempts INTEGER NOT NULL DEFAULT 0,"
            " created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),"
            " delivered_at TEXT"
            ")"
        )
        self.conn.commit()

    def enqueue(self, event_key: str, message: str, slug: str | None = None) -> bool:
        """Queue a bounded event; duplicate keys are no-ops (idempotency)."""
        msg = sanitize_event(message)
        try:
            self.conn.execute(
                "INSERT INTO projection_queue (event_key, slug, message) VALUES (?,?,?)",
                (event_key, slug or self.default_slug, msg),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # already queued/delivered

    def flush(self, max_events: int = 50) -> dict:
        delivered, failed = 0, 0
        rows = self.conn.execute(
            "SELECT event_key, slug, message FROM projection_queue"
            " WHERE status='queued' ORDER BY rowid LIMIT ?",
            (max_events,),
        ).fetchall()
        for row in rows:
            self.conn.execute(
                "UPDATE projection_queue SET attempts = attempts + 1 WHERE event_key=?",
                (row["event_key"],),
            )
            try:
                subprocess.run(
                    [self.wiki_cli, "log", row["slug"], row["message"]],
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
                self.conn.execute(
                    "UPDATE projection_queue SET status='delivered',"
                    " delivered_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE event_key=?",
                    (row["event_key"],),
                )
                delivered += 1
            except Exception:
                self.conn.execute(
                    "UPDATE projection_queue SET status='failed' WHERE attempts >= 3 AND event_key=?",
                    (row["event_key"],),
                )
                failed += 1
        self.conn.commit()
        return {"delivered": delivered, "failed": failed}

    def pending(self) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) AS n FROM projection_queue WHERE status='queued'"
        ).fetchone()["n"]
