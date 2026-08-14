"""agent_system.handoff: CAO-owned handoff projection (plan V2 §13.4).

The canonical handoff record lives in CAO's lifecycle database. For
consumers that still expect files under legacy handoff directories, CAO can
generate a bounded, sanitized Markdown projection — clearly marked
non-authoritative. No provider writes these files directly.
"""
