"""Tests for agent_system.security hardening (plan V2 §17.2/17.3)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cli_agent_orchestrator.agent_system.security import control_auth, launch_guard


# ---------------------------------------------------------------- launch guard


def test_default_mode_preserves_upstream_behavior(monkeypatch):
    monkeypatch.delenv("CAO_STRICT_PERMISSIONS", raising=False)
    assert launch_guard.agy_permission_bypass_allowed() is True
    assert launch_guard.hermes_yolo_allowed() is True
    assert launch_guard.codex_yolo_allowed(wildcard_tools=True) is True
    assert launch_guard.codex_yolo_allowed(wildcard_tools=False) is False


def test_strict_mode_removes_bypasses(monkeypatch):
    monkeypatch.setenv("CAO_STRICT_PERMISSIONS", "1")
    monkeypatch.delenv("CAO_AGY_SKIP_PERMISSIONS", raising=False)
    monkeypatch.delenv("CAO_HERMES_YOLO", raising=False)
    monkeypatch.delenv("CAO_CODEX_YOLO", raising=False)
    assert launch_guard.agy_permission_bypass_allowed() is False
    assert launch_guard.hermes_yolo_allowed() is False
    assert launch_guard.codex_yolo_allowed(wildcard_tools=True) is False


def test_strict_mode_explicit_opt_ins(monkeypatch):
    monkeypatch.setenv("CAO_STRICT_PERMISSIONS", "1")
    monkeypatch.setenv("CAO_AGY_SKIP_PERMISSIONS", "1")
    monkeypatch.setenv("CAO_HERMES_YOLO", "1")
    monkeypatch.setenv("CAO_CODEX_YOLO", "1")
    assert launch_guard.agy_permission_bypass_allowed() is True
    assert launch_guard.hermes_yolo_allowed() is True
    assert launch_guard.codex_yolo_allowed(wildcard_tools=False) is True


# ---------------------------------------------------------------- loopback bind


def test_loopback_hosts_allowed(monkeypatch):
    monkeypatch.delenv("CAO_ALLOW_REMOTE_BINDING", raising=False)
    for h in ("127.0.0.1", "::1", "localhost"):
        assert control_auth.enforce_loopback_binding(h) == h


def test_remote_host_refused(monkeypatch):
    monkeypatch.delenv("CAO_ALLOW_REMOTE_BINDING", raising=False)
    with pytest.raises(SystemExit):
        control_auth.enforce_loopback_binding("0.0.0.0")


def test_remote_host_with_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("CAO_ALLOW_REMOTE_BINDING", "1")
    assert control_auth.enforce_loopback_binding("0.0.0.0") == "0.0.0.0"


# ---------------------------------------------------------------- control auth


def _app():
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/sessions")
    def list_sessions():
        return []

    @app.post("/sessions")
    def create_session():
        return {"created": True}

    @app.get("/static/ui")
    def ui():
        return "<html/>"

    return app


def test_no_token_configured_keeps_upstream_behavior(monkeypatch):
    monkeypatch.delenv("CAO_CONTROL_TOKEN", raising=False)
    app = _app()
    control_auth.install_control_auth(app)
    client = TestClient(app)
    assert client.post("/sessions").status_code == 200


def test_token_required_for_control_operations(monkeypatch):
    monkeypatch.setenv("CAO_CONTROL_TOKEN", "sekrit-token")
    app = _app()
    control_auth.install_control_auth(app)
    client = TestClient(app)
    # mutating request without token -> 401
    assert client.post("/sessions").status_code == 401
    # control-prefix read without token -> 401
    assert client.get("/sessions").status_code == 401
    # non-control read stays browsable (local dashboard)
    assert client.get("/static/ui").status_code == 200
    # correct token passes
    assert client.post("/sessions", headers={"Authorization": "Bearer sekrit-token"}).status_code == 200
    assert client.get("/sessions", headers={"Authorization": "Bearer sekrit-token"}).status_code == 200
    # wrong token rejected
    assert client.post("/sessions", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_ws_token_check(monkeypatch):
    class FakeWS:
        def __init__(self, headers=None, query=None):
            self.headers = headers or {}
            self.query_params = query or {}

    monkeypatch.setenv("CAO_CONTROL_TOKEN", "ws-token")
    assert control_auth.ws_token_allowed(FakeWS(headers={"authorization": "Bearer ws-token"}))
    assert control_auth.ws_token_allowed(FakeWS(query={"access_token": "ws-token"}))
    assert not control_auth.ws_token_allowed(FakeWS())
    assert not control_auth.ws_token_allowed(FakeWS(headers={"authorization": "Bearer nope"}))
    monkeypatch.delenv("CAO_CONTROL_TOKEN", raising=False)
    assert control_auth.ws_token_allowed(FakeWS())  # unconfigured -> upstream behavior
