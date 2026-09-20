# R8 — retire Journey shadow measurement scaffolding

Status: **candidate**.

## Purpose

R2 introduced `tools/agent_tools/journey_shadow.py` only to compare the emerging Journey projection against independently observed manual entry/re-entry behavior before promotion.

That measurement purpose is complete:

- R6 produced a fresh positive + negative provider-backed live black-box proof in PR #328;
- R7 changed the operational default and demoted direct Agent Cycle `begin` from the advertised normal Work-bound surface in PR #329.

Keeping the shadow after those gates would preserve migration scaffolding after its death condition had already been satisfied.

## Subtraction

This recut deletes, with no replacement:

- `tools/agent_tools/journey_shadow.py`;
- `tools/tests/test_agent_journey_shadow.py`.

No new runtime module, authority, lifecycle, state, workflow, provider bridge, compatibility layer or alternate projection is added.

## Why deletion is safe

`journey_shadow` is explicitly non-authoritative measurement code. Its module-level contract states that it never executes the projected action and existed to qualify R2 equivalence before later paved-path promotion.

Current normal operation already uses the promoted Journey projection, semantic Work-bound entry and canonical Agent Cycle/Coordination/Delivery primitives. The R6/R7 evidence therefore supersedes the pre-promotion comparison scaffolding rather than depending on it.

Exact-head CI is the final consumer check: any hidden import or contract dependency must fail qualification rather than trigger restoration of the shadow module.

## Migration accounting

- runtime modules added: **0**;
- runtime modules deleted: **1**;
- dedicated migration-only test modules deleted: **1**;
- new public API: **0**;
- new authority/lifecycle/provider surface: **0**;
- replacement compatibility code: **0**;
- net migration scaffolding: **decreased**.

## Qualification gate

Integration requires exact-head PASS from:

1. Agent Ops;
2. Coordination Guard;
3. Supervisor Snapshot.

A failure caused by a genuine remaining consumer must be resolved by either migrating that consumer to the promoted path or proving it is still required migration scaffolding. Do not restore `journey_shadow` merely to satisfy stale tests.

## Remaining R8 candidates

After this deletion, continue only from concrete inventory:

- direct-entry callers that still invoke legacy `begin` outside explicit recovery/tests;
- duplicated hosted issue-bus discovery/submission/result-correlation clients;
- CLI-coupled defaults still reachable from normal operation.

Each later R8 slice must delete or privatize concrete surface. No additive Journey layer is justified by the retirement phase.
