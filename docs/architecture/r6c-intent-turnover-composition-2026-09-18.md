# R6c — Agent Cycle intent-turnover composition

Status: **integrated via PR #317. R6d follows up only on provider-host execution handoff; R6c semantics remain unchanged.**

## Problem discovered by R6Q

Exact-head qualification for PR #315 exposed a legitimate Work transition across Agent Cycle intents. The active Work remained the same, but a `governed-mutation` cycle reached a point where `ci.workflow.rerun` was admissible only under `inspect-and-plan`. `AgentCycleReadiness 0.2` correctly projected `SELECT_INTENT`; the remaining operational burden was manual lifecycle choreography:

`release ownership -> close current cycle -> begin successor cycle for the same Work`.

That choreography is administrative knowledge the paved path is intended to absorb.

## Scope

R6c adds a stateless turnover composer. It does **not** make `declaredIntent` mutable in place and does not add a Journey/turnover authority, session, store, workflow, marker or lifecycle.

The composer consumes already-observed facts:

- current Work identity;
- current Agent Cycle intent when a cycle is active;
- `AgentCycleReadiness.nextSafeAction`;
- canonical Hosted cycle re-entry disposition;
- current Agent Write Lease lifecycle classification.

It derives exactly one next primitive:

- `SELECT_INTENT` when semantic choice remains ambiguous;
- `RELEASE_OWNERSHIP` while the old cycle still owns or must reconcile a write binding;
- `CLOSE_AGENT_CYCLE` once the write lifecycle is clean;
- `BEGIN_AGENT_CYCLE` after the previous cycle is terminal;
- `BLOCKED` / `NO_TURNOVER` otherwise.

Execution is deliberately one-primitive-at-a-time through injected existing adapters. After any submission, authorities must be re-observed before another step. This makes interruption between release, close and begin an ordinary re-entry case rather than a new durable state machine.

PR #317 proved this semantic composition and integrated it. R6d does not change the turnover state model; it formalizes the handoff from an already-derived primitive to the configured host/provider surface so Work-mode execution does not depend on the explicit CLI carrier.

## Boundary

The turnover projection carries no issue number, comment ID, lease ID, binding hash, cycle instance ID or protocol version. Those remain internal to the primitive owners and host adapters.

The core does not choose among multiple candidate intents. A unique readiness candidate may be derived automatically; otherwise the semantic caller/host must choose one of the readiness candidates. After that choice, repeated invocations may carry the chosen target intent across an interruption without persisting turnover state.

## Host integration

R6c must reuse the existing primitive owners:

- ownership lifecycle: existing Agent Write Lease / Coordination path;
- close: existing handle-first Hosted Agent Cycle close;
- begin: existing Journey entry / Hosted Agent Cycle begin composition.

Do not add a second issue-bus client merely to make R6c executable. Where repository-local code cannot materialize a host observation without violating the provider boundary, the hosting control plane should inject the observation/adapter.

The public semantic target remains equivalent to:

`continue Work according to its next admissible intent`

rather than exposing lease/binding/comment/cycle mechanics.

## Re-entry requirements

The implementation must remain safe at each interruption boundary:

1. before release: active/expired ownership yields release/reconciliation;
2. after release but before close: re-observation yields close;
3. after close but before successor begin: re-entry yields `BEGIN_NEW_CYCLE`, then begin;
4. after successor begin: lineage/re-entry must reuse the new cycle rather than create a third one.

UNKNOWN lifecycle or ambiguous intent remains fail-closed.

## Promotion and death condition

R6c is migration scaffolding until repeated use proves otherwise.

Keep it only if independent Works naturally require the same pattern of one Work traversing semantically distinct Agent Cycle intents (for example implementation -> qualification or recovery -> inspection). If R6/R7 evidence shows the pattern was unique to the migration state, R8 should delete/demote the turnover composer and retain only bounded recovery choreography.

Promotion never permits a mutable-intent Agent Cycle or a new turnover authority.
