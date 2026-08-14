"""Versioned policy bundle loading (plan V2 §9.4).

CAO loads a hashed policy bundle at run creation and records per run:
AgentSystem commit, role/provider/route policy hashes, scorecard rubric and
weight versions, memory-policy version, and handoff-schema version. A policy
change affects only new runs.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

POLICY_FILES = (
    "config/roles.yaml",
    "config/providers.yaml",
    "config/policies.yaml",
    "config/tool-registry.yaml",
    "schemas/task-contract.schema.json",
    "schemas/artifact-manifest.schema.json",
)

SCHEMA_VERSION = "policy-bundle/1"


@dataclass(frozen=True)
class PolicyBundle:
    agent_system_root: str
    agent_system_commit: str | None
    file_hashes: dict[str, str] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def bundle_hash(self) -> str:
        payload = json.dumps(
            {
                "commit": self.agent_system_commit,
                "files": self.file_hashes,
                "schema": self.schema_version,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema_version": self.schema_version,
                "agent_system_root": self.agent_system_root,
                "agent_system_commit": self.agent_system_commit,
                "file_hashes": self.file_hashes,
                "bundle_hash": self.bundle_hash(),
            },
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, raw: str) -> "PolicyBundle":
        d = json.loads(raw)
        return cls(
            agent_system_root=d["agent_system_root"],
            agent_system_commit=d.get("agent_system_commit"),
            file_hashes=d.get("file_hashes", {}),
            schema_version=d.get("schema_version", SCHEMA_VERSION),
        )


def _git_head(root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def load_policy_bundle(agent_system_root: str | Path) -> PolicyBundle:
    """Hash every policy file; fail closed on missing files."""
    root = Path(agent_system_root).expanduser()
    if not root.is_dir():
        raise FileNotFoundError(f"AgentSystem root not found: {root}")
    hashes: dict[str, str] = {}
    for rel in POLICY_FILES:
        p = root / rel
        if not p.is_file():
            raise FileNotFoundError(f"required policy file missing: {p}")
        hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return PolicyBundle(
        agent_system_root=str(root),
        agent_system_commit=_git_head(root),
        file_hashes=hashes,
    )
