# R6a hosted entry recut plan

Status: hardening recut plan. This document is subordinate to `docs/architecture/paved-path-migration-hardening.md` and the R6-R8 rules in `AGENTS.md`.

## Purpose

R6a exists to remove hosted Agent Cycle entry choreography from the normal agent path without creating a second lifecycle, authority, session model, or compatibility architecture.

The desired normal-path contract is semantic:

`Work/task intent -> obtain or reuse a valid AgentCycleHandle`

The caller must not need to know the canonical issue number, comment markers, command schema versions, result-comment search mechanics, predicted cycle/hash identities, raw hosted runtime envelopes, or provider-normalization details.

R6a is successful only if it makes that knowledge internal while continuing to delegate safety and lifecycle semantics to the already-proven canonical owners.

## Current baseline and disposition

Observed baseline at planning time:

- `main`: `3a3bccff2e1efedd59abbb0649c34a78b8b191ed`
- historical R6a branch: `work/operations/r6a-hosted-entry-composition`
- historical branch head: `fa36a6903a4410a055ce9dc5d048574aa02708cb`
- prototype implementation commit: `b1ae84f0882f86831233f9f6441cd7f2bebbbff9`
- prototype file: `tools/agent_tools/journey_entry.py`
- the historical branch also contains a hardening-doc commit whose content is already integrated independently on `main`.

Decision: **the historical R6a branch is evidence, not the promotion branch.** Do not force-rewrite or merge it as-is. The hardened implementation must start from current `main` on a clean recut branch after Work/cycle/lease state is reobserved.

The prototype is useful as a behavioral specimen, but it is not promotion-ready. It currently combines semantic entry composition with too much hosted transport/protocol knowledge and has no qualifying test suite on the branch.

## Inventory of current prototype responsibilities

The prototype currently performs several distinct jobs:

1. accepts semantic task/session/actor inputs;
2. accepts a caller-supplied raw `runtime_environment` and otherwise falls back to an older Hosted Agent Cycle command version;
3. discovers the canonical issue bus;
4. paginates issue comments;
5. parses hosted markers;
6. correlates begin requests and begin results;
7. predicts/validates cycle, context, and handle identities;
8. constructs Hosted Agent Cycle command versions;
9. posts begin requests;
10. re-observes results;
11. returns paved-path dispositions such as reused/requested/pass/blocked/unknown.

Only the first and last responsibilities belong naturally to R6a/Journey semantics. The middle responsibilities must be delegated to canonical owners or to a narrowly scoped shared transport seam below Journey semantics.

## Canonical responsibility owners

| Responsibility | Canonical owner | R6a rule |
| --- | --- | --- |
| Agent Cycle schemas, command versions, runtime proof semantics, cycle/context/handle identity algorithms | `tools/hosted_agent_cycle.py` | delegate; do not reproduce algorithms or version-selection rules in Journey |
| Handle lookup, handle payload validation, predicted identity validation | `tools/hosted_handle_requests.py` | delegate; Journey may consume the validated result but must not reimplement handle rules |
| Hosted record/marker vocabulary and directive families | `tools/hosted_record_vocabulary.py` plus canonical host-specific constants where not yet centralized | consume canonical vocabulary; do not create Journey-owned markers |
| Runtime provider/environment derivation | `tools/runtime_provider_adapter.py` and Agent runtime contracts | derive/observe from ToolSurfaces/provider context; do not require raw hosted runtime JSON from the normal caller |
| Work/Continuation truth | canonical continuation writer/state | observe only; no Journey Work mirror |
| Agent Cycle lifecycle truth | canonical Agent Cycle host/carrier | submit/observe only; no Journey cycle/session state |
| Hosted issue-bus I/O | currently duplicated across clients | may be consolidated only as a narrow transport seam under the hardening rules below |
| Paved-path semantic disposition | R6a composer | this is the intended permanent responsibility |

## Proven duplicated transport debt

Hosted issue-bus I/O is currently duplicated in at least:

- `tools/agent_ownership.py`
- `tools/agent_authoring.py`
- `tools/agent_delivery.py`
- the historical `tools/agent_tools/journey_entry.py` prototype

The duplicated concerns include canonical issue discovery and direct issue-comment submission; some clients also carry their own polling/result-observation mechanics.

This duplication is migration debt, not a reason to create a generic compatibility framework.

## Transport-seam decision gate

A shared hosted transport seam is permitted in the R6a recut only if the same migration window materially reduces at least **two existing duplicated client implementations**.

