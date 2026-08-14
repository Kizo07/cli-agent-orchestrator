"""Explicit provider permission modes (plan V2 §17.3).

Upstream CAO launches some providers with unconditional permission bypasses
(``agy --dangerously-skip-permissions``, ``hermes --yolo``, codex ``--yolo``
when allowed_tools contains ``*``). Under ``CAO_STRICT_PERMISSIONS=1`` those
bypasses are removed unless the operator explicitly opts the provider in:

* ``CAO_AGY_SKIP_PERMISSIONS=1``   -> agy ``--dangerously-skip-permissions``
* ``CAO_HERMES_YOLO=1``            -> hermes ``--yolo``
* ``CAO_CODEX_YOLO=1``             -> codex ``--yolo`` (otherwise honor
  ``codexProfile``; ``allowed_tools=["*"]`` no longer implies yolo)

Default (env unset) preserves upstream behavior so upstream tests and
existing deployments are unaffected; the AgentSystem deployment sets the
strict mode and grants bypasses only where role policy allows writes.
"""

from __future__ import annotations

import os


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def strict_permissions() -> bool:
    return _truthy("CAO_STRICT_PERMISSIONS")


def agy_permission_bypass_allowed() -> bool:
    if not strict_permissions():
        return True  # upstream default
    return _truthy("CAO_AGY_SKIP_PERMISSIONS")


def hermes_yolo_allowed() -> bool:
    if not strict_permissions():
        return True
    return _truthy("CAO_HERMES_YOLO")


def codex_yolo_allowed(wildcard_tools: bool) -> bool:
    if not strict_permissions():
        return wildcard_tools  # upstream: '*' tools imply yolo
    return _truthy("CAO_CODEX_YOLO")
