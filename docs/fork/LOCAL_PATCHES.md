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
| `src/cli_agent_orchestrator/agent_system/state_dir.py` | CAO_HOME_DIR state-dir resolution outside the AWS tree (plan V2 12.1) |
| `src/cli_agent_orchestrator/agent_system/policy/bundle.py` | versioned, hashed AgentSystem policy bundles (plan V2 9.4) |
| `src/cli_agent_orchestrator/agent_system/policy/routes.py` + `model_routes.yaml` | qwen-default alias via OpenCode Token Plan; qwen_cli excluded (plan V2 10.2/10.3) |
| `src/cli_agent_orchestrator/agent_system/lifecycle/` | canonical run/task/handoff state machine, completion gates, reviewer independence, crash reconciliation, usage lifecycle (plan V2 13/16/6.3) |
| `src/cli_agent_orchestrator/agent_system/scorecard/` | rubric port, evaluation lifecycle, lossless legacy migration (plan V2 14) |
| `src/cli_agent_orchestrator/agent_system/memory/` | hardened memory gate: scanning, scope binding, approval, dedup/contradiction, tombstones, least-privilege recall (plan V2 12) |
| `src/cli_agent_orchestrator/agent_system/backup.py` | owner-only state backup with manifest verification (plan V2 12.6) |
| `scripts/stamp-provenance.py` | release provenance stamping with dirty-build refusal |
| `test/agent_system/` | hardening, lifecycle, routes, scorecard, memory-gate tests |

## Rules

- No unattended upstream merges (see SYNC_RUNBOOK.md).
- Every modified upstream file gets a row above before the change lands.
- Local-only enforcement goes through stable service boundaries where possible;
  upstream files are modified only when enforcement cannot be added otherwise.
