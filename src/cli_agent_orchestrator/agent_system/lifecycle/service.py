"""LifecycleService: CAO's canonical run/task/handoff state machine.

Only CAO performs transitions (plan V2 §13.2). Provider sessions propose
completion or blockage; they never mutate state directly. Every transition
is journaled to the ``events`` table for crash replay.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from . import db as _db
from . import states as S
from . import LifecycleError
from ..policy.bundle import PolicyBundle

CANONICAL_ROLES = {
    "supervisor",
    "architect",
    "implementer",
    "reviewer",
    "verifier",
    "specialist",
    "memory-curator",
    "scorecard-evaluator",
}

USAGE_TERMINAL = {"completed", "failed", "cancelled", "timeout"}


class GateFailure(LifecycleError):
    pass


class StaleArtifact(LifecycleError):
    pass


class ReviewIndependenceViolation(LifecycleError):
    pass


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def hash_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class TaskSpec:
    role: str
    contract_path: str | None = None


class LifecycleService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    @classmethod
    def open(cls, db_path: str | Path) -> "LifecycleService":
        return cls(_db.connect(db_path))

    # ------------------------------------------------------------------ runs

    def create_run(
        self,
        goal: str,
        policy_bundle: PolicyBundle,
        project_slug: str | None = None,
        idempotency_key: str | None = None,
    ) -> str:
        if idempotency_key:
            row = self.conn.execute(
                "SELECT run_id FROM runs WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            if row:
                return row["run_id"]
        run_id = new_id("run")
        self.conn.execute(
            "INSERT INTO runs (run_id, goal, project_slug, status, policy_bundle_json, idempotency_key)"
            " VALUES (?,?,?,?,?,?)",
            (run_id, goal, project_slug, S.RUN_CREATED, policy_bundle.to_json(), idempotency_key),
        )
        self._event(run_id, None, "run_created", {"goal_len": len(goal)})
        self.conn.commit()
        return run_id

    def transition_run(self, run_id: str, target: str) -> None:
        row = self._require("runs", run_id)
        S.check_transition(row["status"], target, S.RUN_TRANSITIONS, "run")
        self.conn.execute("UPDATE runs SET status=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE run_id=?", (target, run_id))
        self._event(run_id, None, f"run_{target}", None)
        self.conn.commit()

    # ----------------------------------------------------------------- tasks

    def plan_tasks(self, run_id: str, specs: list[TaskSpec]) -> list[str]:
        run = self._require("runs", run_id)
        if run["status"] != S.RUN_CREATED:
            raise LifecycleError(f"run {run_id} is not in created state (is {run['status']})")
        task_ids = []
        for spec in specs:
            if spec.role not in CANONICAL_ROLES:
                raise LifecycleError(f"unknown role: {spec.role}")
            task_id = new_id("task")
            contract_sha = hash_file(spec.contract_path) if spec.contract_path else None
            self.conn.execute(
                "INSERT INTO tasks (task_id, run_id, role, status, contract_path, contract_sha256)"
                " VALUES (?,?,?,?,?,?)",
                (task_id, run_id, spec.role, S.TASK_PENDING, spec.contract_path, contract_sha),
            )
            task_ids.append(task_id)
        self.transition_run(run_id, S.RUN_PLANNED)
        return task_ids

    def assign_task(
        self,
        task_id: str,
        provider: str,
        provider_family: str,
        session_id: str,
        model_alias: str | None = None,
        worktree_path: str | None = None,
    ) -> None:
        task = self._require("tasks", task_id)
        S.check_transition(task["status"], S.TASK_ASSIGNED, S.TASK_TRANSITIONS, "task")
        self.conn.execute(
            "UPDATE tasks SET status=?, provider=?, provider_family=?, session_id=?,"
            " model_alias=?, worktree_path=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE task_id=?",
            (S.TASK_ASSIGNED, provider, provider_family, session_id, model_alias, worktree_path, task_id),
        )
        self._event(task["run_id"], task_id, "task_assigned", {"provider": provider})
        self.transition_run_if(task["run_id"], S.RUN_RUNNING)
        self.conn.commit()

    def transition_task(self, task_id: str, target: str) -> None:
        task = self._require("tasks", task_id)
        S.check_transition(task["status"], target, S.TASK_TRANSITIONS, "task")
        self.conn.execute(
            "UPDATE tasks SET status=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE task_id=?",
            (target, task_id),
        )
        self._event(task["run_id"], task_id, f"task_{target}", None)
        self.conn.commit()

    def submit_artifact(self, task_id: str, artifact_path: str | Path) -> str:
        """Freeze the artifact hash at submission (plan V2 §16 step 9/11)."""
        task = self._require("tasks", task_id)
        if task["status"] not in (S.TASK_IMPLEMENTING, S.TASK_REWORK):
            raise LifecycleError(f"cannot submit artifact from state {task['status']}")
        artifact_sha = hash_file(artifact_path)
        target = S.TASK_SUBMITTED
        S.check_transition(task["status"], target, S.TASK_TRANSITIONS, "task")
        self.conn.execute(
            "UPDATE tasks SET status=?, artifact_path=?, artifact_sha256=?,"
            " updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE task_id=?",
            (target, str(artifact_path), artifact_sha, task_id),
        )
        self._event(task["run_id"], task_id, "artifact_submitted", {"sha256": artifact_sha})
        self.conn.commit()
        return artifact_sha

    def record_verification(self, task_id: str, passed: bool) -> None:
        task = self._require("tasks", task_id)
        S.check_transition(task["status"], S.TASK_VERIFYING, S.TASK_TRANSITIONS, "task")
        self.conn.execute(
            "UPDATE tasks SET status=?, verification_status=?,"
            " updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE task_id=?",
            (S.TASK_VERIFYING, "passed" if passed else "failed", task_id),
        )
        self._event(task["run_id"], task_id, "verification", {"passed": passed})
        self.conn.commit()

    # -------------------------------------------------------------- handoffs

    def request_review(
        self,
        task_id: str,
        reviewer_session: str,
        reviewer_provider_family: str,
        require_different_family: bool = True,
        idempotency_key: str | None = None,
        expires_in_seconds: int | None = None,
    ) -> str:
        """Create an independent review handoff (plan V2 §7.4, §13.3).

        Repeated delivery with the same idempotency key returns the existing
        handoff instead of duplicating it (plan V2 §13.4 gate).
        """
        if idempotency_key:
            existing = self.conn.execute(
                "SELECT handoff_id FROM handoffs WHERE idempotency_key=?", (idempotency_key,)
            ).fetchone()
            if existing:
                return existing["handoff_id"]
        task = self._require("tasks", task_id)
        if task["status"] != S.TASK_VERIFYING or task["verification_status"] != "passed":
            raise GateFailure("verification must pass before review")
        if not task["artifact_sha256"]:
            raise GateFailure("no frozen artifact to review")
        # independence from recorded identities, not prompt text
        if reviewer_session == task["session_id"]:
            raise ReviewIndependenceViolation("reviewer session equals implementer session")
        if require_different_family and reviewer_provider_family == task["provider_family"]:
            raise ReviewIndependenceViolation(
                f"reviewer provider family must differ (both {reviewer_provider_family})"
            )
        handoff_id = new_id("ho")
        expires_at = None
        if expires_in_seconds is not None:
            expires_at = self.conn.execute(
                "SELECT strftime('%Y-%m-%dT%H:%M:%fZ','now',?) AS t",
                (f"{int(expires_in_seconds):+d} seconds",),
            ).fetchone()["t"]
        self.conn.execute(
            "INSERT INTO handoffs (handoff_id, run_id, task_id, kind, sender_role, sender_session,"
            " recipient_role, recipient_session, recipient_provider_family,"
            " contract_sha256, artifact_sha256, status, idempotency_key, expires_at, policy_version)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                handoff_id,
                task["run_id"],
                task_id,
                "review",
                task["role"],
                task["session_id"],
                "reviewer",
                reviewer_session,
                reviewer_provider_family,
                task["contract_sha256"],
                task["artifact_sha256"],
                S.HO_DRAFT,
                idempotency_key,
                expires_at,
                self._run_policy_version(task["run_id"]),
            ),
        )
        self._transition_handoff(handoff_id, S.HO_VALIDATED)
        self._transition_handoff(handoff_id, S.HO_OFFERED)
        self.conn.execute(
            "UPDATE tasks SET status=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE task_id=?",
            (S.TASK_IN_REVIEW, task_id),
        )
        self._event(task["run_id"], task_id, "review_offered", {"handoff": handoff_id})
        self.conn.commit()
        return handoff_id

    def _run_policy_version(self, run_id: str) -> str | None:
        run = self.conn.execute("SELECT policy_bundle_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if not run:
            return None
        try:
            return json.loads(run["policy_bundle_json"]).get("bundle_hash")
        except Exception:
            return None

    def accept_handoff(self, handoff_id: str) -> None:
        self._transition_handoff(handoff_id, S.HO_ACCEPTED)
        self.conn.execute(
            "UPDATE handoffs SET accepted_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE handoff_id=?",
            (handoff_id,),
        )
        self.conn.commit()

    def complete_review(self, handoff_id: str, approved: bool, findings_json: str | None = None) -> None:
        """Close a review handoff; enforce exact-artifact-hash binding."""
        ho = self._require("handoffs", handoff_id)
        if ho["status"] != S.HO_ACCEPTED:
            raise LifecycleError(f"handoff {handoff_id} not accepted (is {ho['status']})")
        task = self._require("tasks", ho["task_id"])
        # stale-diff guard: the reviewed hash must still be the frozen hash
        if ho["artifact_sha256"] != task["artifact_sha256"]:
            self._transition_handoff(handoff_id, S.HO_CANCELLED)
            raise StaleArtifact(
                f"artifact changed since review handoff was created "
                f"(reviewed {ho['artifact_sha256'][:12]} != current {task['artifact_sha256'][:12]})"
            )
        if approved:
            self.conn.execute(
                "UPDATE handoffs SET status=?, disposition='approved', findings_json=?,"
                " completed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE handoff_id=?",
                (S.HO_COMPLETED, findings_json, handoff_id),
            )
            self.transition_task(ho["task_id"], S.TASK_APPROVED)
            self._complete_task_if_gates_pass(ho["task_id"])
        else:
            self.conn.execute(
                "UPDATE handoffs SET status=?, disposition='rework', findings_json=?,"
                " completed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE handoff_id=?",
                (S.HO_RETURNED, findings_json, handoff_id),
            )
            self.transition_task(ho["task_id"], S.TASK_REWORK)
            # CAO creates the rework handoff back to the implementer (§13.3 step 6)
            rework_id = new_id("ho")
            self.conn.execute(
                "INSERT INTO handoffs (handoff_id, run_id, task_id, kind, sender_role,"
                " recipient_role, recipient_session, artifact_sha256, status, next_action,"
                " schema_version, policy_version)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rework_id,
                    ho["run_id"],
                    ho["task_id"],
                    "rework",
                    "reviewer",
                    task["role"],
                    task["session_id"],
                    task["artifact_sha256"],
                    S.HO_OFFERED,
                    "resubmit artifact addressing findings",
                    "handoff/1",
                    self._run_policy_version(ho["run_id"]),
                ),
            )
            self._event(task["run_id"], task["task_id"], "rework_offered", {"handoff": rework_id})
        self._event(task["run_id"], task["task_id"], "review_closed", {"approved": approved})
        self.conn.commit()

    # ----------------------------------------------------------------- gates

    def _complete_task_if_gates_pass(self, task_id: str) -> None:
        """Completion gates (plan V2 §6.3) minus wiki projection (queued later)."""
        task = self._require("tasks", task_id)
        if not task["artifact_path"] or not task["artifact_sha256"]:
            raise GateFailure("gate 1: implementation artifact missing")
        if task["verification_status"] != "passed":
            raise GateFailure("gate 2: deterministic verification not passed")
        review = self.conn.execute(
            "SELECT * FROM handoffs WHERE task_id=? AND kind='review' AND status=? ORDER BY rowid",
            (task_id, S.HO_COMPLETED),
        ).fetchone()
        if review is None:
            raise GateFailure("gate 3: no completed independent review")
        if review["artifact_sha256"] != task["artifact_sha256"]:
            raise GateFailure("gate 7: reviewed artifact hash differs from current artifact")
        open_usage = self.conn.execute(
            "SELECT COUNT(*) AS n FROM usage WHERE task_id=? AND status NOT IN ({})".format(
                ",".join("?" for _ in USAGE_TERMINAL)
            ),
            (task_id, *USAGE_TERMINAL),
        ).fetchone()["n"]
        if open_usage:
            raise GateFailure("gate 5: usage records not terminal")
        pending_eval = self.conn.execute(
            "SELECT COUNT(*) AS n FROM usage u LEFT JOIN evaluations e ON e.usage_id=u.usage_id"
            " WHERE u.task_id=? AND e.evaluation_id IS NULL AND u.status='completed'",
            (task_id,),
        ).fetchone()["n"]
        # gate 6 is enforced by callers that require scorecards (Phase 5 wires the policy flag)
        self.transition_task(task_id, S.TASK_DONE)

    # ----------------------------------------------------------------- usage

    def begin_usage(self, run_id: str, task_id: str | None, provider: str, requested_model: str, role: str) -> str:
        """Usage begins BEFORE provider process launch (plan V2 §14.4)."""
        usage_id = new_id("usage")
        self.conn.execute(
            "INSERT INTO usage (usage_id, task_id, run_id, provider, requested_model, role, status)"
            " VALUES (?,?,?,?,?,?,?)",
            (usage_id, task_id, run_id, provider, requested_model, role, "running"),
        )
        self._event(run_id, task_id, "usage_began", {"usage_id": usage_id})
        self.conn.commit()
        return usage_id

    def attach_usage(self, usage_id: str, pid: int | None = None, resolved_model: str | None = None) -> None:
        self.conn.execute(
            "UPDATE usage SET pid=COALESCE(?, pid), resolved_model=COALESCE(?, resolved_model) WHERE usage_id=?",
            (pid, resolved_model, usage_id),
        )
        self.conn.commit()

    def finish_usage(self, usage_id: str, status: str) -> None:
        if status not in USAGE_TERMINAL:
            raise LifecycleError(f"usage terminal status invalid: {status}")
        self.conn.execute(
            "UPDATE usage SET status=?, finished_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE usage_id=?",
            (status, usage_id),
        )
        row = self.conn.execute("SELECT run_id, task_id FROM usage WHERE usage_id=?", (usage_id,)).fetchone()
        self._event(row["run_id"] if row else None, row["task_id"] if row else None, "usage_finished", {"status": status})
        self.conn.commit()

    # ------------------------------------------------------------ recovery

    def reconcile(self) -> dict:
        """Crash reconciliation: never infer completion from process exit.

        Marks usage left 'running' as failed (provider process vanished) and
        surfaces tasks stuck in active states for operator attention.
        """
        stuck_usage = self.conn.execute("SELECT usage_id FROM usage WHERE status='running'").fetchall()
        for row in stuck_usage:
            self.finish_usage(row["usage_id"], "failed")
        active_task_states = (S.TASK_ASSIGNED, S.TASK_IMPLEMENTING, S.TASK_SUBMITTED, S.TASK_VERIFYING)
        stuck_tasks = self.conn.execute(
            "SELECT task_id FROM tasks WHERE status IN ({})".format(",".join("?" * len(active_task_states))),
            active_task_states,
        ).fetchall()
        report = {
            "usage_marked_failed": len(stuck_usage),
            "tasks_needing_attention": [r["task_id"] for r in stuck_tasks],
        }
        # expire non-terminal handoffs past their expiry (crash-safe sweep)
        expired = self.conn.execute(
            "SELECT handoff_id FROM handoffs WHERE status IN (?,?,?)"
            " AND expires_at IS NOT NULL AND expires_at < strftime('%Y-%m-%dT%H:%M:%fZ','now')",
            (S.HO_DRAFT, S.HO_VALIDATED, S.HO_OFFERED),
        ).fetchall()
        for row in expired:
            self.conn.execute("UPDATE handoffs SET status=? WHERE handoff_id=?", (S.HO_EXPIRED, row["handoff_id"]))
        report["handoffs_expired"] = len(expired)
        self._event(None, None, "reconcile", report)
        self.conn.commit()
        return report

    # -------------------------------------------------------------- helpers

    def transition_run_if(self, run_id: str, target: str) -> None:
        row = self._require("runs", run_id)
        if target in S.RUN_TRANSITIONS.get(row["status"], set()):
            self.transition_run(run_id, target)

    def _transition_handoff(self, handoff_id: str, target: str) -> None:
        ho = self._require("handoffs", handoff_id)
        S.check_transition(ho["status"], target, S.HO_TRANSITIONS, "handoff")
        self.conn.execute("UPDATE handoffs SET status=? WHERE handoff_id=?", (target, handoff_id))

    def _require(self, table: str, key: str) -> sqlite3.Row:
        col = {
            "runs": "run_id",
            "tasks": "task_id",
            "handoffs": "handoff_id",
            "usage": "usage_id",
            "evaluations": "evaluation_id",
        }[table]
        row = self.conn.execute(f"SELECT * FROM {table} WHERE {col}=?", (key,)).fetchone()
        if row is None:
            raise LifecycleError(f"{table[:-1]} not found: {key}")
        return row

    def _event(self, run_id: str | None, task_id: str | None, kind: str, payload: dict | None) -> None:
        self.conn.execute(
            "INSERT INTO events (run_id, task_id, kind, payload_json) VALUES (?,?,?,?)",
            (run_id, task_id, kind, json.dumps(payload) if payload is not None else None),
        )
