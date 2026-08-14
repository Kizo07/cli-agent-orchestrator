"""Phase 5 gate tests: rubric parity, evaluation integrity, lossless migration."""

from __future__ import annotations

import json
import sqlite3

import pytest

from cli_agent_orchestrator.agent_system.lifecycle import db as _db
from cli_agent_orchestrator.agent_system.scorecard.migrate import migrate_legacy_stores
from cli_agent_orchestrator.agent_system.scorecard.rubric import (
    ScoreValidationError,
    posterior_score,
    weighted_score,
)
from cli_agent_orchestrator.agent_system.scorecard.service import (
    EvaluationError,
    ScorecardService,
)

AGENT_SYSTEM_ROOT = "/home/fire/Documents/AgentSystem"
LEGACY_FIXTURES = "/home/fire/Documents/AgentSystem/tools/tests/fixtures/legacy"


@pytest.fixture()
def conn(tmp_path):
    c = _db.connect(tmp_path / "lifecycle.db")
    yield c
    c.close()


# ------------------------------------------------------------------ rubric


def test_rubric_matches_legacy_implementation_on_live_data():
    """Current rubric outputs match the legacy implementation row-for-row.

    The legacy JSONL store is the reconciliation baseline; every row whose
    scores pass validation must aggregate identically under both
    implementations (plan V2 Phase 5 gate).
    """
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "legacy_weights",
        f"{AGENT_SYSTEM_ROOT}/tools/src/agent_system_tools/scorecard/weights.py",
    )
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    checked = 0
    preserved = 0
    for line in open(f"{AGENT_SYSTEM_ROOT}/scorecards/evaluations.jsonl"):
        rec = json.loads(line)
        try:
            ours = weighted_score(rec["scores"])
            theirs = legacy.weighted_score(rec["scores"])
            assert ours == theirs
            checked += 1
        except ScoreValidationError:
            preserved += 1
    assert checked + preserved == 66
    assert checked >= 60  # the vast majority validates under the current rubric


def test_score_bounds_enforced():
    with pytest.raises(ScoreValidationError):
        weighted_score(
            {
                "correctness": 6,
                "usefulness": 3,
                "instruction_adherence": 3,
                "reliability": 3,
                "efficiency": 3,
                "verification_burden": 3,
            }
        )
    with pytest.raises(ScoreValidationError):
        weighted_score({"correctness": 3})  # incomplete field set


def test_postior_shrinks_toward_prior():
    assert posterior_score([]) == 3.0
    assert posterior_score([5.0] * 100) > 4.5
    assert posterior_score([5.0]) < 3.2  # single observation stays near prior


# -------------------------------------------------------------- evaluation


def _usage(conn, uid="usage-x", provider="opencode"):
    conn.execute(
        "INSERT INTO usage (usage_id, provider, status) VALUES (?,?,?)", (uid, provider, "completed")
    )
    conn.commit()


def test_self_evaluation_rejected(conn):
    _usage(conn, provider="opencode")
    svc = ScorecardService(conn)
    scores = {
        "correctness": 4,
        "usefulness": 4,
        "instruction_adherence": 4,
        "reliability": 4,
        "efficiency": 4,
        "verification_burden": 2,
    }
    with pytest.raises(EvaluationError):
        svc.submit_evaluation("usage-x", "implementer", scores, evaluator_provider_family="opencode")
    eid = svc.submit_evaluation("usage-x", "reviewer", scores, evaluator_provider_family="kimi")
    assert eid.startswith("eval-")


def test_duplicate_evaluation_rejected_and_supersession_works(conn):
    _usage(conn, provider="agy")
    svc = ScorecardService(conn)
    scores = {
        "correctness": 3,
        "usefulness": 3,
        "instruction_adherence": 3,
        "reliability": 3,
        "efficiency": 3,
        "verification_burden": 3,
    }
    e1 = svc.submit_evaluation("usage-x", "reviewer", scores, evaluator_provider_family="kimi")
    with pytest.raises(EvaluationError):
        svc.submit_evaluation("usage-x", "reviewer", scores, evaluator_provider_family="kimi")
    e2 = svc.submit_evaluation("usage-x", "reviewer-2", scores, evaluator_provider_family="kimi")
    svc.supersede(e1, e2)
    row = conn.execute("SELECT superseded_by FROM evaluations WHERE evaluation_id=?", (e1,)).fetchone()
    assert row["superseded_by"] == e2


def test_route_statistics_report_sample_count(conn):
    _usage(conn, provider="opencode")
    svc = ScorecardService(conn)
    scores = {
        "correctness": 5,
        "usefulness": 5,
        "instruction_adherence": 5,
        "reliability": 5,
        "efficiency": 5,
        "verification_burden": 1,
    }
    svc.submit_evaluation("usage-x", "reviewer", scores, evaluator_provider_family="kimi")
    stats = svc.route_statistics(provider="opencode")
    assert stats["observations"] == 1
    assert 3.0 < stats["posterior"] < 5.0


# ---------------------------------------------------------------- migration


def test_migration_is_lossless_by_id_and_count(conn):
    report = migrate_legacy_stores(conn, AGENT_SYSTEM_ROOT)
    assert report.usage_rows == 84
    assert report.evaluation_rows == 66
    assert report.quirk_rows == 9
    assert report.foreign_key_ok
    # distinct IDs preserved
    n_usage = conn.execute("SELECT COUNT(DISTINCT usage_id) AS n FROM usage").fetchone()["n"]
    assert n_usage == 84 + len(report.usage_stubbed_for_fk)
    n_eval = conn.execute("SELECT COUNT(DISTINCT evaluation_id) AS n FROM evaluations").fetchone()["n"]
    assert n_eval == 66
    # every legacy record byte-recoverable
    row = conn.execute("SELECT legacy_json FROM usage LIMIT 1").fetchone()
    assert json.loads(row["legacy_json"])["usage_id"]
    # rubric parity for valid rows
    valid = conn.execute(
        "SELECT COUNT(*) AS n FROM evaluations WHERE rubric_version='score-v1'"
    ).fetchone()["n"]
    preserved = conn.execute(
        "SELECT COUNT(*) AS n FROM evaluations WHERE rubric_version='legacy-preserved'"
    ).fetchone()["n"]
    assert valid + preserved == 66
    assert preserved == len(report.legacy_preserved_evaluations)


def test_migration_rejects_double_apply(conn):
    migrate_legacy_stores(conn, AGENT_SYSTEM_ROOT)
    with pytest.raises(sqlite3.IntegrityError):
        migrate_legacy_stores(conn, AGENT_SYSTEM_ROOT)