If introduced, that seam must be intentionally boring and I/O-only. Acceptable responsibilities are:

- locate the canonical issue by a caller-supplied canonical title;
- list/paginate issue comments;
- post an already-constructed comment payload;
- surface transport/provider failures without semantic reinterpretation.

It must **not** own:

- marker vocabulary;
- command schema/version selection;
- request/result semantic correlation rules;
- cycle/handle identity algorithms;
- Work, lease, Delivery, or Journey lifecycle state;
- generic legacy/new-model translation.

If moving I/O into a shared seam does not delete or materially reduce duplicate I/O code in at least two callers in the same recut, do not add the seam. Keep R6a local and record the remaining transport duplication as an explicit R7 retirement target instead.

## Required recut shape

The hardened R6a implementation should be decomposable conceptually into four steps without introducing four new subsystems:

1. **Observe semantic context.** Resolve Work/task identity, actor/session intent, ToolSurfaces/provider context, and any existing canonical handle.
2. **Ask canonical owners for protocol material.** Runtime environment and begin command/identity semantics come from existing canonical builders/validators, not Journey-authored copies.
3. **Use existing hosted transport.** Submit the canonical request and observe canonical results. If a narrow shared transport seam is justified by simultaneous deduplication, use it here.
4. **Project a semantic disposition.** Return only what a normal agent needs: valid handle/reuse, request submitted/pending, blocked, unknown, and the next safe action. Never authorize mutation beyond the canonical primitive.

The recut must not add another Journey module merely to split these steps. Prefer functions in the existing canonical owner when a missing reusable operation is genuinely owner-specific.

## Runtime-environment rule

Normal R6a callers must not supply a raw hosted `runtimeEnvironment` object.

R6a must derive or observe the runtime proof inputs through the existing runtime-provider/Agent runtime contracts. If required ToolSurfaces/provider observations are unavailable, the result is `UNKNOWN` or `BLOCKED` according to the canonical contract; it must not silently downgrade to an older command schema to make entry succeed.

Backward command-schema support may remain inside the canonical Agent Cycle host for replay/recovery of historical records, but it must not become a normal-path Journey fallback.

## Handle/re-entry rule

Existing handle reuse must flow through `hosted_handle_requests` validation. R6a must not decide that a handle is valid by comparing a locally recreated subset of hashes.

The composer may distinguish:

- no existing handle -> canonical begin is eligible;
- one canonical valid handle for the semantic identity -> reuse;
- incomplete provider/authority observation -> `UNKNOWN`/`BLOCKED`;
- stale, malformed, ambiguous, or identity-mismatched handle -> fail closed and preserve the canonical reason.

It must not create `JourneySession`, a second re-entry state machine, or a reconciliation loop between Journey and Agent Cycle.

## Lifecycle discontinuity discovered during R6a

Observed behavior: an Agent Cycle may remain open after its write lease expires, while the write lifecycle refuses a second acquire in the same cycle once that lifecycle has started. The safe recovery sequence observed was:

`release expired binding -> close old cycle -> begin new cycle for the same Work -> acquire new ownership`

This is a real engine/lifecycle boundary, not a reason to add Journey compatibility state. R6a may surface the canonical next safe action, but it must not hide the discontinuity by inventing a persistent session abstraction.

Treat this as candidate retirement/simplification material for R7/R8 after the paved path is proven.

## Test and canary matrix

R6a cannot be promoted without tests/canaries covering all of the following:

| Case | Required result |
| --- | --- |
| fresh semantic entry with complete observations | obtains/submits canonical begin without caller bus/protocol knowledge |
| valid existing canonical handle | reuses it idempotently; no new begin/write |
| repeated identical entry request while canonical result is pending | no duplicate semantic begin; disposition remains conservative |
| incomplete ToolSurfaces/provider/runtime observation | `UNKNOWN` or `BLOCKED`; no command-version downgrade for convenience |
| malformed/stale/identity-mismatched handle | fail closed; no new mutable authority |
| ambiguous/multiple conflicting canonical handles | fail closed |
| transport/provider failure | preserve failure/unknown evidence; no false PASS |
| negative canary with intentionally wrong identity/context | blocked before unintended write |
| historical/recovery record requiring old schema | handled by canonical host/recovery path, not normal Journey fallback |
| end-to-end black-box R6 entry | agent starts from semantic Work/task intent and receives/reuses a valid handle without knowing issue/markers/schema/result search |

Every test must assert absence of unintended writes where applicable, not merely the returned status.

