# R8 closeout and operational friction baseline — 2026-09-21

Status: **R8 architectural subtraction is complete enough to stop adding runtime recuts by default.**

This checkpoint follows:
- PR #330 — retire `journey_shadow`;
- PR #331 — retire direct public `agent.py begin`;
- PR #332 — consolidate hosted issue-bus I/O below protocol semantics;
- PR #333 — retire historical hosted second-close compatibility recovery;
- PR #334 — retire automatic close-recovery generation from public `agent close`.

The closeout decision is based on responsibility, not line count alone.

## Remaining runtime layers and why they still exist

The remaining core responsibilities are distinct:

- **Work / Continuation** — durable task progress and handoff.
- **Coordination** — ownership and lease authority.
- **Agent Cycle** — bounded execution identity and begin/close lifecycle.
- **Delivery** — governed integration/finalization.
- **Project Machine / sensors** — observation and derived operational state.
- **canonical close** — verifies durable delta and supplied evidence.
- **R6g BLOCKED-terminal reconciliation** — classifies strongly-bound write-lease BLOCKED failures as terminal non-mutation while keeping UNKNOWN fail-closed.
- **AgentCycleNonInterferenceReadback verification** — validates externally supplied read-only proof that unrelated authority drift did not touch the bound Work.

The last two originated during R6 but now have independently useful safety semantics. Their historical generators/retry orchestration have been removed.

## Remaining provider / CLI coupling inventory

No provider selection was found in the semantic `journey_entry` or turnover composition paths.

The remaining concrete `GhApiTransport` / CLI coupling is classified as an explicit environment edge:

| Surface | Remaining role | Classification |
| --- | --- | --- |
| `tools/agent.py` | live re-entry observation and Work continuation host execution | explicit public host edge |
| `tools/project_sensors.py` | live repository/Coordination/Continuation observation | explicit live-sensor edge |
| `tools/hosted_agent_cycle.py` | hosted workflow/CLI carrier | explicit host edge |
| `tools/hosted_agent_tool.py` | hosted Agent Tool execution | explicit host edge |
| `tools/hosted_agent_write_lease.py` | hosted write-lease execution | explicit host edge |
| `tools/agent_tools/dispatch_host.py` | provider-backed Agent Tool dispatch | explicit host edge |
| `tools/continuation_live.py` | live continuation CLI | explicit CLI edge |
| `tools/coordination_remote.py` | concrete `gh api` transport implementation | provider implementation |

These are not automatically R8 debt. Removing them is justified only if a real platform-native ToolSurface replaces at least one explicit environment role without moving provider selection back into semantics.

## No remaining migration-only productive path found

After PR #334:

- public `agent close` invokes canonical close directly;
- Hosted Agent Cycle has one productive close invocation;
- no recovery generator package remains;
- direct public `begin` remains retired;
- `journey_shadow` remains absent;
- hosted issue-bus carrier mechanics have one shared owner;
- no replacement Journey authority/state/session/workflow was introduced.

This satisfies the R8 stop condition more strongly than continuing to delete code solely because it originated during migration.

## Operational friction baseline

The architecture is no longer the dominant source of friction. The #334 recut required one semantic decision — retire the hidden recovery generator while preserving evidence verification — but executing that decision still required substantial tool-level mechanics.

Observed execution shape for the #334 recut:

- 1 branch creation;
- 6 sequential repository content mutations;
- per-file SHA/precondition handling for updates/deletions;
- explicit readback after destructive/significant writes;
- 1 PR creation;
- 3 exact-head CI gates;
- repeated workflow/job observation until completion;
- 1 expected-head guarded merge;
- repeated handling of technical identifiers: main SHA, branch ref, blob SHAs, PR number/head SHA and workflow run IDs.

Additional friction observed across R8 work:

- connector actions use similar but not fully uniform argument names such as `repository_full_name` vs `repo_full_name`;
- exact textual patches are brittle when imports or local structure differ from the inspected shape;
- one logical change spanning several files is still expressed as several low-level mutations;
- CAS/readback is valuable and should remain, but the agent currently coordinates much of that ceremony manually.

This is qualitatively different from the pre-R7/R8 problem. The agent now generally knows **what semantic action is correct**; the remaining cost is translating that action into multiple safe tool operations.

## Decision rule for a new tool

A new ToolSurface or capability is allowed. It should not be created merely because the current connector is verbose.

A new governed-mutation tool becomes justified when all are true:

1. the same observe -> plan -> mutate -> readback choreography recurs across multiple representative tasks;
2. the missing capability belongs to the execution edge, not Work/Coordination/Agent Cycle/Delivery semantics;
3. the tool introduces no authority, lifecycle or persistent state;
4. canonical CAS/preconditions/readback remain visible in the returned proof;
5. it materially reduces agent-facing administrative calls/identifiers;
6. it does not require generic multi-provider or multi-forge abstraction before a second real case exists.

A plausible future surface is a narrow governed repository mutation operation that accepts a semantic mutation set and internally performs plan construction, sequential CAS writes and aggregate readback. This is a hypothesis for discovery, not a committed design.

## Next phase

Do not open an R9 architecture program by default.

Run a short **operational ergonomics discovery** across representative work:
- one single-file edit;
- one multi-file refactor;
- one branch/PR/CI integration;
- one authority-bound mutation.

For each, record:
- semantic decisions required;
- administrative tool calls;
- technical identifiers manually propagated;
- readbacks;
- retries caused by plumbing rather than semantics.

If the same execution-edge gap dominates those samples, design the smallest tool/composition that removes it. If friction remains task-specific, keep the current architecture and improve locally rather than creating another permanent layer.


## Discovery result — live atomic Git-data experiment

The follow-up discovery confirmed the repository already contains the correct semantic capability and the connected GitHub ToolSurface already contains the required raw provider primitives.

Two coherent multi-path documentation mutations were executed through the Git Data API shape:

1. create a tree containing two new discovery documents, create one commit with the exact observed parent, publish the branch ref non-force, and read back exactly two changed paths;
2. update this closeout plus the migration status together as a second atomic tree/commit/ref mutation.

The first experiment produced one commit for two paths with exact parent/readback, instead of one Contents API commit per file. The second experiment exercises the same shape on updates to existing paths.

This strengthens the conclusion: the remaining gap is a **ToolSurface composition gap**. The repository already has `GitMutationPlan.mutate-files`, `GitMutationBundle`, canonical tree/readback verification, and governed Agent-owned Git execution.

Accordingly:

- do not create a second repository mutation module;
- do not generalize across providers/forges yet;
- a future ergonomic capability should expose the existing governed multi-path mutation as one host action;
- it should return canonical plan/bundle/readback proof rather than only a success boolean;
- PR/CI/merge remain outside this first ergonomic surface.

See:
- `post-r8-operational-ergonomics-discovery-2026-09-21.md`;
- `governed-multi-path-tool-surface-candidate-2026-09-21.md`.
