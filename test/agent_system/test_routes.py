"""Model route policy tests (plan V2 Phase 4 gate)."""

from __future__ import annotations

import pytest

from cli_agent_orchestrator.agent_system.policy.routes import QWEN_DEFAULT, load_route_policy


def test_qwen_default_resolves_to_exact_token_plan_model():
    policy = load_route_policy()
    route = policy.resolve(QWEN_DEFAULT)
    assert route.provider == "opencode"
    assert route.provider_family == "alibaba-token-plan"
    assert route.resolved_model == "qwen3.7-plus"
    assert route.opencode_model_id == "alibaba-token-plan/qwen3.7-plus"
    # fallbacks are exact allowlisted Token Plan models only
    assert route.fallbacks == ("qwen3.8-max", "qwen3.6-flash")


def test_qwen_cli_is_excluded():
    policy = load_route_policy()
    assert policy.is_excluded("qwen_cli")
    assert not policy.is_excluded("opencode")


def test_unknown_alias_fails_closed():
    policy = load_route_policy()
    with pytest.raises(KeyError):
        policy.resolve("nonexistent-alias")
