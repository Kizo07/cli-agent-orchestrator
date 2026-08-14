"""State backup/restore for crash safety and rollback (plan V2 §12.6).

Backups are owner-only (0700/0600). Restore verifies the manifest before
swapping anything in.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from .state_dir import state_dir


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def backup_state(backup_root: str | Path | None = None) -> Path:
    src = state_dir()
    root = Path(backup_root) if backup_root else src.parent / "backups"
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    import datetime as _dt

    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = root / f"cao-state-{stamp}"
    manifest: dict[str, str] = {}
    for p in src.rglob("*"):
        if p.is_file() and not p.name.endswith(("-wal", "-shm")):
            rel = p.relative_to(src)
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
            os.chmod(target, 0o600)
            manifest[str(rel)] = _sha256(p)
    (dest / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    os.chmod(dest / "MANIFEST.json", 0o600)
    return dest


def verify_backup(backup_dir: str | Path) -> bool:
    backup_dir = Path(backup_dir)
    manifest = json.loads((backup_dir / "MANIFEST.json").read_text())
    for rel, digest in manifest.items():
        p = backup_dir / rel
        if not p.is_file() or _sha256(p) != digest:
            return False
    return True
