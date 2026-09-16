# R6a hosted entry recut plan

Status: **executed and promoted through PR #306; retained as the historical design and retirement contract for R6a.** The clean recut was integrated before the R6 public-surface proof in PR #307. This document remains subordinate to `docs/architecture/paved-path-migration-hardening.md` and the R6-R8 rules in `AGENTS.md`.

Current execution control point: do not continue patching or promote `work/operations/r6a-hosted-entry-composition`. That prototype branch remains historical evidence. The promoted implementation came from the clean recut branch `work/operations/r6a-hosted-entry-recut`. Future changes to hosted entry are justified only by live R6 evidence and must satisfy the hardening contract; the current checkpoint is `docs/architecture/paved-path-migration-status-2026-09-16.md`.

## Outcome after PR #306 / PR #307

The clean recut satisfied the core architectural intent of this plan without creating a second lifecycle or authority:

- normal callers provide semantic Work/task intent and ToolSurface observations rather than a raw hosted runtime envelope;
- the normal path emits the current V0.4 Agent Cycle begin contract only; no convenience downgrade to older schemas was promoted;
- runtime validation remains owned by the canonical Agent Cycle/runtime contracts;
- handle decoding/validation remains delegated to canonical handle tooling;
- incomplete runtime observation remains `UNKNOWN` before transport writes;
- identical pending/ready requests are reusable/idempotent and conflicting identity remains fail-closed;
- no Journey authority, session, store, workflow, marker or protocol version was introduced;
- hosted issue/comment/result correlation remains bounded migration debt with an explicit R7 retirement/consolidation obligation.

PR #307 then added the public-surface guard and negative no-transport canary. Those proofs make the old caller knowledge listed in this plan eligible for R7 demotion, but they do **not** replace the still-required live positive + negative R6 traversal.

## Purpose

R6a exists to remove hosted Agent Cycle entry choreography from the normal agent path without creating a second lifecycle, authority, session model, or compatibility architecture.

The desired normal-path contract is semantic:

`Work/task intent -> obtain or reuse a valid AgentCycleHandle`

The caller must not need to know the canonical issue number, comment markers, command schema versions, result-comment search mechanics, predicted cycle/hash identities, raw hosted runtime envelopes, or provider-normalization details.

R6a is successful only if it makes that knowledge internal while continuing to delegate safety and lifecycle semantics to the already-proven canonical owners.

## Current baseline and disposition

Observed baseline at planning time:

- planning `main`: `3a3bccff2e1efedd59abbb0649c34a78b8b191ed`
- plan integration `main`: `ebf016a0f23585cecb61c0d8edd2fb19d381e977`
- historical R6a branch: `work/operations/r6a-hosted-entry-composition`
- historical branch head at planning time: `fa36a6903a4410a055ce9dc5d048574aa02708cb`
- prototype implementation commit: `b1ae84f0882f86831233f9f6441cd7f2bebbbff9`
- prototype file: `tools/agent_tools/journey_entry.py`
- the historical branch also contains a hardening-doc commit whose content was integrated independently on `main` through PR #301.
- hardening enforcement was integrated through PR #303 after PR #302 correctly failed closed on a non-operational `docs/*` branch.

Planning-time decision: **the historical R6a branch is evidence, not the promotion branch.** That decision was carried out. PR #306 promoted a clean recut from current `main`; the prototype branch was not force-rewritten or merged.

The prototype remains useful as a behavioral specimen because it shows the failure mode this plan was designed to avoid: semantic entry composition mixed with excessive hosted transport/protocol knowledge and insufficient qualification. It is not a fallback implementation.

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

A shared hosted transport seam is permitted only if the same migration window materially reduces at least **two existing duplicated client implementations**.

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

If moving I/O into a shared seam does not delete or materially reduce duplicate I/O code in at least two callers in the same recut, do not add the seam. Keep the duplication explicitly bounded and carry it into the R7 retirement ledger.

## Required recut shape

The hardened R6a implementation was designed around four conceptual steps without introducing four new subsystems:

1. **Observe semantic context.** Resolve Work/task identity, actor/session intent, ToolSurfaces/provider context, and any existing canonical handle.
2. **Ask canonical owners for protocol material.** Runtime environment and begin command/identity semantics come from existing canonical builders/validators, not Journey-authored copies.
3. **Use existing hosted transport.** Submit the canonical request and observe canonical results. If a narrow shared transport seam is later justified by simultaneous deduplication, use it below Journey semantics.
4. **Project a semantic disposition.** Return only what a normal agent needs: valid handle/reuse, request submitted/pending, blocked, unknown, and the next safe action. Never authorize mutation beyond the canonical primitive.

