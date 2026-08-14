"""Synthetic workflow tests for the lifecycle state machine (plan V2 Phase 3 gate).

Covers: success, rejection + rework, cancellation, timeout, stale-artifact
review, crash reconciliation, idempotent replay, reviewer independence, and
policy-bundle hashing.
"""

from __future__ import annotations

import pytest

from cli_agent_orchestrator.agent_system.lifecycle import states as S
from cli_agent_orchestrator.agent_system.lifecycle.service import (
    GateFailure,
    LifecycleError,
    LifecycleService,
    ReviewIndependenceViolation,
    StaleArtifact,
    TaskSpec,
)
from cli_agent_orchestrator.agent_system.policy.bundle import load_policy_bundle

AGENT_SYSTEM_ROOT = "/home/fire/Documents/AgentSystem"


@pytest.fixture()
def svc(tmp_path):
    return LifecycleService.open(tmp_path / "lifecycle.db")


@pytest.fixture()
def bundle():
    return load_policy_bundle(AGENT_SYSTEM_ROOT)


def _implement(svc, bundle, tmp_path, family="opencode-glm", reviewer_family="kimi"):
    """Drive a run to the point where review is offered; return ids."""
    run = svc.create_run("demo goal", bundle, project_slug="demo", idempotency_key="k1")
    contract = tmp_path / "contract.json"
    contract.write_text('{"task": "demo"}')
    (task,) = svc.plan_tasks(run, [TaskSpec(role="implementer", contract_path=str(contract))])
    svc.assign_task(task, provider="opencode", provider_family=family, session_id="sess-impl", model_alias="glm-implementer")
    svc.transition_task(task, S.TASK_IMPLEMENTING)
    usage = svc.begin_usage(run, task, "opencode", "glm-5.2", "implementer")
    svc.attach_usage(usage, pid=1234, resolved_model="glm-5.2")
    artifact = tmp_path / "artifact.diff"
    artifact.write_text("diff --git demo")
    svc.submit_artifact(task, artifact)
    svc.finish_usage(usage, "completed")
    svc.record_verification(task, passed=True)
    ho = svc.request_review(task, reviewer_session="sess-review", reviewer_provider_family=reviewer_family)
    return run, task, ho


def test_success_workflow(svc, bundle, tmp_path):
    run, task, ho = _implement(svc, bundle, tmp_path)
    svc.accept_handoff(ho)
    svc.complete_review(ho, approved=True, findings_json="[]")
    assert svc._require("tasks", task)["status"] == S.TASK_DONE
    svc.transition_run(run, S.RUN_COMPLETED)
    assert svc._require("runs", run)["status"] == S.RUN_COMPLETED


def test_rejection_and_rework_cycle(svc, bundle, tmp_path):
    run, task, ho = _implement(svc, bundle, tmp_path)
    svc.accept_handoff(ho)
    svc.complete_review(ho, approved=False, findings_json='[{"blocking": true}]')
    assert svc._require("tasks", task)["status"] == S.TASK_REWORK
    # rework: new artifact hash, new verification, new review handoff
    artifact2 = tmp_path / "artifact2.diff"
    artifact2.write_text("diff --git demo v2")
    new_sha = svc.submit_artifact(task, artifact2)
    assert new_sha != svc._require("handoffs", ho)["artifact_sha256"]
    svc.record_verification(task, passed=True)
    ho2 = svc.request_review(task, reviewer_session="sess-review2", reviewer_provider_family="kimi")
    svc.accept_handoff(ho2)
    svc.complete_review(ho2, approved=True)
    assert svc._require("tasks", task)["status"] == S.TASK_DONE


def test_stale_diff_review_rejected(svc, bundle, tmp_path):
    run, task, ho = _implement(svc, bundle, tmp_path)
    svc.accept_handoff(ho)
    # artifact silently changes after the review handoff froze the hash
    svc.conn.execute("UPDATE tasks SET artifact_sha256='deadbeef' WHERE task_id=?", (task,))
    with pytest.raises(StaleArtifact):
        svc.complete_review(ho, approved=True)
    assert svc._require("handoffs", ho)["status"] == S.HO_CANCELLED


