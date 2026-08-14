# Local Patch Inventory

Every modification to upstream files must be listed here. Additive local modules
under `src/cli_agent_orchestrator/agent_system/` are tracked in
`src/cli_agent_orchestrator/agent_system/README.md` instead.

| Upstream file | Local change | Reason | Upstreamable? |
|---|---|---|---|
| (none yet) | — | — | — |

## Additive local modules

| Module | Purpose |
|---|---|
| (none yet) | — |

## Rules

- No unattended upstream merges (see SYNC_RUNBOOK.md).
- Every modified upstream file gets a row above before the change lands.
- Local-only enforcement goes through stable service boundaries where possible;
  upstream files are modified only when enforcement cannot be added otherwise.
