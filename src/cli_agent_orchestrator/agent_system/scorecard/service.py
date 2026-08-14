"""Evaluation lifecycle under CAO (plan V2 §14.2-14.6).

Integrity rules enforced here:
* an invocation cannot be its own sole evaluator;
* one evaluation per (usage, evaluator) relationship unless superseded;
* immutable rows — corrections supersede, never rewrite;
* score bounds and field sets validated;
* evaluator identity and provider family recorded.
"""

from __future__ import annotations

import json
import sqlite3
import uuid

from .rubric import RUBRIC_VERSION, WEIGHT_VERSION, posterior_score, weighted_score


class EvaluationError(Exception):
    pass


class ScorecardService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def submit_evaluation(
        self,
        usage_id: str,
        evaluator_role: str,
        scores: dict[str, int],
        evaluator_provider_family: str | None = None,
    ) -> str:
        usage = self.conn.execute("SELECT * FROM usage WHERE usage_id=?", (usage_id,)).fetchone()
        if usage is None:
            raise EvaluationError(f"usage not found: {usage_id}")
        # self-evaluation guard: evaluator must differ from the evaluated identity
        if evaluator_provider_family and usage["provider"] and evaluator_provider_family == usage["provider"]:
            raise EvaluationError("evaluator provider family equals evaluated provider family")
        aggregate = weighted_score(scores)  # raises ScoreValidationError on bad input
        existing = self.conn.execute(
            "SELECT evaluation_id FROM evaluations WHERE usage_id=? AND evaluator_role=?"
            " AND superseded_by IS NULL",
            (usage_id, evaluator_role),
        ).fetchone()
        if existing:
            raise EvaluationError(
                f"evaluation already exists for usage {usage_id} by {evaluator_role}; supersede instead"
            )
        evaluation_id = f"eval-{uuid.uuid4().hex[:12]}"
        self.conn.execute(
            "INSERT INTO evaluations (evaluation_id, usage_id, evaluator_role,"
            " evaluator_provider_family, scores_json, aggregate, rubric_version, weights_version)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (
                evaluation_id,
                usage_id,
                evaluator_role,
                evaluator_provider_family,
                json.dumps(scores, sort_keys=True),
                aggregate,
                RUBRIC_VERSION,
                WEIGHT_VERSION,
            ),
        )
        self.conn.commit()
        return evaluation_id

    def supersede(self, old_evaluation_id: str, new_evaluation_id: str) -> None:
        row = self.conn.execute(
            "SELECT superseded_by FROM evaluations WHERE evaluation_id=?", (old_evaluation_id,)
        ).fetchone()
        if row is None:
            raise EvaluationError(f"evaluation not found: {old_evaluation_id}")
        if row["superseded_by"]:
            raise EvaluationError("evaluation already superseded")
        self.conn.execute(
            "UPDATE evaluations SET superseded_by=? WHERE evaluation_id=?",
            (new_evaluation_id, old_evaluation_id),
        )
        self.conn.commit()

    def pending_for_task(self, task_id: str) -> list[str]:
        """Completed usage rows lacking any evaluation (plan V2 gate 6)."""
        rows = self.conn.execute(
            "SELECT u.usage_id FROM usage u LEFT JOIN evaluations e ON e.usage_id = u.usage_id"
            " WHERE u.task_id=? AND u.status='completed' AND e.evaluation_id IS NULL",
            (task_id,),
        ).fetchall()
        return [r["usage_id"] for r in rows]

    def route_statistics(self, provider: str | None = None, model: str | None = None) -> dict:
        """Posterior aggregate for routing advice with sample count (§14.5)."""
        where, params = [], []
        if provider:
            where.append("u.provider = ?")
            params.append(provider)
        if model:
            where.append("(u.resolved_model = ? OR u.requested_model = ?)")
            params.extend([model, model])
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        rows = self.conn.execute(
            f"SELECT e.aggregate FROM evaluations e JOIN usage u ON u.usage_id=e.usage_id"
            f" {clause} AND e.superseded_by IS NULL" if clause else
            "SELECT e.aggregate FROM evaluations e JOIN usage u ON u.usage_id=e.usage_id"
            " WHERE e.superseded_by IS NULL",
            params,
        ).fetchall()
        values = [r["aggregate"] for r in rows]
        return {
            "observations": len(values),
            "posterior": posterior_score(values),
            "raw_mean": (sum(values) / len(values)) if values else None,
        }
