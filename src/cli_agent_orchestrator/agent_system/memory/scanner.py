"""Secret and prompt-injection scanning for memory content (plan V2 §12.4/§17.4).

Every scope is scanned — not only federated. Model-produced content is
untrusted; findings reject the write.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SECRET_PATTERNS = [
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("openai-style-key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b")),
    ("private-key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer-token", re.compile(r"\bbearer\s+[A-Za-z0-9_\-\.=+/]{20,}", re.IGNORECASE)),
    (
        "credential-assignment",
        re.compile(
            r"(api[_-]?key|apikey|access[_-]?token|auth[_-]?token|token|secret|passwd|password)"
            r"\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{16,}",
            re.IGNORECASE,
        ),
    ),
    (
        "env-secret-export",
        re.compile(r"\bexport\s+[A-Z_]*(KEY|TOKEN|SECRET|CREDENTIAL)[A-Z_]*=\S{8,}"),
    ),
    ("dotted-platform-key", re.compile(r"\b[0-9a-f]{32}\.[A-Za-z0-9_\-]{16,}\b")),
]

INJECTION_PATTERNS = [
    ("instruction-override", re.compile(r"ignore (all )?(previous|prior|above) (instructions|prompts)", re.IGNORECASE)),
    ("system-replace", re.compile(r"(disregard|forget) your (system|instructions|rules)", re.IGNORECASE)),
    ("role-hijack", re.compile(r"you are now\b", re.IGNORECASE)),
    ("new-system-prompt", re.compile(r"new system prompt", re.IGNORECASE)),
    ("chatml-escape", re.compile(r"<\|im_start\|>|<\|system\|>", re.IGNORECASE)),
    ("system-marker", re.compile(r"^\s*(\[SYSTEM\]|###\s*SYSTEM)\b", re.IGNORECASE | re.MULTILINE)),
    ("agents-md-mutation", re.compile(r"(write|update|edit|append|modify)[^\n]{0,60}AGENTS\.md", re.IGNORECASE)),
    ("base64-blob", re.compile(r"[A-Za-z0-9+/=]{200,}")),
]


@dataclass
class ScanFinding:
    kind: str
    pattern: str
    excerpt: str


@dataclass
class ScanReport:
    findings: list[ScanFinding] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.findings


def scan_memory_content(content: str, key: str = "", tags: str = "") -> ScanReport:
    report = ScanReport()
    blob = f"{key}\n{tags}\n{content}"
    for name, rx in SECRET_PATTERNS:
        m = rx.search(blob)
        if m:
            report.findings.append(ScanFinding("secret", name, _excerpt(m.group(0))))
    for name, rx in INJECTION_PATTERNS:
        m = rx.search(blob)
        if m:
            report.findings.append(ScanFinding("injection", name, _excerpt(m.group(0))))
    return report


def _excerpt(s: str) -> str:
    """Bounded excerpt that never reproduces a full secret value."""
    s = s.strip()
    if len(s) <= 12:
        return s[:2] + "…"
    return s[:6] + "…" + s[-2:]
