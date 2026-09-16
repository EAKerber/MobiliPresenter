# Paved-path migration status — 2026-09-15

Status: consolidated architectural checkpoint after R5, migration hardening, enforcement, and R6a recut planning.

This document is a status snapshot, not a mutable authority. Current Work, Coordination, Agent Cycle, CI, Delivery and Project state remain owned by their canonical structured authorities and tooling.

## Current control baseline

- `main`: `ebf016a0f23585cecb61c0d8edd2fb19d381e977`
- latest architectural milestone: `Architecture: harden R6a hosted-entry recut plan (#304)`
- paved-path migration hardening: merged in PR #301
- hardening enforcement in permanent agent bootstrap rules: merged in PR #303
- R6a clean-recut plan: merged in PR #304
- PR #302 was intentionally closed unmerged because its `docs/*` branch violated the Agent Cycle operational branch grammar; the guard correctly failed closed and the same policy change was resubmitted from a canonical `work/operations/...` branch in PR #303.

## Migration thesis

Do not rewrite the proven engine. Build a reentrant, initially non-authoritative transmission layer over existing guarantees; prove equivalence; promote one paved normal path; then demote, privatize or remove superseded manual choreography.

Additive scaffolding is expected during migration. It remains healthy only while every permanent paved-path surface has a credible replacement target and temporary scaffolding has an explicit death condition.

## Completed recuts

| Rec- ut | State | What is now proven | Retirement significance |
| --- | --- | --- | --- |
| R0 — trust repair | complete | negative close evidence is preserved before terminal propagation; release-before-seal ordering established | restores confidence that later automation cannot hide negative evidence |
| R1 — JourneyProjection | complete | live, read-only, non-authoritative JourneyProjection is exposed through the existing agent surface | manual multi-authority interpretation becomes eligible for demotion once paved-path promotion is proven |
| R2 — shadow equivalence | complete | non-authoritative comparison can evaluate projected entry/re-entry against observed actions without executing the projection | `journey_shadow` is explicitly temporary and becomes a deletion target after stable R6 canaries |
| R3 — ownership composition | complete | ownership request construction/CAS discovery can be derived over the existing lease lifecycle without a new Journey authority | manual lease choreography becomes a candidate internal/recovery-only surface |
| R4 — authoring composition | complete | handle + branch + changes can compose into the existing Agent Tool / `git.files.mutate` path while existing guards own CAS, lease proofs and readbacks | direct canonical mutation construction becomes a candidate internal/recovery-only surface |
| R5 — delivery/finalization composition | complete | Delivery request inputs can be derived while existing Delivery remains sole merge authority; safe post-delivery order is projected as Work -> ownership release -> cycle close | manual Delivery request assembly becomes a candidate internal/recovery-only surface |

## Current frontier: R6 / R6a

The first R6 black-box attempt exposed a real paved-path gap before project mutation: a normal agent still had to know hosted issue-bus choreography to obtain the initial `AgentCycleHandle`.

R6a exists only to remove that entry choreography from the normal path.

The desired public contract is:

`semantic Work/task intent -> obtain or reuse a valid AgentCycleHandle`

The caller must not need to know issue #145, hosted comment markers, command schema versions, result-comment search mechanics, predicted cycle/hash identities, raw hosted runtime envelopes, lease/binding identities, or authority-head choreography.

### Historical R6a prototype disposition

The historical branch `work/operations/r6a-hosted-entry-composition` and its prototype `tools/agent_tools/journey_entry.py` are evidence, not the promotion branch.

The prototype demonstrated useful behavior but combined semantic composition with too much hosted transport/protocol knowledge and lacked a qualifying test suite when first observed. It must not be promoted by incremental patching until green.

The clean R6a recut is governed by `docs/architecture/r6a-hosted-entry-recut-plan.md`.

## Hardening now in force

`docs/architecture/paved-path-migration-hardening.md` is no longer advisory planning. Its R6-R8 rules are referenced by `AGENTS.md` and therefore part of the permanent agent bootstrap contract.

Key consequences:

