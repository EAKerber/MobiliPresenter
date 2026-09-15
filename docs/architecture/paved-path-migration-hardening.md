# Paved-path migration hardening

Status: migration control gate before continuing R6a.

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

## Protocol containment rule

The hosted issue bus is infrastructure, not Journey semantics. Journey/paved-path composers must not independently evolve copies of comment pagination, marker parsing, request/result correlation, protocol-version selection, or provider response normalization. Existing shared validators/builders such as `hosted_handle_requests.py`, `hosted_agent_cycle.py`, `hosted_cycle_handle.py`, `runtime_provider_adapter.py`, and canonical host modules remain the semantic owners.

If a missing transport seam is proven, consolidation is allowed only when all of the following are true:

1. it lives below Journey/paved-path semantics;
2. it introduces no authority or persistence;
3. at least two existing duplicated transport implementations are deleted or materially reduced in the same migration window;
4. callers retain the canonical primitive contracts and fail-closed dispositions;
5. it does not become a generic compatibility framework.

## Replacement and retirement map

| Scaffolding / paved surface | Superseded normal-path knowledge | Promotion evidence | Retirement / demotion target |
| --- | --- | --- | --- |
| JourneyProjection | manually interpreting Project/Work/Git/re-entry authorities to know where the agent is | projection agrees with observed outcomes and never creates false PASS | keep projection only if it remains the single public read model; remove redundant manual interpretation helpers |
| `journey_shadow` | none; it is measurement scaffolding | R6 black-box canaries show stable agreement including negative cases | delete after promotion confidence is established |
| `ensure_ownership` | manual acquire/release/re-entry request construction and CAS discovery | repeated valid reuse/acquire/release/expired cases, zero false ownership | manual lease choreography becomes internal/recovery-only |
| authoring composition | manual GitMutationPlan/CAS/lease plumbing for normal edits | black-box authoring succeeds through existing Agent Tool with complete readback | direct canonical mutation construction becomes internal/recovery-only |
| delivery/finalization composition | manual Delivery request assembly and post-merge ordering discovery | governed merge + Work/lease/cycle finalization canary succeeds | manual Delivery request assembly becomes internal/recovery-only |
| R6/R6a entry composition | issue number, markers, HostedAgentCycleCommand versions, begin-result search, runtime envelope mechanics | task/Work intent obtains or reuses a valid AgentCycleHandle without caller protocol knowledge | manual Agent Cycle bus entry becomes internal/recovery-only |

## R6a hardening gate

The current partial `journey_entry.py` must not be promoted merely because it works. Before PR/merge:

- caller input must be semantic (task/Work identity, role/intent, observed ToolSurfaces where platform observation requires them), not a raw hosted runtime envelope;
- runtime provider semantics must delegate to existing `runtime_provider_adapter` / Agent runtime contracts;
- command/handle validation must delegate to existing Agent Cycle/handle contracts;
- no new marker, schema, authority, persistence, workflow, or lifecycle state may be added;
- issue-bus plumbing duplicated from R3/R4/R5 must be reduced or explicitly isolated as temporary debt with a concrete R7 deletion target;
- tests must cover fresh entry, valid reuse/re-entry, incomplete observation -> UNKNOWN/BLOCKED, stale/invalid handle, and absence of unintended writes;
- implementation size is not a gate by itself, but every protocol-handling block must have a named existing owner or retirement target. Unowned compatibility code blocks promotion.

## Promotion gates

### R6 — prove the paved path

A black-box agent starting from semantic Work/task intent must be able to reach entry, ownership, authoring, candidate/CI, Delivery and safe finalization without knowing issue #145, bus markers, protocol versions, authority-head CAS, lease IDs/binding hashes, or result-comment search mechanics. Negative canaries must remain fail-closed.

R6 is blocked if completing the path requires a new Journey authority/session/store, a second lifecycle, or permanent dual-write/dual-read reconciliation.

### R7 — promote and demote

Promotion is allowed only after R6 passes both positive and negative canaries. R7 must change the operational default: paved-path surfaces become the documented/default path and at least one legacy/manual surface becomes explicitly internal or recovery-only. Merely adding recommendations or another wrapper does not count as promotion.

### R8 — retire and delete

R8 must produce measurable subtraction. Required targets include deleting shadow instrumentation once no longer needed, removing duplicated hosted-bus plumbing where consolidation has replaced it, and deleting or privatizing legacy entry/request-construction paths that no normal-path caller needs.

If R8 cannot identify code/API surface that can be removed or demoted because the new layer depends permanently on both models, the migration thesis is considered unproven and must be re-evaluated rather than extended with more compatibility code.

## Abort / redesign triggers

Stop horizontal expansion and redesign before merging a recut if any of these becomes necessary:

- new mutable Journey authority/state/session;
- permanent dual source of truth or reconciliation loop;
- new generic compatibility framework to translate between paved and legacy models;
- a composer that must understand more hosted protocol versions/exceptions than the canonical host it wraps;
- safety guard weakening to make the paved path convenient;
- inability to name what old normal-path surface a new permanent module will supersede;
- two consecutive recuts that add permanent orchestration surface without making any legacy surface eligible for demotion.

## Accounting rule

Track migration surface in three buckets: permanent safety primitives, temporary migration scaffolding, and public normal-path API. Additive LOC is not itself a failure. The failure condition is scaffolding without a death condition or growth of the public normal-path API in both old and new forms.

For every R6-R8 PR, the description/review must state: what is added, what old knowledge/API it supersedes, its promotion evidence, what becomes removable/demotable, and whether the net public normal-path surface shrinks, stays flat temporarily, or grows with an explicit deadline.

## Immediate plan

1. Freeze new Journey modules while R6a is hardened.
2. Reduce/delegate R6a before adding tests around accidental protocol duplication.
3. Use R6a to obtain/reuse the handle from semantic inputs and run the R6 black-box canary.
4. Only after R6 evidence, perform R7 promotion; do not add another convenience layer.
5. Execute R8 as a deletion/demotion milestone, not optional cleanup.

The migration remains successful only if the final architecture has one normal operational model: paved semantic intent over canonical primitives, with manual hosted protocol mechanics retained only where recovery/debugging genuinely requires them.
