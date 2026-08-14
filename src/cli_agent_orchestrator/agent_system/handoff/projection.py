"""Legacy Markdown projection for CAO handoffs (plan V2 §13.4).

Generated from the canonical CAO record; marked non-authoritative. Contains
identifiers, hashes, roles, and bounded status only — never prompts,
responses, reasoning, transcripts, credentials, environment values, or
unbounded file content (plan V2 §13.1).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

PROJECTION_MARKER = "<!-- NON-AUTHORITATIVE PROJECTION: canonical record lives in CAO lifecycle DB -->"

FORBIDDEN_SUBSTRINGS = ("BEGIN RSA", "BEGIN PRIVATE", "api_key", "Authorization: Bearer")


def _findings_count(findings_json: str | None) -> int | None:
    if not findings_json:
        return None
    try:
        parsed = json.loads(findings_json)
        return len(parsed) if isinstance(parsed, list) else None
    except Exception:
        return None


def render_projection(row: sqlite3.Row) -> str:
    lines = [
        PROJECTION_MARKER,
        f"# Handoff {row['handoff_id']}",
        "",
        f"- kind: {row['kind']}",
        f"- run: {row['run_id']}",
        f"- task: {row['task_id']}",
        f"- sender_role: {row['sender_role'] or '-'}",
        f"- recipient_role: {row['recipient_role'] or '-'}",
        f"- recipient_session: {row['recipient_session'] or '-'}",
        f"- contract_sha256: {row['contract_sha256'] or '-'}",
        f"- artifact_sha256: {row['artifact_sha256'] or '-'}",
        f"- status: {row['status']}",
        f"- disposition: {row['disposition'] or '-'}",
        f"- next_action: {row['next_action'] or '-'}",
        f"- schema_version: {row['schema_version']}",
        f"- created_at: {row['created_at']}",
        f"- accepted_at: {row['accepted_at'] or '-'}",
        f"- completed_at: {row['completed_at'] or '-'}",
    ]
    count = _findings_count(row["findings_json"])
    if count is not None:
        lines.append(f"- findings_count: {count}")
    lines.append("")
    text = "\n".join(lines)
    for bad in FORBIDDEN_SUBSTRINGS:
        if bad in text:
            raise ValueError(f"projection would contain forbidden content: {bad}")
    return text


def write_projection(conn: sqlite3.Connection, handoff_id: str, legacy_dir: str | Path) -> Path:
    row = conn.execute("SELECT * FROM handoffs WHERE handoff_id=?", (handoff_id,)).fetchone()
    if row is None:
        raise KeyError(f"handoff not found: {handoff_id}")
    dest = Path(legacy_dir)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{handoff_id}.md"
    path.write_text(render_projection(row))
    return path
