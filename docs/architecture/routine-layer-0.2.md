# MobiliPresenter — Routine Layer 0.2

Status: pipeline adoption contract for M9-0B2.

## Purpose

Routine Layer turns recurring operational obligations into deterministic read-only tooling. A worker should not need to remember each recurring check in its prompt or reasoning. The canonical pipeline materializes one `RoutineInspection 0.1` from an already materialized `ProjectMachineInspection` and passes that exact artifact downstream.

```text
ProjectMachineInspection
        ↓
RoutineInspection 0.1
        ↓
MaintenanceInspection 0.6
        ↓
SchedulerPlan 0.2
        ↓
SchedulerSnapshot 0.3
```

## Boundaries

- Routine is not a Scheduled Task. Scheduled Tasks wake a worker; routines are checks executed inside an operational cycle.
- Routine is not an authority and has no writer or mutable state.
- Routine is not Maintenance. It reports recurring facts/findings and never emits `OperationalAction`.
- Routine is not Scheduler. It never chooses routing, transport or wake targets.
- Routine is not Capability. A capability may be monitored by a routine, but the routine cannot promote, mutate or authorize it.
- Routine does not reobserve authorities. Its input is the closed `ProjectMachineInspection` supplied by the caller.

## Canonical input lineage

`MaintenanceInspection 0.6` has two required canonical inputs:

1. one validated `ProjectMachineInspection`;
2. one validated `RoutineInspection 0.1` deterministically derived from that same ProjectMachine.

Maintenance persists both hashes:

- `projectMachineInspectionHash`;
- `routineInspectionHash`.

The CLI path using `--input` therefore also requires `--routines`. Convenience local/base/live modes may derive ProjectMachine and RoutineInspection sequentially inside the same invocation, but canonical workflows materialize both artifacts explicitly.

## Interpretation boundary

Routine findings are factual/policy-obligation observations. They contain no action. Maintenance owns the translation from a supervisor-eligible routine finding into the existing `OperationalAction` vocabulary.

For the initial `capability-deathcircle` routine, the behavior-preserving mapping is:

| Routine finding | Maintenance action |
| --- | --- |
| `CAPABILITY_GATES_DUE` | `CONTINUE` |
| `CAPABILITY_EMPTY_REVIEW_DUE` | `CONTINUE` |
| `CAPABILITY_EMPTY_LIMIT` | `NEEDS_HUMAN` |

A finding with `supervisorEligible=false` remains visible in RoutineInspection but cannot become a Maintenance action. This preserves isolated capability semantics.

An unknown supervisor-eligible finding code fails closed rather than being silently ignored.

## Routine health semantics

A valid RoutineInspection can itself report incomplete evaluation:

- aggregate `UNKNOWN` produces a `ROUTINE_INSPECTION_INCOMPLETE` Maintenance finding;
- aggregate `FAIL` produces a `ROUTINE_INSPECTION_FAILED` Maintenance finding.

An invalid, tampered, stale, wrong-machine or non-derivable RoutineInspection prevents Maintenance materialization entirely.

Therefore missing execution never becomes the semantic equivalent of an empty routine result.

## Capability Death-Circle migration

M9-0B1 ran `capability-deathcircle` in shadow while Maintenance retained its historical `_capability_findings()` implementation.

M9-0B2 removes that duplicate path. Maintenance no longer reads the capability sensor to reconstruct death-circle policy. The only recurring capability findings used by Maintenance arrive through the validated RoutineInspection.

The Capability authority, lifecycle planner and writer remain unchanged.

## Scheduler boundary

`SchedulerPlan 0.2` remains unchanged. It consumes a validated MaintenanceInspection and routes its selected `OperationalAction`. Scheduler has no knowledge of routine identifiers or routine finding codes.

This keeps recurring-check semantics upstream of routing.

## Supervisor Snapshot lineage

`SchedulerSnapshot 0.3` closes the complete derivation chain. Build and validate require the same `RoutineInspection 0.1` used by Maintenance. The snapshot stores `routineInspectionHash`, and the Supervisor artifact carries `routine-inspection.json` alongside the existing source/readback ProjectMachines, MaintenanceInspection and SchedulerPlan.

Validation proves:

```text
ProjectMachine source
  → exact RoutineInspection derivation
  → exact Maintenance derivation(machine, routine)
  → exact SchedulerPlan derivation(maintenance)
  → snapshot hashes/source heads
  → ProjectMachine readback freshness
```

Consumer-time current-head checks remain unchanged for control, Coordination and Work authorities.

## Determinism and coverage

RoutineInspection continues to own catalog coverage (`required`, `evaluated`, `missing`) and deterministic hashing. M9-0B2 does not introduce another routine, cadence authority or mutable routine state.

Expansion to Work lifecycle and Branch Hygiene review is intentionally deferred until this pipeline adoption is proven in CI and Supervisor artifacts.

## Retirement rule

After M9-0B2, adding a recurring operational obligation must not add a parallel check directly to Maintenance merely because that is convenient. It should first be modeled as a routine when the concern is genuinely recurring and read-only; Maintenance may then translate its supervisor-eligible findings into operational policy.
