"""agent_system.lifecycle: canonical run/task/handoff state machine."""


class LifecycleError(Exception):
    """Base error for the agent-system lifecycle service."""


class IllegalTransition(LifecycleError):
    """A state transition outside the canonical tables was attempted."""
