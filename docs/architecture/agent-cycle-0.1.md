# Agent Cycle 0.1 — Entry and Close Protocol

Status: **M10 executable contract**.

## Problem

MobiliPresenter has deterministic tools for ProjectState, ProjectMachine, runtime capability discovery, Routine, Maintenance, Scheduler, Work, Coordination and Git mutation. Agent Cycle composes the recurring session protocol so correctness does not depend on a worker remembering an informal sequence.

Agent Cycle is not Routine and creates no authority or writer.

## Entry

The public facade is:

```bash
python3 tools/agent.py begin \
  --role <role> \
  --intent <declared-intent> \
  --machine-scope <local|base|live> \
  --json
```

Optional closed provider inputs are `--observations <RuntimeObservationBundle 0.1>` and `--runtime-providers <RuntimeProviderObservations 0.1>`.

The result is `AgentCycleContext 0.1`, always read-only, `semanticAuthority=false`, `authorizesMutation=false`. It binds semantic context, ProjectMachine, runtime capabilities, RoutineInspection, MaintenanceInspection, SchedulerPlan, AgentSemanticBrief and a baseline of source heads/artifact hashes.

Unavailable downstream derivations remain explicit `UNKNOWN` slots. No missing observation is silently rebuilt or promoted to PASS.

## Baseline integrity

The baseline is self-hashed and also bound back to the embedded ProjectMachine/runtime/semantic artifacts. Re-hashing a tampered baseline cannot make it valid if its facts no longer match those artifacts.

No open-cycle marker is persisted. The context is the immutable closure input; this avoids creating an accidental mutable cycle authority.

## Close

After work, close the preserved context:

```bash
python3 tools/agent.py close --context <agent-cycle-context.json> --json
```

Close reobserves the same ProjectMachine scope used at begin. Scope substitution fails closed. Live provider inputs may be supplied again explicitly.

The deterministic close pipeline is:

```text
preserved AgentCycleContext
-> reobserve after-state
-> AgentCycleDelta 0.1
-> validate supplied canonical mutation/readback evidence
-> AgentCycleAggregateReadback 0.1
-> AgentCycleReceipt 0.1
-> AgentCycleClosure 0.1
```

All outputs are projections: read-only, `semanticAuthority=false`, `authorizesMutation=false`.

## AgentCycleDelta 0.1

Delta separates:

- durable changes: ProjectState hash and source-head changes;
- derived changes: ProjectMachine/runtime/routine/maintenance/scheduler/semantic-brief hash changes;
- blocking unknowns added/resolved;
- before/after cycle status.

Delta observes effects; it never authorizes or attributes them by itself.

## Mutation evidence

Agent Cycle does not execute mutation. Mutation remains delegated to the existing domain writer or governed Git operation. Close accepts only evidence it can deterministically validate:

- `transition-receipt`: a `TransitionPlan 0.1` with its verified `TransitionReceipt 0.1`;
- `git-mutation-bundle-readback`: a `GitMutationBundle 0.1` with provider readback accepted by the canonical bundle verifier;
- `git-mutation-plan-readback`: a `GitMutationPlan 0.1` with an observed result matching the plan's readback contract.

Evidence is normalized and hash-bound in the receipt. Duplicate evidence is rejected.

## Aggregate readback and fail-closed coverage

Every durable delta is checked for attributable verified evidence. A source-head change is covered only by evidence tied to that branch/authority; a ProjectState content change requires a verified project-state transition.

If a durable change is not covered, the receipt is `UNKNOWN` with `UNATTRIBUTED_DURABLE_DELTA`. No evidence or missing evidence is never interpreted as success.

A no-durable-change cycle may close without mutation evidence. Derived-only drift remains recorded in Delta but does not fabricate a mutation obligation.

If the after context is `UNKNOWN`, close is `UNKNOWN`. If it is `BLOCKED`, close is `BLOCKED`.

## Compatibility

`AgentCycleContext 0.1` created by the earlier close foundation remains structurally valid. The validator distinguishes:

```text
AgentCycleCloseFoundation 0.1 -> implemented=false, nextSlice=M10-OS1C
AgentCycleCloseContract 0.1   -> implemented=true, nextSlice=null
```

This permits a preserved pre-close context to be closed after the executable protocol exists without rewriting history.

## Dimensional readiness

`AgentCycleContext 0.3` preserves the aggregate `status` consumed by existing
begin/hosted/close paths and adds the hash-bound `AgentCycleReadiness 0.1`
projection. It separates context integrity, intent readiness, tool readiness,
provider resolution and mutation authorization.

The projection is read-only and never authorizes mutation. In particular,
aggregate `READY` does not imply that a mutation tool, provider or exact
authorization is available. Provider resolution remains `UNKNOWN` until an
operation is unambiguous, and mutation authorization remains `UNKNOWN` until
the operation-specific policy and guards are evaluated.

Contexts 0.1 and 0.2 remain readable as supplied. Missing dimensional fields in
historical contexts are not synthesized or promoted to `PASS`; consumers that
require dimensional readiness must require context 0.3.

## Boundary

Agent Cycle owns orchestration of entry/reobservation/delta/receipt only. It does not replace ProjectState, Work, Coordination, Scheduler, Capability Lifecycle, GitMutationPlan or GitMutationBundle writers/planners.

Provider transport is not authority. Discovery is not authorization. `UNKNOWN != PASS`.

## M10 closure condition

M10 may close only when:

- `agent begin` composes the deterministic entry context;
- `agent close` reobserves the same scope and emits deterministic Delta/Receipt/Closure;
- required capabilities cannot silently disappear;
- stale/tampered semantic briefs remain distinguishable;
- baseline tampering cannot be repaired by re-hashing alone;
- unattributed durable changes fail closed;
- mutation evidence is delegated to and validated against existing canonical contracts;
- full Agent Ops, semantic contracts, OperationalSemantics coverage and roadmap freshness gates pass;
- no new authority or canonical writer is introduced.
