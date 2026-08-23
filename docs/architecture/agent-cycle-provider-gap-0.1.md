# Agent Cycle Provider Gap 0.1 — Degraded Boundary

Status: **formalized gap boundary; not an Agent Cycle implementation**.

## Problem

`Agent Cycle 0.1` is currently materialized through the repository CLI (`python3 tools/agent.py begin|close`) and a checkout/runtime able to execute the repository tooling. Provider equivalence elsewhere in the operational stack does **not** make an ad hoc sequence of remote GitHub calls equivalent to `AgentCycleContext 0.1`, `AgentCycleReceipt 0.1`, or `AgentCycleClosure 0.1`.

The concrete M12 case exposed the boundary: a connected GitHub provider could observe and mutate the authorized repository while the local conversation runtime could not reach GitHub, so `agent.py begin/close` could not be materialized there. Operation-level Git governance could still be followed, but the session could not truthfully claim Agent Cycle conformance.

## Classification

When the repository Agent Cycle cannot be materialized because its execution carrier is unavailable, classify the cycle as:

```text
AGENT_CYCLE_UNMATERIALIZED_PROVIDER_GAP
cycleConformance = UNKNOWN
```

`UNKNOWN != PASS`.

This classification is evidence about the cycle boundary. It is not an authorization to bypass the cycle, a new authority, or a replacement writer.

## What may still proceed

A separately authorized operation may proceed only when **its own canonical contract** can be materialized end-to-end through an equivalent provider:

```text
observe
-> canonical plan
-> validate exact scope + expected heads
-> canonical apply
-> independent readback
-> verifiable operation receipt
```

The alternate carrier must preserve every invariant required by the operation. A remote transport acknowledgement is not readback, and provider availability does not create semantic or operational authority.

`Remote Canonical Execution 0.1` is such an operation-level path. It does not retroactively create an Agent Cycle begin context or close receipt.

## Forbidden compensations

A provider gap must never be hidden by fabricating or backdating:

- a `WorkItem` that did not exist;
- a Coordination intent or lease that did not exist;
- an `AgentCycleContext` or close artifact that was not produced by the canonical cycle;
- a synthetic begin/close narrative;
- PR/CI state presented as if it were an Agent Cycle receipt;
- a provider transcript promoted to authority.

Historical evidence remains historical evidence. It is not rewritten to make the process appear more complete than it was.

## Minimum evidence when an operation proceeds under the gap

Record enough evidence to audit the operation independently of the missing cycle:

1. repository identity;
2. exact observed source/authority heads;
3. exact target branch, paths, or managed authority;
4. canonical plan identity (`planHash`/equivalent contract identity);
5. provider/carrier used for apply;
6. exact apply result;
7. independent readback bound to the plan;
8. PR/CI evidence when integration is part of the operation;
9. final `main` readback when `main` changes;
10. explicit `AGENT_CYCLE_UNMATERIALIZED_PROVIDER_GAP` classification.

This evidence can prove the operation. It cannot upgrade `cycleConformance` from `UNKNOWN` to `PASS`.

## Relationship to M12-RP1B

RP1B addresses the **remote mutation/provider gap** by hosting canonical planning and execution in repository-controlled tooling and using GitHub as carrier. It preserves existing domain writers and admits the governed direct-Git path only where no domain writer exists.

RP1B does **not** implement a hosted provider-neutral Agent Cycle. The issue/workflow transport is not an Agent Cycle authority and does not own begin/close semantics.

## Consequence for S2

A Scheduled Task environment can claim full Agent Cycle conformance only if it can either:

- run the canonical `agent.py begin/close` path; or
- invoke a future hosted Agent Cycle adapter that produces the same canonical context, baseline, close evidence, aggregate readback, receipt, and `UNKNOWN/BLOCKED` semantics.

If neither path is available, S2 may still run a deliberately scoped remote-execution experiment, but its cycle conformance remains `UNKNOWN`; it must not be reported as a full Agent Cycle PASS.

This distinction must be reviewed before the S2 scheduled test is launched.

## Death condition

Retire this degraded-boundary document when a canonical hosted/provider-neutral Agent Cycle adapter exists and proves all of the following:

- the same closed entry context and scope semantics as `agent begin`;
- the same baseline integrity guarantees;
- the same close re-observation and evidence validation;
- the same aggregate readback and closure contracts;
- the same fail-closed `UNKNOWN/BLOCKED` behavior;
- OperationalSemantics registration and CI coverage;
- no new mutable cycle authority.
