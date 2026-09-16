# Paved-path migration status — 2026-09-15

Status: consolidated architectural checkpoint after R5, migration hardening, enforcement, and qualified R6a clean recut.

This document is a status snapshot, not a mutable authority. Current Work, Coordination, Agent Cycle, CI, Delivery and Project state remain owned by their canonical structured authorities and tooling.

## Current control baseline

- `main` at clean-recut start: `f4c7ae59692c71d988fbadf481a80cce47f36ee1`
- latest merged architectural checkpoint before the recut: PR #305
- paved-path migration hardening: merged in PR #301
- hardening enforcement in permanent agent bootstrap rules: merged in PR #303
- R6a clean-recut plan: merged in PR #304
- post-hardening checkpoint: merged in PR #305
- clean R6a candidate: PR #306, branch `work/operations/r6a-hosted-entry-recut`
- historical prototype branch `work/operations/r6a-hosted-entry-composition` remains evidence and is not a promotion source.
- PR #302 was intentionally closed unmerged because its `docs/*` branch violated the Agent Cycle operational branch grammar; the guard correctly failed closed and the same policy change was resubmitted from a canonical `work/operations/...` branch in PR #303.

## Migration thesis

Do not rewrite the proven engine. Build a reentrant, initially non-authoritative transmission layer over existing guarantees; prove equivalence; promote one paved normal path; then demote, privatize or remove superseded manual choreography.

Additive scaffolding is expected during migration. It remains healthy only while every permanent paved-path surface has a credible replacement target and temporary scaffolding has an explicit death condition.

## Completed recuts

| Recut | State | What is now proven | Retirement significance |
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

### Clean R6a recut checkpoint

PR #306 was created from current `main`, not from the historical prototype. The candidate adds one semantic hosted-entry composer and focused canaries.

The recut deliberately differs from the prototype:

- V0.4 is the only begin contract emitted; there is no V0.3 fallback;
- the caller supplies observed semantic ToolSurface identifiers plus inventory completeness, not a raw hosted `runtimeEnvironment` object;
- runtime-environment validity is delegated to `hosted_agent_cycle.validate_runtime_begin_command`, which in turn consumes the existing runtime-provider adapter vocabulary;
- canonical handle decoding remains owned by `hosted_cycle_handle`;
- no Journey authority, session, store, lifecycle, workflow, marker or protocol version was introduced;
- incomplete ToolSurface observation yields `UNKNOWN` before any transport write;
- an exact pending request is idempotently reused; a same-ID/different-payload conflict fails closed;
- hosted issue discovery, comment pagination and result correlation remain local duplicated transport debt. They are not promoted as Journey semantics and are a bounded R7 consolidation/demotion target.

The first Agent Ops run for PR #306 failed only in the new R6a fixture because the fixture invented an unregistered ToolSurface (`github.issue.comment.write`). The production composer correctly delegated to the canonical runtime validator, which rejected the invented surface. The fixture was corrected to the existing registered `github-connector-tools` surface; no production guard was weakened.

On head `4251d30e0cf6a4ab6639dedf9542895f59e50f07`, all three qualification carriers completed successfully:

- Agent Ops run `35049709127`: `success`;
- Coordination Guard run `35049709121`: `success`;
- Supervisor Snapshot run `35049709110`: `success`.

This is **R6a qualification evidence, not paved-path promotion evidence**. PR #306 must still preserve canonical Work/branch lineage before integration, and R6 remains incomplete until the black-box positive and negative canaries prove the normal path from semantic task/Work intent.

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

The migration remains structurally healthy because R1-R5 and the clean R6a recut did not create parallel mutable authorities. Journey surfaces derive or compose over existing primitives; canonical Work, Coordination, Agent Cycle, Git mutation, Delivery and Project Machine contracts remain authoritative.

The main risk is no longer authority duplication. It is protocol duplication: paved composers can accidentally absorb hosted issue-bus mechanics, version selection, marker parsing and result correlation. The clean R6a recut removed version fallback and raw runtime-envelope knowledge from the caller but intentionally did not invent a generic hosted-transport framework. The remaining bus plumbing has an explicit R7 retirement/consolidation obligation.

## Promotion path from here

### R6a — clean hosted-entry recut

Qualification achieved in PR #306:

- started from current `main`, not the historical prototype branch;
- caller inputs are semantic ToolSurfaces and task/Work intent;
- runtime proof delegates to existing runtime-provider/Agent runtime contracts;
- handle and Agent Cycle validation delegate to canonical owners;
- no silent command-version downgrade exists;
- fresh/build-only, valid reuse, pending/idempotent retry, incomplete inventory, conflicting identity and invalid-surface negatives are covered by focused canaries;
- no new authority/workflow/marker/state was introduced;
- remaining duplicated transport debt is explicit and assigned to R7 rather than abstracted prematurely.

Still required before integration/promotion:

- reconcile the canonical Work execution binding with the clean recut branch/PR rather than leaving the Work attached only to the historical prototype;
- keep all integration gates green after this documentation checkpoint;
- integrate through the governed delivery path;
- then execute the R6 black-box canaries.

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

Preserve the qualified PR #306 candidate, reconcile its clean branch/PR with the canonical R6a Work execution binding, and integrate only through the governed path while gates remain green. After integration, rerun R6 as a black-box positive + negative paved-path canary. Only that evidence permits R7 promotion/demotion.