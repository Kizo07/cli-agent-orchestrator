"""agent_system.memory: hardened canonical shared memory (plan V2 §12).

CAO memory is the only canonical shared-memory service. Writes go through
HardenedMemoryGate: validation, scanning, scope binding, dedup/contradiction,
approval gates, audit, tombstones. Reads are least-privilege per role.
"""