def test_review_independence_enforced(svc, bundle, tmp_path):
    run = svc.create_run("g", bundle, idempotency_key="ind-1")
    contract = tmp_path / "c.json"
    contract.write_text("{}")
    (task,) = svc.plan_tasks(run, [TaskSpec(role="implementer", contract_path=str(contract))])
    svc.assign_task(task, provider="opencode", provider_family="opencode-glm", session_id="sess-A")
    svc.transition_task(task, S.TASK_IMPLEMENTING)
    a = tmp_path / "a.diff"
    a.write_text("x")
    svc.submit_artifact(task, a)
    svc.record_verification(task, passed=True)
    with pytest.raises(ReviewIndependenceViolation):
        svc.request_review(task, reviewer_session="sess-A", reviewer_provider_family="kimi")
    with pytest.raises(ReviewIndependenceViolation):
        svc.request_review(task, reviewer_session="sess-B", reviewer_provider_family="opencode-glm")


def test_cancellation_and_timeout(svc, bundle, tmp_path):
    run = svc.create_run("g", bundle, idempotency_key="cancel-1")
    (task,) = svc.plan_tasks(run, [TaskSpec(role="specialist")])
    svc.transition_task(task, S.TASK_CANCELLED)
    svc.transition_run(run, S.RUN_CANCELLED)
    assert svc._require("tasks", task)["status"] == S.TASK_CANCELLED

    run2 = svc.create_run("g2", bundle, idempotency_key="timeout-1")
    (t2,) = svc.plan_tasks(run2, [TaskSpec(role="implementer")])
    svc.assign_task(t2, provider="agy", provider_family="gemini", session_id="s")
    svc.transition_task(t2, S.TASK_IMPLEMENTING)
    svc.transition_task(t2, S.TASK_TIMEOUT)
    assert svc._require("tasks", t2)["status"] == S.TASK_TIMEOUT


def test_illegal_transitions_rejected(svc, bundle):
    run = svc.create_run("g", bundle, idempotency_key="illegal-1")
    with pytest.raises(LifecycleError):
        svc.transition_run(run, S.RUN_COMPLETED)  # created -> completed illegal
    (task,) = svc.plan_tasks(run, [TaskSpec(role="implementer")])
    with pytest.raises(LifecycleError):
        svc.transition_task(task, S.TASK_DONE)


def test_idempotent_replay(svc, bundle, tmp_path):
    r1 = svc.create_run("g", bundle, idempotency_key="dup")
    r2 = svc.create_run("g", bundle, idempotency_key="dup")
    assert r1 == r2
    n = svc.conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"]
    assert n == 1


def test_gates_block_done_without_review(svc, bundle, tmp_path):
    run = svc.create_run("g", bundle, idempotency_key="gates-1")
    (task,) = svc.plan_tasks(run, [TaskSpec(role="implementer")])
    svc.assign_task(task, provider="opencode", provider_family="opencode-glm", session_id="s")
    svc.transition_task(task, S.TASK_IMPLEMENTING)
    a = tmp_path / "a.diff"
    a.write_text("y")
    svc.submit_artifact(task, a)
    svc.record_verification(task, passed=True)
    # force "approved" without any completed review to prove the gate holds
    svc.conn.execute("UPDATE tasks SET status=? WHERE task_id=?", (S.TASK_APPROVED, task))
    svc.conn.commit()
    with pytest.raises(GateFailure):
        svc._complete_task_if_gates_pass(task)


def test_crash_reconciliation(svc, bundle, tmp_path):
    run, task, ho = _implement(svc, bundle, tmp_path)
    # simulate crash: usage left running, task stuck implementing
    u = svc.begin_usage(run, task, "opencode", "glm-5.2", "implementer")
    svc.conn.execute("UPDATE tasks SET status=? WHERE task_id=?", (S.TASK_IMPLEMENTING, task))
    svc.conn.commit()
    report = svc.reconcile()
    assert report["usage_marked_failed"] == 1
    assert task in report["tasks_needing_attention"]
    assert svc._require("usage", u)["status"] == "failed"


def test_policy_bundle_hashed_per_run(svc, bundle):
    run = svc.create_run("g", bundle, idempotency_key="pol-1")
    row = svc._require("runs", run)
    import json

    stored = json.loads(row["policy_bundle_json"])
    assert stored["bundle_hash"] == bundle.bundle_hash()
    assert "config/roles.yaml" in stored["file_hashes"]
    assert len(stored["file_hashes"]["config/roles.yaml"]) == 64
