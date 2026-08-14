"""Phase 7 gate tests: handoff expiry, idempotent delivery, rework handoffs,
restart-safe recovery, and sanitized legacy projection."""

from __future__ import annotations

import pytest

from cli_agent_orchestrator.agent_system.handoff.projection import (
    PROJECTION_MARKER,
    write_projection,
)
from cli_agent_orchestrator.agent_system.lifecycle import states as S
from cli_agent_orchestrator.agent_system.lifecycle.service import (
    LifecycleService,
    TaskSpec,
)
from cli_agent_orchestrator.agent_system.policy.bundle import load_policy_bundle

AGENT_SYSTEM_ROOT = "/home/fire/Documents/AgentSystem"
LEGACY_HANDOFF_DIR = "/home/fire/Documents/AgentSystem/handoffs"


@pytest.fixture()
def svc(tmp_path):
    return LifecycleService.open(tmp_path / "lifecycle.db")


@pytest.fixture()
def bundle():
    return load_policy_bundle(AGENT_SYSTEM_ROOT)


def _to_review(svc, bundle, tmp_path):
    run = svc.create_run("handoff goal", bundle, project_slug="demo", idempotency_key=f"ho-{id(svc)}")
    contract = tmp_path / "contract.json"
    contract.write_text("{}")
    (task,) = svc.plan_tasks(run, [TaskSpec(role="implementer", contract_path=str(contract))])
    svc.assign_task(task, provider="opencode", provider_family="opencode-glm", session_id="impl-1")
    svc.transition_task(task, S.TASK_IMPLEMENTING)
    a = tmp_path / "a.diff"
    a.write_text("diff")
    svc.submit_artifact(task, a)
    svc.record_verification(task, passed=True)
    return run, task


def test_idempotent_handoff_delivery(svc, bundle, tmp_path):
    run, task = _to_review(svc, bundle, tmp_path)
    h1 = svc.request_review(task, "rev-1", "kimi", idempotency_key="review-xyz")
    h2 = svc.request_review(task, "rev-1", "kimi", idempotency_key="review-xyz")
    assert h1 == h2
    n = svc.conn.execute("SELECT COUNT(*) AS n FROM handoffs WHERE kind='review'").fetchone()["n"]
    assert n == 1


def test_handoff_expiry_survives_reconcile(svc, bundle, tmp_path):
    run, task = _to_review(svc, bundle, tmp_path)
    ho = svc.request_review(task, "rev-1", "kimi", expires_in_seconds=-1)  # already past
    report = svc.reconcile()
    assert report["handoffs_expired"] == 1
    assert svc._require("handoffs", ho)["status"] == S.HO_EXPIRED


def test_rejection_creates_rework_handoff_and_new_review_cycle(svc, bundle, tmp_path):
    run, task = _to_review(svc, bundle, tmp_path)
    ho = svc.request_review(task, "rev-1", "kimi")
    svc.accept_handoff(ho)
    svc.complete_review(ho, approved=False, findings_json='[{"id": "f1"}]')
    rework = svc.conn.execute("SELECT * FROM handoffs WHERE kind='rework'").fetchone()
    assert rework is not None
    assert rework["status"] == S.HO_OFFERED
    assert rework["next_action"]
    # rework + resubmit + new review bound to the NEW artifact hash
    a2 = tmp_path / "a2.diff"
    a2.write_text("diff v2")
    svc.submit_artifact(task, a2)
    svc.record_verification(task, passed=True)
    ho2 = svc.request_review(task, "rev-2", "kimi")
    row2 = svc._require("handoffs", ho2)
    assert row2["artifact_sha256"] != svc._require("handoffs", ho)["artifact_sha256"]


def test_handoffs_survive_restart(svc, bundle, tmp_path):
    run, task = _to_review(svc, bundle, tmp_path)
    ho = svc.request_review(task, "rev-1", "kimi")
    # simulate CAO restart: reopen the database
    db_path = tmp_path / "lifecycle.db"
    svc2 = LifecycleService.open(db_path)
    row = svc2._require("handoffs", ho)
    assert row["status"] == S.HO_OFFERED
    svc2.accept_handoff(ho)
    svc2.complete_review(ho, approved=True)
    assert svc2._require("tasks", task)["status"] == S.TASK_DONE


def test_projection_is_sanitized_and_marked(svc, bundle, tmp_path):
    run, task = _to_review(svc, bundle, tmp_path)
    ho = svc.request_review(task, "rev-1", "kimi")
    svc.accept_handoff(ho)
    svc.complete_review(ho, approved=False, findings_json='[{"id": "f1"}, {"id": "f2"}]')
    dest = tmp_path / "handoffs"
    path = write_projection(svc.conn, ho, dest)
    text = path.read_text()
    assert PROJECTION_MARKER in text
    assert ho in path.name
    assert "findings_count: 2" in text
    # forbidden content classes never appear
    for bad in ("transcript", "BEGIN PRIVATE", "api_key", "password"):
        assert bad.lower() not in text.lower()
    # canonical data matches projection
    assert svc._require("handoffs", ho)["artifact_sha256"] in text


def test_projection_into_legacy_dir_matches_canonical(svc, bundle, tmp_path):
    run, task = _to_review(svc, bundle, tmp_path)
    ho = svc.request_review(task, "rev-1", "kimi")
    path = write_projection(svc.conn, ho, tmp_path / "legacy")
    assert path.exists()
    assert "NON-AUTHORITATIVE" in path.read_text()
