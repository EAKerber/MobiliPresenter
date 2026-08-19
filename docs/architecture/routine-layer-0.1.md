# Routine Layer 0.1 — Shadow Kernel

Status: architecture contract for M9-0B1. The Routine Layer is read-only and shadow-only in this increment.

## Purpose

A Routine is a deterministic recurring obligation to evaluate an operational condition. It exists so workers do not depend on conversational memory or prompt checklists to remember lifecycle checks such as death-circle detection.

The first canonical routine is `capability-deathcircle`.

## Boundaries

Routine is not a Scheduled Task. Scheduled Tasks wake a worker; routines are evaluated inside an operational cycle.

Routine is not Scheduler. A routine never emits `OperationalAction` and never selects routing.

Routine is not Maintenance. Routine emits neutral findings; Maintenance owns operational interpretation.

Routine is not Capability. A capability describes supported behavior and lifecycle policy; a routine is an obligation to inspect a condition.

Routine is not an authority. `RoutineInspection 0.1` is a derived artifact and never becomes a writer or source of mutable truth.

## Pipeline in M9-0B1

```text
ProjectMachineInspection
        |
        +--> RoutineInspection 0.1 (shadow)
        |
        +--> MaintenanceInspection --> SchedulerPlan
```

Maintenance and Scheduler remain unchanged. The shadow output is generated and validated in Agent Ops and Supervisor Snapshot, but it is not consumed by SchedulerSnapshot lineage in this increment.

## Routine catalog and coverage

The canonical catalog lives in tooling. Required routines must be discoverable from one catalog; the runner derives `required`, `evaluated`, and `missing` coverage from that catalog and its results.

A required routine that is not evaluated is never a healthy no-op. Coverage becomes incomplete and the inspection is not PASS.

`applicable=false` is different: the routine was evaluated successfully and established that no current subject requires a finding.

No cadence state is introduced in 0.1. Cheap required routines run on every operational cycle that materializes the shadow inspection.

## Capability death-circle routine

The routine consumes only the capability sensor already embedded in the supplied ProjectMachineInspection. It does not reread `ops/capabilities`.

It reuses the current `CapabilityReviewPlan` projection carried by the sensor:

- `TEST_NEXT_GATES` -> `CAPABILITY_GATES_DUE`
- `REVIEW_EMPTY_ROUND` -> `CAPABILITY_EMPTY_REVIEW_DUE`
- `REVIEW_EMPTY_LIMIT` -> `CAPABILITY_EMPTY_LIMIT`

It never increments `roundsWithoutActiveGates` and never mutates Capability state.

Capabilities with `supervisorParticipation=isolated` are still monitored. Their findings are marked `supervisorEligible=false`; shadow equivalence compares only supervisor-eligible findings with the legacy Maintenance projection.

## Determinism

`RoutineInspection 0.1` contains no timestamps or runtime identity. The same validated ProjectMachineInspection and same routine catalog produce the same inspection and hash.

Routine failures are explicit. If an evaluator throws, the runner materializes a FAIL result with `ROUTINE_EVALUATION_FAILED`; it never silently omits the routine.

## Shadow exit criteria

M9-0B1 is complete when:

1. the required catalog is evaluated automatically in both Agent Ops and Supervisor Snapshot;
2. coverage failure is explicit;
3. Capability Death Circle is detected from fixtures without prompt memory;
4. current canonical capabilities produce a healthy no-op;
5. active routine findings are equivalent to the legacy Maintenance capability findings;
6. isolated capability findings remain monitored but do not become Supervisor input;
7. Maintenance, Scheduler and SchedulerSnapshot behavior remain unchanged.

Only a later increment may insert RoutineInspection into the Maintenance input contract.
