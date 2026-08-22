# Agent Cycle 0.1 — Entry Protocol and Closure Foundation

Status: **M10-OS1B implementation contract**.

## Problem

MobiliPresenter already has deterministic tools for ProjectState, ProjectMachine, runtime capability inspection, Routines, Maintenance, Scheduler, Work, Coordination and Git mutation. Before this slice, a worker still had to remember the bootstrap sequence and manually compose those artifacts.

That is a protocol-memory failure mode: the system can have correct tools while a worker omits one.

Agent Cycle moves the recurring execution protocol from model memory into deterministic tooling.

## Boundary

Agent Cycle is **not** Routine.

`RoutineInspection 0.1` remains a recurring read-only obligation evaluated over one materialized ProjectMachine. Agent Cycle is the outer session protocol that composes existing projections for a worker execution.

Agent Cycle creates no authority and no canonical writer in OS1B.

## Entry

The public facade is:

```bash
python3 tools/agent.py begin \
  --role <role> \
  --intent <declared-intent> \
  --machine-scope <local|base|live> \
  --json
```

Optional closed provider inputs:

```text
--observations <RuntimeObservationBundle 0.1>
--runtime-providers <RuntimeProviderObservations 0.1>
```

`agent begin` does not silently substitute one observation scope/provider for another.

The result is `AgentCycleContext 0.1`.

Downstream projections that cannot be derived from the selected observation scope
remain explicit artifact slots with `status=UNKNOWN`, `value=null` and a stable
`reasonCode`. A missing local branch-backed authority therefore degrades the
cycle context instead of aborting the entire bootstrap or being silently rebuilt.

## AgentCycleContext 0.1

The context binds:

- role + DeclaredIntent entry profile;
- ProjectMachine inspection;
- RuntimeCapabilityInspection;
- RoutineInspection;
- MaintenanceInspection;
- SchedulerPlan;
- AgentSemanticBrief;
- source-head/project hashes in an immutable baseline;
- explicit blockers/unknowns;
- close requirement metadata.

It is always:

```text
readOnly = true
semanticAuthority = false
authorizesMutation = false
```

The `cycleId` is derived from the baseline hash. Equal normalized evidence produces the same cycle identity; the id is not a lease, assignment or authority.

## Entry profiles

OS1B intentionally avoids heuristic classification of arbitrary task prose.

A closed `(role, DeclaredIntent)` entry profile supplies the lifecycle phase, objects, operations and read scopes used by the semantic projection. Profiles cover the current bootstrap/inspect cases. Intents without a closed profile fail with `AGENT_CYCLE_ENTRY_PROFILE_REQUIRED`.

Mutation profiles are intentionally absent in OS1B. Discovery does not authorize mutation.

## CapabilityRelevanceProjection

Selection uses typed OperationalSemantics facets:

```text
role
+ DeclaredIntent
+ lifecycle phase
+ object intersection
+ operation intersection
```

Required capabilities come from an explicit SemanticFoundations policy, never from the mere presence of an intent facet.

Required capabilities are force-visible when role/intent/lifecycle match even if the task object filter would otherwise omit them.

Availability rules:

- `repository-static`: available only with complete current OperationalSemantics coverage;
- `runtime-observed`: uses only `RuntimeCapabilityInspection 0.1`;
- `contextual`: remains conditional;
- missing scope: unavailable;
- unresolved precondition: conditional.

A provider failure never removes the logical capability.

## AgentSemanticBrief 0.1

The brief is bound to:

- normalized context hash;
- OperationalSemantics hash;
- OperationalSemanticsCoverage inspection hash;
- EcosystemMaxims catalog hash;
- RuntimeCapabilityInspection hash;
- current role pointer and target document content hashes.

The brief contains no more than three maxims. Maxim selection is deterministic and cannot change capability eligibility or availability.

## Freshness

`CAPABILITY_DISCOVERY_FRESHNESS_GUARD` distinguishes:

- `FRESH`: current inputs reproduce the brief;
- `STALE`: one or more bound inputs changed;
- `TAMPERED`: self-hash/derivation no longer matches.

A stale brief is informative only and cannot prove capability availability.

## Baseline and monitoring boundary

OS1B does **not** persist an open-cycle marker. Persisting such a marker before ownership/writer semantics are closed could accidentally create another mutable state source.

Instead, the AgentCycleContext embeds a hash-bound baseline containing the source heads and key artifact hashes observed at begin time.

M10-OS1C will consume that baseline to reobserve the after-state and derive an `AgentCycleDelta`.

The monitor should track durable effects/evidence, not attempt to spy on every tool invocation.

## Closure foundation

Every context declares:

```text
CLOSE_REQUIRED_AFTER_WORK
```

and lists the future closure evidence:

1. baseline;
2. after-state reobservation;
3. deterministic before/after delta;
4. any required mutations delegated to existing canonical writers;
5. aggregate readback;
6. AgentCycleReceipt.

OS1B deliberately leaves `closeRequirements.implemented=false`.

M10-OS1C owns the executable close protocol.

## No new authority

AgentCycleContext, AgentSemanticBrief, CapabilityRelevanceProjection, RuntimeCapabilityInspection, RoutineInspection, MaintenanceInspection and SchedulerPlan remain projections.

The sources of truth continue to be the authorities already declared by OperationalSemantics.

## Exit condition for OS1B

OS1B is ready to integrate when:

- one `agent begin` composes the current entry context;
- required capabilities cannot disappear silently;
- stale/tampered briefs are distinguishable;
- bootstrap role docs point to the single entry facade;
- full tests, semantic contracts and OperationalSemantics coverage pass;
- no new authority/writer was introduced;
- M10 remains open for OS1C.
