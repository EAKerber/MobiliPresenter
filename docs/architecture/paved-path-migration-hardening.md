# Paved-path migration hardening

Status: **active migration control contract for R6-R8**. Merged in PR #301 and enforced by `AGENTS.md` through PR #303. R6a was promoted through the clean recut in PR #306, the R6 public-surface proof was integrated in PR #307, and PRs #309-#310 refined the live-executor/provider boundary. The current execution checkpoint is `docs/architecture/paved-path-migration-status-2026-09-16.md`; `docs/architecture/paved-path-provider-policy.md` is a normative addendum for provider/executor decisions.

This document is not pre-implementation advice. Any R6-R8 architectural mutation must satisfy these gates or stop for redesign.

## Thesis

Do not rewrite the proven engine. Build a reentrant, initially non-authoritative transmission layer over existing guarantees, prove equivalence, promote the paved path, then demote or remove superseded public choreography. Temporary additive scaffolding is acceptable only when it has an explicit retirement target and evidence gate.

## Non-negotiable boundaries

- No new mutable authority for derivable information.
- No JourneyState, JourneyAuthority, JourneyLease, JourneySession, or equivalent shadow ownership.
- No workflow, marker, protocol version, durable store, or state machine solely for ergonomics.
- UNKNOWN or BLOCKED must never be normalized to PASS.
- Existing CAS, lease, continuation, Agent Cycle, Delivery, Project Machine, canonical-writer and readback guarantees remain authoritative.
- A composer may derive inputs and submit an existing primitive; it must not become an independent implementation of that primitive.
- Compatibility logic must have a deletion/demotion gate. Generic compatibility layers are forbidden unless they immediately remove more duplicated protocol surface than they add.
- Provider availability and executor availability are distinct. A discovered ToolSurface does not by itself justify inventing an executor bridge.
- `gh-api-cli`, shell `gh`, raw DNS/HTTP and local git are not paved-path fallbacks merely because they are executable from some runtimes; provider policy is defined by `paved-path-provider-policy.md`.

## Protocol containment rule

The hosted issue bus is infrastructure, not Journey semantics. Journey/paved-path composers must not independently evolve copies of comment pagination, marker parsing, request/result correlation, protocol-version selection, or provider response normalization. Existing shared validators/builders such as `hosted_handle_requests.py`, `hosted_agent_cycle.py`, `hosted_cycle_handle.py`, `runtime_provider_adapter.py`, and canonical host modules remain the semantic owners.

If a missing transport or executor seam is proven, consolidation is allowed only when all of the following are true:

1. it lives below Journey/paved-path semantics;
2. it introduces no authority or persistence;
3. at least two existing duplicated transport/executor implementations are deleted, demoted or materially reduced in the same migration window;
4. callers retain the canonical primitive contracts and fail-closed dispositions;
5. it does not become a generic compatibility framework;
6. it is useful as runtime/provider infrastructure beyond making one migration canary executable.

A canary-only executor, Journey runner or bridge is explicitly disallowed.

## Replacement and retirement map

| Scaffolding / paved surface | Superseded normal-path knowledge | Promotion evidence | Retirement / demotion target |
| --- | --- | --- | --- |
| JourneyProjection | manually interpreting Project/Work/Git/re-entry authorities to know where the agent is | projection agrees with observed outcomes and never creates false PASS | keep projection only if it remains the single public read model; remove redundant manual interpretation helpers |
| `journey_shadow` | none; it is measurement scaffolding | R6 black-box positive + negative canaries and R7 default-path promotion | **retired in R8; no runtime replacement** |
| `ensure_ownership` | manual acquire/release/re-entry request construction and CAS discovery | repeated valid reuse/acquire/release/expired cases, zero false ownership | manual lease choreography becomes internal/recovery-only |
| authoring composition | manual GitMutationPlan/CAS/lease plumbing for normal edits | black-box authoring succeeds through existing Agent Tool with complete readback | direct canonical mutation construction becomes internal/recovery-only |
| delivery/finalization composition | manual Delivery request assembly and post-merge ordering discovery | governed merge + Work/lease/cycle finalization canary succeeds | manual Delivery request assembly becomes internal/recovery-only |
| R6/R6a entry composition | issue number, markers, HostedAgentCycleCommand versions, begin-result search, runtime envelope mechanics | task/Work intent obtains or reuses a valid AgentCycleHandle without caller protocol knowledge | manual Agent Cycle bus entry becomes internal/recovery-only |
| provider/executor seam | implicit shell/CLI transport assumptions and duplicated hosted transport clients | real provider-backed public-façade traversal plus no loss of guards/readbacks | normal path binds canonical ToolSurfaces; CLI/legacy clients become recovery-only or are removed |

## R6a hardening gate — satisfied by clean recut

The R6a gate was exercised by the clean recut in PR #306. The historical `work/operations/r6a-hosted-entry-composition` prototype remains evidence only and must not be revived as the promotion path.

The following remain regression requirements for any future change to hosted entry:

- caller input must be semantic (task/Work identity, role/intent, observed ToolSurfaces where platform observation requires them), not a raw hosted runtime envelope;
- runtime provider semantics must delegate to existing `runtime_provider_adapter` / Agent runtime contracts;
- command/handle validation must delegate to existing Agent Cycle/handle contracts;
- no new marker, schema, authority, persistence, workflow, or lifecycle state may be added;
- issue-bus plumbing duplicated from R3/R4/R5 must be reduced or explicitly isolated as temporary debt with a concrete R7 deletion target;
- tests must cover fresh entry, valid reuse/re-entry, incomplete observation -> UNKNOWN/BLOCKED, stale/invalid handle, and absence of unintended writes;
- implementation size is not a gate by itself, but every protocol-handling block must have a named existing owner or retirement target. Unowned compatibility code blocks promotion.

