# Paved-path migration status — 2026-09-16

Status: **R6a and the R6 black-box surface proof are integrated. R6 live promotion remains BLOCKED_EXECUTION_SURFACE until positive + negative traversal can run through the public paved façade without falling back to legacy hosted-bus choreography.**

This is a narrative checkpoint only. Work, Coordination, Agent Cycle, Delivery, CI and Project state remain owned by their canonical structured authorities.

## Current baseline

- `main`: `61cc1defd3cba8f8f4367a5d0cccde668108b271`
- PR #301: migration hardening and retirement gates merged
- PR #303: hardening made part of permanent agent bootstrap rules
- PR #304: clean R6a recut plan merged
- PR #305: post-hardening status checkpoint merged
- PR #306: clean R6a semantic hosted-entry recut merged
- PR #307: R6 black-box surface guard and documentation checkpoint merged
- PR #308: paved-path status consolidated through the R6 proof boundary

The historical `work/operations/r6a-hosted-entry-composition` prototype remains evidence only. The promoted implementation came from the clean recut and did not inherit the prototype branch.

## Migration progression

| Recut | Integrated outcome | Normal-path knowledge reduced | Retirement implication |
| --- | --- | --- | --- |
| R1 / PR #296 | read-only `JourneyProjection` | manual multi-authority interpretation of stage/disposition | projection can become the single public semantic read model |
| R2 / PR #297 | entry/re-entry shadow equivalence | none; measurement only | `journey_shadow` is temporary and must die after sufficient evidence |
| R3 / PR #298 | `ensure_ownership` composition | manual lease/CAS/binding request construction | manual lease choreography becomes internal/recovery-only after promotion |
| R4 / PR #299 | authoring composition over Agent Tool | direct Git mutation/CAS/ownership plumbing | direct canonical request construction becomes internal/recovery-only |
| R5 / PR #300 | Delivery request composition + finalization projection | manual Delivery precondition assembly and finalization-order discovery | manual Delivery request assembly becomes internal/recovery-only |
| Hardening / PRs #301-#305 | explicit promotion/retirement contract | removes ambiguity about additive scaffolding vs permanent architecture | R7/R8 are mandatory migration phases, not optional cleanup |
| R6a / PR #306 | semantic hosted-entry composer | raw runtime envelope, command-version choice, caller begin-identity construction | direct Agent Cycle bus entry becomes internal/recovery-only after R6 proof |
| R6 surface / PR #307 | public surface guard + fail-closed negative entry canary | caller protocol identities are no longer accepted by the paved surfaces | establishes cognitive/API compression precondition for live proof |

## What R6a now proves

The normal entry caller can provide semantic Work/task intent plus observed ToolSurface inventory and does not need to construct a raw hosted runtime envelope or select an Agent Cycle command version.

The merged composer:

- emits only the current V0.4 begin contract;
- delegates runtime validation to the canonical Agent Cycle runtime validator;
- delegates handle decoding to `hosted_cycle_handle`;
- preserves UNKNOWN/BLOCKED fail-closed behavior;
- reuses exact pending/ready requests idempotently;
- introduces no Journey authority, session, store, workflow, marker or protocol version.

This makes the old normal-path knowledge of raw `runtimeEnvironment`, explicit command-version selection, caller-side begin identity construction and manual handle decoding eligible for R7 demotion.

## What the R6 surface proof now proves

PR #307 is integrated and qualified on the normal repository gates. It added no production runtime module; it added a guard over the public paved surface and advanced this checkpoint.

The guard asserts that normal-path entry, ownership, authoring, delivery and finalization do not require callers to supply hosted protocol identities such as:

- issue numbers or bus markers;
- command/schema versions;
- raw runtime envelopes;
- authority-head CAS values;
- lease IDs or binding hashes;
- result-comment IDs;
- cycle IDs or context hashes.

The negative entry canary also requires incomplete ToolSurface observation to return `UNKNOWN` before transport writes.

This is meaningful proof of API/cognitive compression, but it is **not** live end-to-end promotion evidence by itself.

## Remaining R6 gate — live traversal

Still required: a black-box positive and negative traversal starting from semantic task/Work intent and passing through:

`entry -> ownership -> authoring -> candidate/CI -> Delivery -> COMPLETE_WORK -> RELEASE_OWNERSHIP -> CLOSE_AGENT_CYCLE`

The traversal must not require caller knowledge of issue #145, markers, protocol versions, authority-head CAS, lease/binding identities, comment-result search mechanics, raw runtime envelopes, or manually predicted cycle/context identities.

Negative cases must remain fail-closed and must prove absence of unintended writes where applicable.

R6 is not complete until this evidence exists. Surface/unit success must not be promoted into an R7 claim.

### Live-executor audit — 2026-09-16

Disposition: **BLOCKED_EXECUTION_SURFACE**. This is neither PASS nor evidence that the paved semantic API is defective.

