"""Lossless migration of AgentSystem JSONL history into the CAO state tree.

Plan V2 Phase 5: migrate a COPY of historical data; preserve IDs, foreign
keys, timestamps, rubric versions, and exact records. The legacy store stays
read-only and intact; reconciliation proves losslessness by ID and count.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from .rubric import RUBRIC_VERSION, WEIGHT_VERSION, ScoreValidationError, weighted_score

USAGE_STATUS_MAP = {
    "success": "completed",
    "cli_failed": "failed",
    "failed": "failed",
    "cancelled": "cancelled",
    "timeout": "timeout",
}


@dataclass
class MigrationReport:
    usage_rows: int = 0
    evaluation_rows: int = 0
    quirk_rows: int = 0
    usage_stubbed_for_fk: list[str] = field(default_factory=list)
    legacy_preserved_evaluations: list[str] = field(default_factory=list)
    aggregate_mismatches: list[str] = field(default_factory=list)
    foreign_key_ok: bool = False

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2, sort_keys=True)


def _iter_jsonl(path: Path):
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            yield json.loads(line)


def migrate_legacy_stores(conn: sqlite3.Connection, agent_system_root: str | Path) -> MigrationReport:
    root = Path(agent_system_root)
    report = MigrationReport()

    # ---- usage ---------------------------------------------------------
    usage_ids: set[str] = set()
    for rec in _iter_jsonl(root / "usage" / "usage.jsonl"):
        uid = rec["usage_id"]
        usage_ids.add(uid)
        conn.execute(
            "INSERT INTO usage (usage_id, provider, requested_model, resolved_model, role,"
            " status, started_at, finished_at, legacy_json)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (
                uid,
                rec.get("tool"),
                rec.get("model"),
                rec.get("model"),
                rec.get("role"),
                USAGE_STATUS_MAP.get(rec.get("status"), "failed"),
                rec.get("timestamp_start"),
                rec.get("timestamp_end"),
                json.dumps(rec, sort_keys=True),
            ),
        )
        report.usage_rows += 1

    # ---- evaluations ---------------------------------------------------
    for rec in _iter_jsonl(root / "scorecards" / "evaluations.jsonl"):
        eid = rec["evaluation_id"]
        uid = rec["usage_id"]
        if uid not in usage_ids:
            # preserve FK integrity without losing the historical evaluation
            conn.execute(
                "INSERT INTO usage (usage_id, provider, status, legacy_json) VALUES (?,?,?,?)",
                (uid, None, "failed", json.dumps({"stub": True, "reason": "orphan evaluation FK"})),
            )
            usage_ids.add(uid)
            report.usage_stubbed_for_fk.append(uid)
        try:
            aggregate = weighted_score(rec["scores"])
            rubric = RUBRIC_VERSION
            if abs(aggregate - float(rec.get("aggregate_score", aggregate))) > 1e-4:
                report.aggregate_mismatches.append(eid)
        except ScoreValidationError:
            # historical row predates current bounds — preserve verbatim
            aggregate = float(rec.get("aggregate_score", 0.0))
            rubric = "legacy-preserved"
            report.legacy_preserved_evaluations.append(eid)
        conn.execute(
            "INSERT INTO evaluations (evaluation_id, usage_id, evaluator_role,"
            " evaluator_provider_family, scores_json, aggregate, rubric_version,"
            " weights_version, legacy_json)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (
                eid,
                uid,
                rec.get("role", "legacy"),
                None,
                json.dumps(rec.get("scores", {}), sort_keys=True),
                aggregate,
                rubric,
                WEIGHT_VERSION,
                json.dumps(rec, sort_keys=True),
            ),
        )
        report.evaluation_rows += 1

    # ---- quirks --------------------------------------------------------
    for rec in _iter_jsonl(root / "quirks" / "quirks.jsonl"):
        conn.execute(
            "INSERT INTO quirks (quirk_id, tool, model, symptom, workaround, status, legacy_json)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                rec["quirk_id"],
                rec.get("tool"),
                rec.get("model"),
                rec.get("symptom"),
                rec.get("workaround"),
                rec.get("status"),
                json.dumps(rec, sort_keys=True),
            ),
        )
        report.quirk_rows += 1

    conn.commit()
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    report.foreign_key_ok = not violations
    return report