Future changes must preserve this decomposition and must not add another Journey module merely to split these steps. Prefer functions in the existing canonical owner when a missing reusable operation is genuinely owner-specific.

## Runtime-environment rule

Normal R6a callers must not supply a raw hosted `runtimeEnvironment` object.

R6a must derive or observe the runtime proof inputs through the existing runtime-provider/Agent runtime contracts. If required ToolSurfaces/provider observations are unavailable, the result is `UNKNOWN` or `BLOCKED` according to the canonical contract; it must not silently downgrade to an older command schema to make entry succeed.

Backward command-schema support may remain inside the canonical Agent Cycle host for replay/recovery of historical records, but it must not become a normal-path Journey fallback.

## Handle/re-entry rule

Existing handle reuse must flow through canonical handle validation. R6a must not decide that a handle is valid by comparing a locally recreated subset of hashes.

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

The following cases remain regression requirements even though the clean recut has been promoted:

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

## R6a promotion gate — historical result

PR #306 satisfied the implementation-side promotion gate:

- caller contract is semantic and contains no raw hosted runtime envelope;
- no new authority, persistence, workflow, marker, protocol version, or lifecycle state was introduced;
- handle semantics remain delegated to canonical handle tooling;
- Agent Cycle command/runtime semantics remain delegated to canonical Agent Cycle/runtime owners;
- no normal-path fallback silently selects an older protocol version;
- remaining hosted transport duplication is explicitly bounded with an R7 deletion/consolidation target;
- positive and negative qualification canaries were integrated;
- the PR description names the legacy/public knowledge that becomes eligible for demotion.

PR #307 additionally proves the public surface does not require hosted protocol identities and preserves the negative no-transport behavior.

The remaining gate belongs to R6 as a whole: a live positive + negative traversal must prove the composed path end to end before R7 promotion begins.

## R7 handoff obligations

R6a promotion leaves a concrete R7 retirement ledger. At minimum R7 must evaluate/demote:

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

## Execution sequence — current disposition

1. Historical R6a prototype branch retained unchanged as evidence — **done**.
2. Stale lifecycle/lease state reconciled before the clean recut — **done**.
3. Clean R6a recut branch started from current main — **done**.
4. R6a implementation qualified and integrated through PR #306 — **done**.
5. R6 public surface and fail-closed negative guard integrated through PR #307 — **done**.
6. Run the live positive + negative R6 traversal without adding another façade/workflow — **next**.
7. If live traversal succeeds, execute R7 as an actual default-path/demotion change.
8. Execute R8 as deletion/demotion, not optional cleanup.

## Review accounting for every R7/R8 follow-up

Every relevant PR must state explicitly:

- permanent code added;
- temporary scaffolding added;
- existing code/API removed or materially reduced;
- old normal-path knowledge made unnecessary;
- remaining duplicated protocol debt;
- evidence supporting promotion;
- exact R7/R8 retirement target;
- whether public normal-path surface shrinks, is temporarily flat, or grows under an explicit retirement deadline.

## Abort triggers carried forward

Abort and redesign before merge if any of the following occurs:

- Journey needs to own a new session/authority/store to make entry work;
- the migration requires permanent reading/reconciling of two lifecycle models;
- `journey_entry` must understand more command versions/exceptions than `hosted_agent_cycle.py`;
- a new transport helper is added without materially reducing at least two existing duplicate consumers;
- runtime proof is weakened or silently downgraded for convenience;
- a negative canary requires suppressing BLOCKED/UNKNOWN to reach green;
- the migration increases both old and new public normal-path APIs without naming which one will be demoted in R7;
- two consecutive migration recuts add orchestration without making a legacy surface eligible for demotion.

## Definition of done

R6a implementation is done. The broader entry migration is promotable to R7 only when a black-box agent can start from semantic Work/task intent and traverse the paved path through canonical primitives without knowing hosted issue-bus mechanics, command versions, raw runtime envelopes, authority-head choreography, lease/binding identities or result-comment search mechanics; negative cases remain fail-closed; and the implementation leaves an explicit, credible deletion/demotion path for R7/R8.