The current ChatGPT runtime cannot execute the repository checkout directly because outbound GitHub DNS is unavailable in the local container. The GitHub connector can observe and mutate repository resources, but it is not a Python execution environment for `tools/agent.py`.

The existing repository runners were audited rather than extending the architecture to manufacture a canary:

- `Agent Ops` exposes CI/inspection through `workflow_dispatch`, but does not execute a live paved traversal;
- `Hosted Agent Cycle`, `Hosted Agent Tool`, `Hosted Agent Write Lease`, Remote Canonical Execution and related hosted carriers are driven by the legacy issue-comment bus/markers;
- using those marker protocols manually as the R6 black-box caller would invalidate the proof, because the caller would again need the exact hosted choreography the paved path exists to hide;
- the current workflow inventory contains no existing semantic `tools/agent.py` / paved-journey executor that can be invoked from this runtime without crossing back into that legacy protocol surface.

Therefore no canary-only workflow, Journey runner, compatibility façade, or alternate authority will be introduced to force the gate green. The live positive and negative canaries remain pending until a naturally available execution surface can run the public façade with repository/GitHub access. Once such a surface is available, the first action is to execute both canaries as specified above; no R7 work is eligible before that evidence exists.

This block is itself hardening evidence: the migration contract prevented a test-only orchestration layer and prevented legacy bus mechanics from being mislabeled as paved-path proof.

## Remaining protocol debt

R6a still contains hosted issue discovery, comment pagination and result correlation. Ownership and other paved composers also retain local hosted-bus mechanics. This is accepted only as bounded migration debt.

The hardening rule remains active: a shared transport seam may be introduced only when the same migration window materially reduces at least two duplicate clients. No generic compatibility framework is permitted.

The lifecycle discontinuity discovered during R6a also remains engine/recovery behavior rather than Journey state: after an expired write binding, the proven safe recovery was `release expired binding -> close old cycle -> begin new cycle for the same Work -> acquire new ownership`. Do not hide this by creating a persistent Journey session model.

## Retirement ledger

| Paved surface | Old normal-path knowledge eligible for demotion after R6 | R7/R8 obligation |
| --- | --- | --- |
| JourneyProjection | manual multi-authority stage interpretation | make projection/default semantic view; demote redundant interpretation helpers |
| `journey_shadow` | none; measurement scaffolding | delete after stable positive + negative R6 equivalence evidence |
| `ensure_ownership` | manual lease request/CAS/binding construction | make manual lease choreography internal/recovery-only |
| authoring composition | direct canonical Git mutation/CAS plumbing | make direct request construction internal/recovery-only |
| delivery composition | manual Delivery precondition/request assembly | make manual Delivery request construction internal/recovery-only |
| R6a entry composition | issue/marker/version/runtime-envelope/begin identity mechanics | make direct Agent Cycle bus entry internal/recovery-only |
| duplicated hosted-bus I/O | repeated issue discovery/comment submission/result correlation | consolidate only if at least two clients are materially reduced in the same migration window; otherwise keep recovery-scoped and explicit |

## Frankenstein abort conditions

Stop and redesign rather than extend the paved layer if any next recut requires:

- a new mutable Journey authority/state/session/store;
- permanent dual-read or dual-write reconciliation;
- a second lifecycle or merge/mutation primitive;
- weakening UNKNOWN/BLOCKED or existing safety guards;
- a generic compatibility framework between paved and legacy models;
- a new permanent composer without a named old normal-path surface that becomes removable or demotable;
- continued hosted-protocol duplication without a concrete R7 consolidation/demotion target;
- two consecutive recuts that add permanent orchestration without making any legacy surface eligible for demotion.

## Immediate next steps

1. Keep R7 blocked while `BLOCKED_EXECUTION_SURFACE` remains unresolved; do not add runtime architecture solely to execute the canary.
2. When a naturally available runtime can invoke the existing public façade with GitHub/repository access, run the live positive + negative R6 traversal first.
3. Record exact traversal evidence and negative-write assertions here and in the R6 accounting.
4. If the traversal then exposes a genuine semantic gap, repair it under the hardening contract; do not add Journey state or compatibility layers to force green.
5. Only after the live R6 evidence succeeds, begin R7 promotion.
6. R7 must change the operational default and demote at least one manual/legacy surface in the same migration window. A documentation preference alone is not promotion.
7. During R7, consolidate hosted transport only if the same recut materially reduces at least two duplicated clients; otherwise demote duplicate paths to recovery scope rather than generalize them.
8. R8 remains mandatory subtraction: delete `journey_shadow` when justified and remove/private duplicated or superseded normal-path protocol surfaces.

The migration thesis remains: **one normal operational model — semantic paved intent over canonical primitives — with hosted protocol mechanics retained only where recovery/debugging genuinely requires them.**
