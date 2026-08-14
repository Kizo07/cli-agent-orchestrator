"""CAO state directory resolution (plan V2 §12.1).

State must live outside the AWS credential tree. ``CAO_HOME_DIR`` governs
every CAO server, command, workflow, and MCP process; the deployment sets it
in ``~/.config/environment.d/cao.conf``.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_STATE_DIR = Path.home() / ".aws" / "cli-agent-orchestrator"
AGENT_SYSTEM_SUBDIR = "agent_system"


def state_dir() -> Path:
    raw = os.environ.get("CAO_HOME_DIR", "").strip()
    return Path(raw).expanduser() if raw else DEFAULT_STATE_DIR


def agent_system_dir() -> Path:
    d = state_dir() / AGENT_SYSTEM_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d
