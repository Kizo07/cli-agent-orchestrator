"""Sanitized scorecard export for the wiki (plan V2 §15.2).

Whitelist-only field construction: forbidden content classes cannot cross the
boundary because they are never read from the source rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

EXPORT_SCHEMA_VERSION = "wiki-scorecard-export/1"

ALLOWED_FIELDS = (
    "evaluation_id",
    "usage_id",
    "project_slug",
    "role",
    "provider",
    "resolved_model",
    "requested_model",
    "evaluator_role",
    "evaluator_provider_family",
    "outcome_status",
    "scores",
    "aggregate",
    "rubric_version",
    "weights_version",
    "created_at",
    "status",
)


def export_scorecards(conn: sqlite3.Connection, since_rowid: int = 0) -> dict:
    rows = conn.execute(
        "SELECT e.evaluation_id, e.usage_id, e.evaluator_role, e.evaluator_provider_family,"
        " e.scores_json, e.aggregate, e.rubric_version, e.weights_version, e.created_at,"
        " e.superseded_by, u.provider, u.requested_model, u.resolved_model, u.role, u.status,"
        " e.rowid AS rid"
        " FROM evaluations e JOIN usage u ON u.usage_id = e.usage_id"
        " WHERE e.rowid > ? ORDER BY e.rowid",
        (since_rowid,),
    ).fetchall()
    records = []
    cursor = since_rowid
    for r in rows:
        records.append(
            {
                "evaluation_id": r["evaluation_id"],
                "usage_id": r["usage_id"],
                "project_slug": None,  # historical rows predate CAO projects
                "role": r["role"],
                "provider": r["provider"],
                "resolved_model": r["resolved_model"],
                "requested_model": r["requested_model"],
                "evaluator_role": r["evaluator_role"],
                "evaluator_provider_family": r["evaluator_provider_family"],
                "outcome_status": r["status"],
                "scores": json.loads(r["scores_json"]),
                "aggregate": r["aggregate"],
                "rubric_version": r["rubric_version"],
                "weights_version": r["weights_version"],
                "created_at": r["created_at"],
                "status": "superseded" if r["superseded_by"] else "active",
            }
        )
        cursor = max(cursor, r["rid"])
    payload = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "cursor": cursor,
        "count": len(records),
        "records": records,
    }
    canonical = json.dumps(records, sort_keys=True)
    payload["export_hash"] = hashlib.sha256(canonical.encode()).hexdigest()
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description="Export sanitized CAO scorecards for the wiki")
    ap.add_argument("--db", required=True, help="path to agent-system lifecycle.db")
    ap.add_argument("--since-rowid", type=int, default=0)
    ap.add_argument("--out", required=True, help="output JSON path")
    args = ap.parse_args()
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    payload = export_scorecards(conn, since_rowid=args.since_rowid)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(f"exported {payload['count']} records cursor={payload['cursor']} hash={payload['export_hash'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
