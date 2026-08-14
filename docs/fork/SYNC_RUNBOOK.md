# Upstream Sync Runbook

Repeatable procedure for importing upstream CAO releases into this fork.
No unattended merges — every sync ends in a reviewed report.

1. `git fetch upstream --tags`
2. Verify the upstream release/tag; record its commit hash.
3. `git checkout -b sync/upstream-vX.Y.Z main`
4. Merge the selected release tag or cherry-pick narrowly scoped fixes:
   `git merge vX.Y.Z` (or `git cherry-pick <sha>...`)
5. Review changes to: `providers/`, permissions/security, control planes (`api/`,
   `ops_mcp_server/`), `services/memory_service.py`, database migrations
   (`clients/database.py`), `plugins/`, dependency pins (`pyproject.toml`,
   `uv.lock`).
6. Run full suites: unit, integration, migration, security, provider canaries
   (`make test` equivalent + AgentSystem canary list in INTEGRATION_PLAN_V2.md §19
   Phase 10).
7. Compare `docs/fork/LOCAL_PATCHES.md` for dropped or duplicated changes;
   re-apply local patches that upstream did not absorb.
8. Write `docs/fork/reports/sync-vX.Y.Z.md` (diff summary, security review,
   test results, dropped/duplicated patch analysis).
9. Merge the sync branch into `main` only after the report is reviewed.
10. Tag a local release `agent-system-vN.M.P`, update
    `docs/fork/build-provenance.json`, and pin deployments to the new commit.

## Emergency fixes

Cherry-pick narrowly from upstream or patch locally; record in LOCAL_PATCHES.md
immediately; a full sync report is still required at the next release import.
