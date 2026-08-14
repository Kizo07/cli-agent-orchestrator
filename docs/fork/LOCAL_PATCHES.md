# Local Patch Inventory

Every modification to upstream files must be listed here. Additive local modules
under `src/cli_agent_orchestrator/agent_system/` are tracked in
`src/cli_agent_orchestrator/agent_system/README.md` instead.

| Upstream file | Local change | Reason | Upstreamable? |
|---|---|---|---|
| `src/cli_agent_orchestrator/api/main.py` | `main()`: loopback-binding guard + `install_control_auth(app)`; `terminal_ws`: control-token handshake check | Plan V2 17.2: authenticated control plane, no unauthenticated PTY, no accidental remote binding | Partially (env-gated, default behavior unchanged) |
| `src/cli_agent_orchestrator/providers/antigravity_cli.py` | `--dangerously-skip-permissions` gated by `CAO_STRICT_PERMISSIONS`/`CAO_AGY_SKIP_PERMISSIONS` | Plan V2 17.3: no unconditional permission bypass | Yes |
| `src/cli_agent_orchestrator/providers/hermes.py` | `--yolo` gated by `CAO_STRICT_PERMISSIONS`/`CAO_HERMES_YOLO` | Plan V2 17.3 | Yes |
| `src/cli_agent_orchestrator/providers/codex.py` | wildcard-tool yolo inference gated by `CAO_STRICT_PERMISSIONS`/`CAO_CODEX_YOLO` | Plan V2 17.3 | Yes |

## Additive local modules

| Module | Purpose |
|---|---|
| `src/cli_agent_orchestrator/agent_system/security/control_auth.py` | CAO_CONTROL_TOKEN middleware, WS token check, loopback binding guard |
| `src/cli_agent_orchestrator/agent_system/security/launch_guard.py` | explicit provider permission modes (strict opt-in bypasses) |
| `src/cli_agent_orchestrator/agent_system/provenance.py` | fork provenance reporting (plan V2 8.4) |
| `scripts/stamp-provenance.py` | release provenance stamping with dirty-build refusal |
| `test/agent_system/test_security.py` | hardening unit tests |

## Rules

- No unattended upstream merges (see SYNC_RUNBOOK.md).
- Every modified upstream file gets a row above before the change lands.
- Local-only enforcement goes through stable service boundaries where possible;
  upstream files are modified only when enforcement cannot be added otherwise.
