#!/usr/bin/env python3
"""Stamp docs/fork/build-provenance.json with the current local commit and build time.

Refuses to stamp a clean release marker when the worktree is dirty unless
--allow-dirty is given (plan INTEGRATION_PLAN_V2.md 8.4: dirty-build refusal).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROV = ROOT / "docs" / "fork" / "build-provenance.json"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", help="local release tag, e.g. agent-system-v0.1.0")
    ap.add_argument("--allow-dirty", action="store_true")
    args = ap.parse_args()

    dirty = bool(git("status", "--porcelain"))
    if dirty and not args.allow_dirty:
        print("refusing to stamp provenance: worktree is dirty (use --allow-dirty for dev markers)", file=sys.stderr)
        return 1

    data = json.loads(PROV.read_text())
    data["local_commit"] = git("rev-parse", "HEAD")
    data["built_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    data["dirty_build"] = dirty
    if args.release:
        data["local_release"] = args.release
    PROV.write_text(json.dumps(data, indent=2) + "\n")
    print(f"stamped {data['local_release']} @ {data['local_commit']} dirty={dirty}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