## R6a promotion gate

R6a is promotable only when all statements below are true:

- caller contract is semantic and contains no raw hosted runtime envelope;
- no new authority, persistence, workflow, marker, protocol version, or lifecycle state was introduced;
- handle semantics are delegated to the canonical handle owner;
- Agent Cycle command/runtime semantics are delegated to the canonical Agent Cycle/runtime owners;
- no normal-path fallback silently selects an older protocol version;
- hosted transport duplication is either materially reduced in at least two existing clients in the same recut or explicitly left as bounded temporary debt with an R7 deletion target;
- positive and negative tests are green;
- a black-box R6 canary proves entry without hosted-protocol knowledge;
- the PR description names the legacy/public knowledge that becomes eligible for demotion.

If any item requires a new Journey state/session/authority or a permanent dual-read model, stop and redesign instead of merging.

## R7 handoff obligations

R6a promotion must leave a concrete R7 retirement ledger. At minimum R7 must evaluate/demote:

- manual Agent Cycle issue-bus entry as a normal documented path;
- direct manual construction of begin commands by normal agents;
- duplicate hosted issue-bus I/O in ownership/authoring/delivery/entry clients if not already consolidated;
- protocol/version details exposed in paved-path-facing documentation;
- re-entry choreography that remains necessary only for recovery/debugging.

R7 does not count as promotion if it only recommends the paved path while keeping every legacy path equally public and normal.

## R8 deletion obligations

R8 must produce measurable subtraction. Candidate deletions/demotions include:

- `journey_shadow` once equivalence confidence no longer requires it;
- duplicated hosted-bus I/O after a proven shared seam exists;
- obsolete normal-path request-construction helpers superseded by semantic composers;
- historical compatibility paths that are no longer needed even for recovery;
- documentation/examples that teach normal agents the hosted protocol directly.

A legacy primitive may remain internal when it is still the canonical safety engine. The target is not to delete proven guarantees; the target is to delete duplicate/public choreography around them.

## Execution sequence

1. Keep the historical R6a branch unchanged as evidence.
2. Reobserve current Work, Agent Cycle, lease, `main`, and branch state. Cleanly close/release any stale execution before a recut begins.
3. Start a clean R6a recut branch from current `main`.
4. Reuse the existing R6a Work if canonical Continuation semantics permit safe re-entry; otherwise create an explicit successor Work with lineage/dependency. Never silently duplicate the Work.
5. Establish tests around canonical ownership boundaries before porting the prototype behavior wholesale.
6. Reduce/delegate command, runtime, handle, and transport responsibilities. Do not copy the 484-line prototype and then patch around it.
7. If a hosted transport seam is introduced, migrate at least two existing duplicated clients in the same PR/recut and show before/after reduction.
8. Run unit/regression tests plus the R6 black-box positive and negative canaries.
9. Promote only after the R6a gate passes; then execute R7 as an actual default-path/demotion change.
10. Execute R8 as deletion/demotion, not optional cleanup.

## Review accounting for every R6a/R7/R8 PR

Every relevant PR must state explicitly:

- permanent code added;
- temporary scaffolding added;
- existing code/API removed or materially reduced;
- old normal-path knowledge made unnecessary;
- remaining duplicated protocol debt;
- evidence supporting promotion;
- exact R7/R8 retirement target;
- whether public normal-path surface shrinks, is temporarily flat, or grows under an explicit retirement deadline.

## Abort triggers specific to this recut

Abort and redesign before merge if any of the following occurs:

- Journey needs to own a new session/authority/store to make entry work;
- the recut requires permanent reading/reconciling of two lifecycle models;
- `journey_entry` must understand more command versions/exceptions than `hosted_agent_cycle.py`;
- a new transport helper is added without materially reducing at least two existing duplicate consumers;
- runtime proof is weakened or silently downgraded for convenience;
- a negative canary requires suppressing BLOCKED/UNKNOWN to reach green;
- the recut increases both old and new public normal-path APIs without naming which one will be demoted in R7;
- two consecutive migration recuts add orchestration without making a legacy surface eligible for demotion.

## Definition of done

R6a is done when a black-box agent can start from semantic Work/task intent and obtain or reuse a valid AgentCycleHandle through canonical primitives, without knowing hosted issue-bus mechanics, command versions, raw runtime envelopes, authority-head choreography, or result-comment search mechanics; negative cases remain fail-closed; and the implementation leaves an explicit, credible deletion/demotion path for R7/R8.