- no new mutable Journey authority/state/session/store;
- no permanent dual-read/dual-write reconciliation;
- no generic compatibility framework for paved-vs-legacy translation;
- no composer may become a second implementation of the canonical primitive it wraps;
- protocol plumbing must remain below Journey semantics;
- a shared hosted-transport seam is allowed only when it materially reduces at least two existing duplicate clients in the same migration window;
- UNKNOWN/BLOCKED remain fail-closed;
- every R6-R8 PR must name the old knowledge/API it supersedes and the exact deletion/demotion target;
- R7 must change the operational default and demote at least one legacy/manual normal-path surface;
- R8 must produce measurable subtraction.

## Known architectural tension discovered during R6a

A real lifecycle discontinuity was observed: an Agent Cycle may remain open after its write lease expires, while the write lifecycle refuses a second acquire once that lifecycle has already started.

The safe sequence observed was:

`release expired binding -> close old cycle -> begin new cycle for the same Work -> acquire new ownership`

This is currently treated as an engine/lifecycle boundary, not something to hide behind a new JourneySession or compatibility state. R7/R8 should evaluate whether the underlying choreography can be simplified after the paved path is proven.

## Evidence that the migration is still on the intended path

The migration remains structurally healthy because R1-R5 did not create parallel mutable authorities. Journey surfaces derive or compose over existing primitives; canonical Work, Coordination, Agent Cycle, Git mutation, Delivery and Project Machine contracts remain authoritative.

The main risk is no longer authority duplication. It is protocol duplication: paved composers can accidentally absorb hosted issue-bus mechanics, version selection, marker parsing and result correlation. R6a is the control point for preventing that from becoming permanent architecture.

## Promotion path from here

### R6a — clean hosted-entry recut

Required before promotion:

- start from current `main`, not the historical prototype branch;
- keep caller inputs semantic;
- derive runtime proof through existing runtime-provider/Agent runtime contracts;
- delegate handle and Agent Cycle semantics to canonical owners;
- do not silently downgrade command versions;
- cover fresh entry, valid reuse, pending/idempotent retry, incomplete observation, stale/malformed/ambiguous handle, provider failure and unintended-write negatives;
- if transport is consolidated, reduce at least two duplicated clients in the same recut;
- leave an explicit R7 retirement ledger.

### R6 — black-box proof

A normal agent starting only from semantic task/Work intent must traverse entry, ownership, authoring, candidate/CI, Delivery and safe finalization without hosted-protocol knowledge. Positive and negative canaries must both pass.

R6 is not complete if the canary succeeds only because a human/agent manually supplies issue, marker, command-version, authority-head, lease/binding or result-search details.

### R7 — promote and demote

R7 changes the default path. Paved semantic surfaces become the documented normal route and at least one superseded manual surface becomes explicitly internal-only or recovery-only.

If R7 merely recommends the paved path while retaining every legacy path as equally normal/public, promotion has failed.

### R8 — retire and delete

R8 is a mandatory subtraction milestone. Expected candidates include:

- `journey_shadow` after equivalence confidence is sufficient;
- duplicated hosted-bus I/O after proven consolidation;
- normal-path request constructors replaced by semantic composers;
- documentation/examples that teach hosted protocol mechanics to normal agents;
- compatibility/re-entry paths that no longer serve recovery.

If R8 cannot identify meaningful deletion/demotion because the new layer permanently depends on both old and new operational models, the migration thesis must be re-evaluated rather than extended.

## Review rubric for the next changes

For each R6-R8 PR answer all of the following:

1. What permanent code is added?
2. What temporary scaffolding is added?
3. What old normal-path knowledge/API becomes unnecessary?
4. What exact code/API/doc surface becomes removable, private, internal-only or recovery-only?
5. What evidence proves promotion is safe?
6. What duplicated protocol debt remains?
7. Does the public normal-path surface shrink, remain temporarily flat, or grow under an explicit retirement deadline?

A change that cannot answer question 3 or 4 is not paved-path progress; it is horizontal expansion and should be redesigned before merge.

## Immediate next action

Do not continue patching the historical R6a prototype. Execute the clean R6a recut from current `main` under the hardening and recut-plan gates, then rerun the R6 black-box canaries. Only successful positive + negative evidence permits R7 promotion.
