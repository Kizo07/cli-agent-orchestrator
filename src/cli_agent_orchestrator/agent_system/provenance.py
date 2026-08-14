"""Fork provenance reporting (INTEGRATION_PLAN_V2.md 8.4).

The installed command must be able to report: local version, local commit,
upstream base tag and commit, schema version, build timestamp, and dirty-build
marker. Data comes from docs/fork/build-provenance.json shipped with the tree.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path


@dataclass(frozen=True)
class Provenance:
    fork: str
    upstream: str
    upstream_base_tag: str
    upstream_base_commit: str
    local_release: str
    local_commit: str | None
    schema_version: str
    built_at: str | None
    dirty_build: bool

    def report(self) -> str:
        lines = [
            f"fork:             {self.fork}",
            f"upstream:         {self.upstream}",
            f"upstream base:    {self.upstream_base_tag} ({self.upstream_base_commit})",
            f"local release:    {self.local_release}",
            f"local commit:     {self.local_commit or 'unstamped'}",
            f"schema version:   {self.schema_version}",
            f"built at:         {self.built_at or 'unstamped'}",
            f"dirty build:      {self.dirty_build}",
        ]
        return "\n".join(lines)


def _locate_provenance_file() -> Path | None:
    # Installed wheel: package data; dev tree: docs/fork/.
    try:
        ref = resources.files("cli_agent_orchestrator") / "docs" / "fork" / "build-provenance.json"
        p = Path(str(ref))
        if p.exists():
            return p
    except Exception:
        pass
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "docs" / "fork" / "build-provenance.json"
        if cand.exists():
            return cand
    return None


def load_provenance() -> Provenance:
    path = _locate_provenance_file()
    if path is None:
        return Provenance(
            fork="unknown",
            upstream="awslabs/cli-agent-orchestrator",
            upstream_base_tag="unknown",
            upstream_base_commit="unknown",
            local_release="unknown",
            local_commit=None,
            schema_version="unknown",
            built_at=None,
            dirty_build=False,
        )
    d = json.loads(path.read_text())
    return Provenance(
        fork=d.get("fork", "unknown"),
        upstream=d.get("upstream", "unknown"),
        upstream_base_tag=d.get("upstream_base_tag", "unknown"),
        upstream_base_commit=d.get("upstream_base_commit", "unknown"),
        local_release=d.get("local_release", "unknown"),
        local_commit=d.get("local_commit"),
        schema_version=d.get("schema_version", "unknown"),
        built_at=d.get("built_at"),
        dirty_build=bool(d.get("dirty_build", False)),
    )
