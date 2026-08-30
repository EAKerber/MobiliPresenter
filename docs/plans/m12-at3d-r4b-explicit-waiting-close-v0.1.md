# M12-AT3D-R4B — Explicit WAITING Close 0.1

Status: implementation slice R4B  
Baseline: `main@9ea8fa6f134b923f82a3fdfb5bb461e97ca35436`  
ProjectState transition: `implement-m12-at3d-r4b-explicit-waiting-close-v0.1`

## Purpose

Replace the Hosted Agent Cycle paved path's short polling loop with one explicit
observation and a truthful non-terminal `WAITING` result when a sealed cycle is
only missing a correlated terminal observation.

R4A already separated the stable request seal from the current result-observation
horizon. R4B uses that property; it does not introduce another seal, cursor, job,
retry authority, scheduler or persistent session state.

## Paved-path behavior

The productive close carrier performs one observation only:

```text
close(handle)
  -> observe sealed cycle once
     -> terminal + clean     => PASS
     -> observational gap    => WAITING
     -> structural/authority => BLOCKED/UNKNOWN through existing failure path
```

`WAITING` means only that observation retry is safe. It never means that replaying
the underlying operation is safe or required.

The result therefore declares:

- `observationRetry = SAFE`;
- `operationReplay = NOT_APPLICABLE`;
- `semanticAuthority = false`;
- `authorizesMutation = false`.

There is no automatic wake-up. A later `close(handle)` is a fresh observation of
the same cycle. R4A keeps the request frontier sealed while allowing correlated
late results to become visible at the later observation horizon.

## Ownership and surface boundary

`tools/hosted_agent_cycle.py` remains the **only productive Hosted Agent Cycle CLI**.
R4B does not add a second cycle entrypoint or semantic component.

`tools/hosted_agent_cycle_waiting.py` is an internal projection helper. It has no
`argparse` surface and no `__main__` entrypoint. The workflow still invokes
`python tools/hosted_agent_cycle.py close`; only after that canonical close has
materialized a validated failure can the workflow ask the internal helper whether
the result is an evidence-backed observational WAITING case.

This keeps trace and write-lifecycle judgment inside the existing Hosted Agent Cycle
component and avoids a parallel authority, registry component or execution surface.

## Classification boundary

R4B promotes only evidence-backed observational gaps.

Recognized waiting targets are closed vocabulary:

- `AGENT_TOOL_RESULT`;
- `REMOTE_CANONICAL_RESULT`;
- `AGENT_WRITE_LEASE_RESULT`.

Trace incompleteness is re-derived from the exact cycle record view; the helper does
not infer a target from error text alone. Write-lifecycle WAITING requires the
validated close report to say a lifecycle request exists without its terminal
result. Receipt mismatch, duplicate/orphan records, active or expired leases,
authority mismatch, malformed identity and other structural failures remain on the
existing failure path.

## Single-observation enforcement

The existing trace helper remains capable of explicit multi-observation
characterization when a caller supplies `attempts > 1`, but its productive default
is changed from three observations to **one**:

- `TRACE_STABILIZATION_ATTEMPTS = 1`;
- `prepare_close_stabilized(... attempts=1)` by default;
- the write-lifecycle close loop reuses the same constant and therefore also runs
  once by default.

No `sleep()` is reachable on that default path because there is no second attempt.
Tests that intentionally characterize delayed transport may continue to request two
or more observations explicitly. No runtime monkey-patch or persistent global policy
is needed.

## Carrier result

`HostedAgentCycleCloseWaiting 0.1` is a transport-local, hash-bound result envelope.
It is not an authority or persistent domain state. Its `sourceFailureHash` binds it
to the validated failure that was promoted after observational classification.

A WAITING close remains non-terminal, so no terminal close proof is uploaded. The
workflow posts the compact WAITING result and its final operational-result gate
accepts the validated envelope. Structural BLOCKED/UNKNOWN results still fail that
gate.

## Non-goals

R4B does not add:

- automatic retry or notification;
- queue/cursor/wake-up state;
- operation replay;
- Work or Coordination mutation;
- sequence numbers or dependency ordering;
- workflow concurrency groups;
- provider selection;
- obligation enforcement in canonical close;
- productive Work Mode provider bridge;
- compatibility retirement.

Sequence/dependency and cross-carrier concurrency remain later R4 work. R5 remains
downstream of that broader async-safety work.

## Qualification

Repository qualification must prove:

1. unit tests cover exact WAITING promotion and structural non-promotion;
2. the productive stabilization default is exactly one observation;
3. explicit characterization can still request multiple observations;
4. Hosted workflow still delegates close to the canonical cycle CLI and does not
   acquire a parallel semantic component;
5. existing Agent Ops, Semantic Contracts, OperationalSemantics, Doctor,
   Coordination Guard and Supervisor Snapshot remain green;
6. Hosted qualification produces `WAITING` on a first close with a pre-seal request
   whose terminal result is absent at that observation;
7. after the correlated result arrives, a later close of the same handle produces
   `PASS` without a new begin or operation replay;
8. no post-seal request is admitted into that retry.

## Exit criterion

R4B is complete when the paved path can truthfully demonstrate:

> Close never polls for eventual consistency. One observation either closes the
> sealed cycle, reports an explicit safe-to-reobserve WAITING state, or fails closed;
> a later retry may consume correlated late results without replaying the operation
> or expanding the request set.

ProjectState is not advanced as an implementation side effect. Successor selection
is reconciled separately after repository and Hosted qualification evidence are
complete.
