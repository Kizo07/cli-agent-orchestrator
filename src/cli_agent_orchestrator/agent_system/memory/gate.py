"""HardenedMemoryGate: the only write path into canonical shared memory.

Workers PROPOSE bounded memories; CAO validates identity, scope, task, and
record class, scans, deduplicates, applies approval gates, then performs the
atomic write through the injected persistence callbacks (production wires the
upstream MemoryService; tests use stubs). Plan V2 §12.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

from .scanner import scan_memory_content

ALLOWED_SCOPES = {"session", "project", "agent-role", "global-user"}
ALLOWED_CLASSES = {
    "preference",
    "decision",
    "convention",
    "verified-fact",
    "reusable-lesson",
    "reference-pointer",
    "operational-gotcha",
}
MAX_CONTENT_CHARS = 4000
MAX_KEY_CHARS = 128

# Least-privilege recall scopes per role (plan V2 §12.5). Federated disabled.
RECALL_SCOPES = {
    "implementer": {"project", "agent-role"},
    "specialist": {"project", "agent-role"},
    "verifier": {"project", "agent-role"},
    "reviewer": {"project"},  # plus review policy; never implementer session scope
    "architect": {"project", "agent-role"},
    "supervisor": {"session", "project", "agent-role", "global-user"},
    "memory-curator": {"project", "agent-role", "global-user"},
    "standalone": set(),
}


class MemoryGateError(Exception):
    pass


class ScopeBindingError(MemoryGateError):
    pass


class ContradictionFound(MemoryGateError):
    pass


@dataclass
class SessionMeta:
    """Identity bound from the CAO session — never from caller input alone."""

    session_id: str
    role: str
    project_id: Optional[str] = None
    run_id: Optional[str] = None
    task_id: Optional[str] = None


@dataclass
class GateDecision:
    audit_id: str
    status: str  # approved | pending_approval | rejected | duplicate | tombstoned
    detail: str = ""


PersistFn = Callable[[str, str, Optional[str], str, str, str], None]
# (content, scope, scope_id, key, record_class, tags) -> None
DeleteFn = Callable[[str, Optional[str], str], None]
# (scope, scope_id, key) -> None


class HardenedMemoryGate:
    def __init__(self, conn: sqlite3.Connection, persist: PersistFn, delete: DeleteFn):
        self.conn = conn
        self._persist = persist
        self._delete = delete

    # ------------------------------------------------------------- proposal

    def propose(
        self,
        meta: SessionMeta,
        scope: str,
        key: str,
        content: str,
        record_class: str,
        tags: str = "",
        policy_version: str = "memory-policy/1",
    ) -> GateDecision:
        if scope not in ALLOWED_SCOPES:
            raise ScopeBindingError(f"scope not allowed: {scope}")
        if record_class not in ALLOWED_CLASSES:
            raise MemoryGateError(f"record class not allowed: {record_class}")
        if len(content) > MAX_CONTENT_CHARS:
            raise MemoryGateError("content exceeds size limit")
        if not key or len(key) > MAX_KEY_CHARS or not all(c.isalnum() or c in "-_." for c in key):
            raise MemoryGateError("invalid memory key")

        # scope identity binds from the CAO session, never caller input
        scope_id: Optional[str] = None
        if scope == "project":
            if not meta.project_id:
                raise ScopeBindingError("project scope requires a CAO-bound project identity")
            scope_id = meta.project_id
        elif scope == "agent-role":
            scope_id = meta.role
        elif scope == "session":
            scope_id = meta.session_id

        scan = scan_memory_content(content, key=key, tags=tags)
        if not scan.clean:
            detail = json.dumps([f.__dict__ for f in scan.findings])
            audit_id = self._audit(meta, scope, scope_id, key, record_class, content, "rejected", policy_version, detail)
            self.conn.commit()
            return GateDecision(audit_id, "rejected", detail)

        content_hash = hashlib.sha256(content.encode()).hexdigest()
        prior = self.conn.execute(
            "SELECT audit_id, content_hash, status FROM memory_audit"
            " WHERE scope=? AND COALESCE(scope_id,'')=? AND key=? AND status != 'tombstoned'"
            " ORDER BY rowid DESC LIMIT 1",
            (scope, scope_id or "", key),
        ).fetchone()
        if prior:
            if prior["content_hash"] == content_hash:
                return GateDecision(prior["audit_id"], "duplicate", "idempotent no-op")
            detail = f"contradicts existing memory {prior['audit_id']}"
            audit_id = self._audit(meta, scope, scope_id, key, record_class, content, "contradiction", policy_version, detail)
            self.conn.commit()
            raise ContradictionFound(detail)

        status = "pending_approval" if scope == "global-user" else "approved"
        audit_id = self._audit(meta, scope, scope_id, key, record_class, content, status, policy_version, "")
        if status == "approved":
            self._persist(content, scope, scope_id, key, record_class, tags)
        self.conn.commit()
        return GateDecision(audit_id, status)

    def approve(self, audit_id: str, approver: str) -> None:
        """Human approval gate for global-user scope (plan V2 §12.4)."""
        row = self.conn.execute(
            "SELECT * FROM memory_audit WHERE audit_id=? AND status='pending_approval'", (audit_id,)
        ).fetchone()
        if row is None:
            raise MemoryGateError(f"no pending proposal: {audit_id}")
        self.conn.execute(
            "UPDATE memory_audit SET status='approved', approver=? WHERE audit_id=?",
            (approver, audit_id),
        )
        self._persist(row["content"], row["scope"], row["scope_id"], row["key"], row["record_class"], "")
        self.conn.commit()

    # ------------------------------------------------------------ tombstone

    def forget(self, meta: SessionMeta, scope: str, scope_id: Optional[str], key: str, reason: str) -> str:
        """Audited tombstone deletion (plan V2 §12.4)."""
        rows = self.conn.execute(
            "SELECT audit_id FROM memory_audit WHERE scope=? AND COALESCE(scope_id,'')=? AND key=?"
            " AND status='approved'",
            (scope, scope_id or "", key),
        ).fetchall()
        if not rows:
            raise MemoryGateError(f"no approved memory to forget: {scope}/{key}")
        for r in rows:
            self.conn.execute(
                "UPDATE memory_audit SET status='tombstoned', detail=? WHERE audit_id=?",
                (f"tombstone: {reason}"[:500], r["audit_id"]),
            )
        self._delete(scope, scope_id, key)
        audit_id = self._audit(meta, scope, scope_id, key, "tombstone", "", "tombstoned", "memory-policy/1", reason[:500])
        self.conn.commit()
        return audit_id

    # --------------------------------------------------------------- recall

    @staticmethod
    def recall_scopes(role: str) -> set[str]:
        return set(RECALL_SCOPES.get(role, set()))

    # ------------------------------------------------------- backup/restore

    def backup_manifest(self) -> dict:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM memory_audit GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}

    # -------------------------------------------------------------- helpers

    def _audit(
        self,
        meta: SessionMeta,
        scope: str,
        scope_id: Optional[str],
        key: str,
        record_class: str,
        content: str,
        status: str,
        policy_version: str,
        detail: str,
    ) -> str:
        audit_id = f"mem-{uuid.uuid4().hex[:12]}"
        content_hash = hashlib.sha256(content.encode()).hexdigest() if content else ""
        self.conn.execute(
            "INSERT INTO memory_audit (audit_id, scope, scope_id, key, record_class, content,"
            " content_hash, status, session_id, task_id, run_id, policy_version, detail)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                audit_id,
                scope,
                scope_id,
                key,
                record_class,
                content,
                content_hash,
                status,
                meta.session_id,
                meta.task_id,
                meta.run_id,
                policy_version,
                detail,
            ),
        )
        return audit_id
