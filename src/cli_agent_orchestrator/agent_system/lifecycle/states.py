"""Canonical states and legal transitions (plan V2 §13.2, §16)."""

from __future__ import annotations

from . import IllegalTransition

# Run states
RUN_CREATED = "created"
RUN_PLANNED = "planned"
RUN_RUNNING = "running"
RUN_COMPLETED = "completed"
RUN_FAILED = "failed"
RUN_CANCELLED = "cancelled"
RUN_ROLLED_BACK = "rolled_back"

RUN_TERMINAL = {RUN_COMPLETED, RUN_FAILED, RUN_CANCELLED, RUN_ROLLED_BACK}

RUN_TRANSITIONS = {
    RUN_CREATED: {RUN_PLANNED, RUN_CANCELLED},
    RUN_PLANNED: {RUN_RUNNING, RUN_CANCELLED},
    RUN_RUNNING: {RUN_COMPLETED, RUN_FAILED, RUN_CANCELLED, RUN_ROLLED_BACK},
}

# Task states
TASK_PENDING = "pending"
TASK_ASSIGNED = "assigned"
TASK_IMPLEMENTING = "implementing"
TASK_SUBMITTED = "submitted"
TASK_VERIFYING = "verifying"
TASK_IN_REVIEW = "in_review"
TASK_REWORK = "rework"
TASK_APPROVED = "approved"
TASK_DONE = "done"
TASK_REJECTED = "rejected"
TASK_CANCELLED = "cancelled"
TASK_TIMEOUT = "timeout"
TASK_BLOCKED = "blocked"

TASK_TERMINAL = {TASK_DONE, TASK_REJECTED, TASK_CANCELLED, TASK_TIMEOUT}

TASK_TRANSITIONS = {
    TASK_PENDING: {TASK_ASSIGNED, TASK_CANCELLED},
    TASK_ASSIGNED: {TASK_IMPLEMENTING, TASK_CANCELLED, TASK_TIMEOUT},
    TASK_IMPLEMENTING: {TASK_SUBMITTED, TASK_BLOCKED, TASK_CANCELLED, TASK_TIMEOUT},
    TASK_SUBMITTED: {TASK_VERIFYING, TASK_CANCELLED},
    TASK_VERIFYING: {TASK_IN_REVIEW, TASK_REWORK, TASK_CANCELLED},
    TASK_IN_REVIEW: {TASK_APPROVED, TASK_REWORK, TASK_CANCELLED},
    TASK_REWORK: {TASK_SUBMITTED, TASK_CANCELLED, TASK_TIMEOUT},
    TASK_APPROVED: {TASK_DONE},
    TASK_BLOCKED: {TASK_IMPLEMENTING, TASK_CANCELLED},
}

# Handoff states (plan V2 §13.2)
HO_DRAFT = "draft"
HO_VALIDATED = "validated"
HO_OFFERED = "offered"
HO_ACCEPTED = "accepted"
HO_COMPLETED = "completed"
HO_EXPIRED = "expired"
HO_RETURNED = "returned_for_rework"
HO_CANCELLED = "cancelled"

HO_TERMINAL = {HO_COMPLETED, HO_EXPIRED, HO_RETURNED, HO_CANCELLED}

HO_TRANSITIONS = {
    HO_DRAFT: {HO_VALIDATED, HO_CANCELLED},
    HO_VALIDATED: {HO_OFFERED, HO_CANCELLED, HO_EXPIRED},
    HO_OFFERED: {HO_ACCEPTED, HO_EXPIRED, HO_CANCELLED},
    HO_ACCEPTED: {HO_COMPLETED, HO_RETURNED, HO_CANCELLED},
}


def check_transition(current: str, target: str, table: dict[str, set[str]], kind: str) -> None:
    allowed = table.get(current, set())
    if target not in allowed:
        raise IllegalTransition(f"illegal {kind} transition: {current} -> {target}")
