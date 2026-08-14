"""Control-plane authentication and binding guards (plan V2 §17.2).

Deployment semantics:

* ``CAO_CONTROL_TOKEN`` set  -> bearer token required for every control
  operation (all mutating requests anywhere, and every request on control
  path prefixes). Read-only UI/document paths stay browsable so the local
  dashboard keeps working.
* ``CAO_CONTROL_TOKEN`` unset -> upstream behavior (loopback-only assumed);
  a loud warning is logged once.
* ``cao-server`` refuses non-loopback binding unless
  ``CAO_ALLOW_REMOTE_BINDING=1``.
"""

from __future__ import annotations

import logging
import os
import secrets
from typing import Iterable

logger = logging.getLogger(__name__)

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}

CONTROL_PATH_PREFIXES: tuple[str, ...] = (
    "/sessions",
    "/terminals",
    "/flows",
    "/workflows",
    "/memory",
    "/agents",
    "/skills",
    "/profiles",
    "/mcp",
    "/plugins",
    "/settings",
    "/runs",
)

_WARNED = {"once": False}


def control_token() -> str | None:
    tok = os.environ.get("CAO_CONTROL_TOKEN", "").strip()
    return tok or None


def _is_control_path(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") or path.startswith(p + "?") for p in CONTROL_PATH_PREFIXES)


def install_control_auth(app) -> None:
    """Attach bearer-token enforcement to a FastAPI app (idempotent).

    Safe to call after the ASGI middleware stack has already been built
    (e.g. ``main()`` invoked from tests that already served requests): in
    that case the built stack is wrapped directly instead of using
    ``add_middleware`` (which Starlette refuses post-startup).
    """
    if getattr(app.state, "agent_system_control_auth", False):
        return

    token = control_token()
    if token is None and not _WARNED["once"]:
        _WARNED["once"] = True
        logger.warning(
            "CAO_CONTROL_TOKEN is not set: control-plane requests are NOT "
            "authenticated. Set CAO_CONTROL_TOKEN for production (plan V2 17.2)."
        )

    if getattr(app, "middleware_stack", None) is None:
        app.add_middleware(ControlAuthASGI)
    else:
        app.middleware_stack = ControlAuthASGI(app.middleware_stack)
    app.state.agent_system_control_auth = True


class ControlAuthASGI:
    """Raw ASGI gate: enforce CAO_CONTROL_TOKEN on control operations.

    HTTP only — the PTY websocket handshake validates its token inside the
    endpoint handler (``ws_token_allowed``).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and control_token() is not None:
            method = scope.get("method", "GET")
            path = scope.get("path", "")
            if method != "GET" or _is_control_path(path):
                headers = {k.decode("latin1"): v.decode("latin1") for k, v in scope.get("headers", [])}
                auth = headers.get("authorization", "")
                supplied = auth.split(" ", 1)[1].strip() if auth.lower().startswith("bearer ") else ""
                if not supplied or not secrets.compare_digest(supplied, control_token()):
                    await send(
                        {
                            "type": "http.response.start",
                            "status": 401,
                            "headers": [(b"content-type", b"application/json")],
                        }
                    )
                    await send(
                        {
                            "type": "http.response.body",
                            "body": b'{"detail":"control token required"}',
                        }
                    )
                    return
        await self.app(scope, receive, send)


def ws_token_allowed(websocket) -> bool:
    """Validate the PTY websocket handshake against the control token.

    Token arrives either as ``Authorization: Bearer <token>`` header or the
    ``access_token`` query param (the browser-viewer convention already used
    for credential scrubbing upstream).
    """
    tok = control_token()
    if tok is None:
        return True
    auth = websocket.headers.get("authorization", "")
    supplied = auth.split(" ", 1)[1].strip() if auth.lower().startswith("bearer ") else ""
    if not supplied:
        supplied = (websocket.query_params.get("access_token") or "").strip()
    return bool(supplied) and secrets.compare_digest(supplied, tok)


def enforce_loopback_binding(host: str) -> str:
    """Refuse to bind a non-loopback address unless explicitly opted in."""
    if host in _LOOPBACK_HOSTS:
        return host
    if os.environ.get("CAO_ALLOW_REMOTE_BINDING", "").strip() == "1":
        logger.warning("CAO server binding to non-loopback host %s (CAO_ALLOW_REMOTE_BINDING=1)", host)
        return host
    raise SystemExit(
        f"refusing to bind cao-server to non-loopback host '{host}'. "
        "Use a loopback address, or set CAO_ALLOW_REMOTE_BINDING=1 with a "
        "control token and a firewall (plan V2 17.2)."
    )


def generate_token() -> str:
    return secrets.token_urlsafe(32)