PR #307 adds the complementary surface guard: the public paved API must not regress into requiring hosted issue/marker/schema/runtime-envelope/authority-head/lease-binding/comment/cycle/context identities from normal callers.

## R6 live-executor gate

A black-box agent starting from semantic Work/task intent must be able to reach entry, ownership, authoring, candidate/CI, Delivery and safe finalization without knowing issue #145, bus markers, protocol versions, authority-head CAS, lease IDs/binding hashes, or result-comment search mechanics. Negative canaries must remain fail-closed.

The public-surface half of this gate is integrated through PR #307. PRs #309-#310 establish the current live disposition: **`BLOCKED_EXECUTION_SURFACE`**.

The block is specifically a missing proven executable binding between the configured provider-backed ToolSurface and the repository's public paved Python façade. ToolSurface/provider observation already exists; that is not equivalent to executing the façade through that provider.

R6 must remain blocked when any proposed solution requires:

- provisioning shell `gh`, raw DNS/HTTP or local git as a paved fallback;
- manually driving legacy issue-comment markers as the black-box caller;
- a canary-only workflow or Journey executor;
- a new authority/session/store;
- a second lifecycle;
- permanent dual-write/dual-read reconciliation.

If a natural provider-backed executor surface appears, the positive + negative R6 traversal is the first use. If a repository-level executor seam must be created, it is admissible only under the protocol-containment rule above and the concrete plan in `docs/architecture/r6-executor-seam-retirement-plan.md`.

## Promotion gates

### R6 — prove the paved path

R6 completes only when the live positive + negative traversal succeeds through a real provider-backed executor surface while preserving canonical guards, receipts, CAS, leases and readbacks.

Surface/unit success, provider observation alone, CI execution alone, or manual legacy-bus traversal do not count as promotion evidence.

### R7 — promote and demote

Promotion is allowed only after R6 passes both positive and negative live canaries. R7 must change the operational default: paved-path surfaces become the documented/default path and at least one legacy/manual surface becomes explicitly internal or recovery-only. Merely adding recommendations or another wrapper does not count as promotion.

R7 should also address bounded hosted-bus/CLI duplication only when the same migration window materially reduces at least two duplicate clients. A generic transport/compatibility framework is not an acceptable substitute for concrete subtraction.

### R8 — retire and delete

R8 must produce measurable subtraction. The first concrete subtraction retires `tools/agent_tools/journey_shadow.py` and its dedicated regression module after R6 live proof and R7 promotion; no replacement runtime surface is introduced. Further targets include removing duplicated hosted-bus plumbing where consolidation has replaced it, and deleting or privatizing legacy entry/request-construction/CLI-coupled paths that no normal-path caller needs.

If R8 cannot identify code/API surface that can be removed or demoted because the new layer depends permanently on both models, the migration thesis is considered unproven and must be re-evaluated rather than extended with more compatibility code.

## Abort / redesign triggers

Stop horizontal expansion and redesign before merging a recut if any of these becomes necessary:

- new mutable Journey authority/state/session;
- permanent dual source of truth or reconciliation loop;
- new generic compatibility framework to translate between paved and legacy models;
- a composer that must understand more hosted protocol versions/exceptions than the canonical host it wraps;
- safety guard weakening to make the paved path convenient;
- inability to name what old normal-path surface a new permanent module will supersede;
- a provider/executor bridge with no non-canary consumer and no same-window legacy reduction;
- two consecutive recuts that add permanent orchestration surface without making any legacy surface eligible for demotion.

## Accounting rule

Track migration surface in three buckets: permanent safety primitives, temporary migration scaffolding, and public normal-path API. Additive LOC is not itself a failure. The failure condition is scaffolding without a death condition or growth of the public normal-path API in both old and new forms.

For every R6-R8 PR, the description/review must state: what is added, what old knowledge/API it supersedes, its promotion evidence, what becomes removable/demotable, and whether the net public normal-path surface shrinks, stays flat temporarily, or grows with an explicit deadline.

## Immediate plan

1. Treat PR #306 as the promoted R6a implementation and PR #307 as the completed R6 public-surface proof.
2. Treat PRs #309-#310 as the current live-executor/provider control point; do not reopen `gh`/DNS provisioning as a paved-path solution.
3. Keep R7 blocked until a genuine provider-backed public-façade positive + negative traversal exists.
4. Investigate only natural runtime/provider executor seams. Do not add architecture solely to execute the canary.
5. If a shared executor seam is eventually justified, require same-window demotion/reduction of at least two duplicated hosted/CLI clients and preserve all existing primitive guarantees.
6. If live traversal exposes a genuine semantic gap, repair it under this contract and preserve UNKNOWN/BLOCKED rather than adding Journey state or compatibility shims.
7. After R6 passes, perform R7 promotion with an actual default-path change and at least one legacy/manual demotion.
8. Execute R8 as a deletion/demotion milestone, not optional cleanup. `journey_shadow`, duplicated hosted I/O, CLI-coupled defaults and superseded request-construction surfaces are explicit subtraction candidates.

The migration remains successful only if the final architecture has one normal operational model: paved semantic intent over canonical primitives, with manual hosted/CLI protocol mechanics retained only where recovery/debugging genuinely requires them.
