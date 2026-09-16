# Paved-path migration status — 2026-09-16

Status: **R6a, the R6 public-surface proof, the live-executor audit and the provider-policy hardening are integrated. R6 promotion remains `BLOCKED_EXECUTION_SURFACE` until a genuine provider-backed positive + negative traversal executes through the public paved façade.**

This is a narrative checkpoint only. Work, Coordination, Agent Cycle, Delivery, CI and Project state remain owned by their canonical structured authorities.

## Current baseline

- `main`: `cf79c0a60c952d4b2cd19e759cdc1d161b0851bf`
- PR #301: migration hardening and retirement gates merged
- PR #303: hardening made part of permanent agent bootstrap rules
- PR #304: clean R6a recut plan merged
- PR #305: post-hardening status checkpoint merged
- PR #306: clean R6a semantic hosted-entry recut merged
- PR #307: R6 black-box public-surface guard merged
- PR #308: paved-path status consolidated through the R6 surface-proof boundary
- PR #309: live-executor audit persisted `BLOCKED_EXECUTION_SURFACE`
- PR #310: provider policy clarified that configured GitHub ToolSurfaces, not `gh`/DNS/shell fallbacks, are the normal paved-path provider model
- open PRs at this checkpoint: none

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
| R6 executor audit / PR #309 | exact blocked disposition without fabricated executor | prevents legacy bus mechanics or CI carriers from being mislabeled as black-box proof | no R7 promotion until real live traversal |
| Provider policy / PR #310 | provider/executor distinction made normative | removes `gh`, raw DNS/HTTP and local git as presumed paved-path requirements | CLI-coupled transport remains explicit R7/R8 debt |

## What R6a and the public-surface proof establish

The normal entry caller can provide semantic Work/task intent plus observed ToolSurface inventory and does not need to construct a raw hosted runtime envelope or select an Agent Cycle command version.

The merged composer:

- emits only the current V0.4 begin contract;
- delegates runtime validation to the canonical Agent Cycle runtime validator;
- delegates handle decoding to `hosted_cycle_handle`;
- preserves UNKNOWN/BLOCKED fail-closed behavior;
- reuses exact pending/ready requests idempotently;
- introduces no Journey authority, session, store, workflow, marker or protocol version.

The R6 surface guard further proves that normal-path entry, ownership, authoring, delivery and finalization do not require callers to provide issue/marker/schema/runtime-envelope/authority-head/lease-binding/comment/cycle/context identities. Incomplete ToolSurface observation returns `UNKNOWN` before transport writes.

This is real API/cognitive compression, but it is **not** live end-to-end promotion evidence.

## Remaining R6 gate — live traversal

Still required: a black-box positive and negative traversal starting from semantic task/Work intent and passing through:

`entry -> ownership -> authoring -> candidate/CI -> Delivery -> COMPLETE_WORK -> RELEASE_OWNERSHIP -> CLOSE_AGENT_CYCLE`

The traversal must not require caller knowledge of issue #145, bus markers, protocol versions, authority-head CAS, lease/binding identities, comment-result search mechanics, raw runtime envelopes, or manually predicted cycle/context identities.

Negative cases must remain fail-closed and must prove absence of unintended writes where applicable.

R6 is not complete until this evidence exists. Surface/unit success must not be promoted into an R7 claim.

## Executor/provider seam audit — post-PR #310

Disposition remains **`BLOCKED_EXECUTION_SURFACE`**. The blocker is now characterized more precisely than “local GitHub access is unavailable.”

There are two distinct halves of the runtime seam:

1. **ToolSurface observation and provider semantics — present.** `tools/agent.py` accepts external ToolSurface observations and `runtime_provider_adapter.observations_from_tool_surfaces()` converts them into canonical provider observations without creating authority.
2. **Executable provider binding — not proven.** The public paved Python composers need a concrete `Transport.request()` implementation to perform GitHub operations. `journey_entry.compose_entry()` supports dependency injection through `transport=`, but its repository-local default is still `GhApiTransport()`, backed by shell `gh`.

The configured ChatGPT GitHub connector/API ToolSurface can observe and mutate GitHub resources from the hosting platform, but the repository's Python process has no current binding that invokes that platform ToolSurface as a `Transport.request()` implementation. Provider availability therefore does not equal an executable Python transport binding.

This distinction matters:

- provisioning `gh`, raw DNS/HTTP or local git merely to make R6 executable would violate `paved-path-provider-policy.md`;
- manually driving the existing hosted issue-comment markers would invalidate the black-box proof because the caller would again know the legacy choreography;
- `Agent Ops` and the hosted carrier workflows are useful qualification/execution machinery but are not a black-box executor of the public paved façade;
- adding a canary-only workflow, Journey runner, alternate authority or compatibility façade would manufacture evidence rather than prove the intended path.

No legitimate repository runtime change is currently identified that closes this seam without adding architecture specifically for the canary. Therefore the correct action is to preserve the blocked disposition, not force a PASS.

A future executor seam is admissible only if it is a genuine runtime/provider capability below Journey semantics, introduces no authority or persistence, preserves canonical primitive contracts and fail-closed behavior, and in the same migration window materially reduces/demotes at least two duplicated hosted/CLI transport clients. A bridge that only makes the R6 canary runnable is not sufficient justification.

See `docs/architecture/paved-path-provider-policy.md` and `docs/architecture/r6-executor-seam-retirement-plan.md`.

## Existing workflow audit

The repository workflow inventory was rechecked at this checkpoint:

- `Agent Ops` can checkout and execute repository Python, tests, semantic checks, Project Machine inspection and handoff evidence, but it does not expose the live semantic paved traversal as an existing service;
- `Hosted Agent Cycle`, `Hosted Agent Tool`, `Hosted Agent Write Lease`, Remote Canonical Execution and related carriers remain driven by the legacy hosted protocol surface;
- reusing those markers manually as the R6 caller would test the legacy protocol rather than the public paved façade.

Therefore the prior live-executor conclusion remains valid after PR #310.

## Remaining protocol debt

R6a still contains hosted issue discovery, comment pagination and result correlation. Ownership and other paved composers also retain local hosted-bus mechanics. `GhApiTransport` remains a CLI-coupled concrete transport used by legacy/recovery paths. These are accepted only as bounded migration debt.

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
| CLI-coupled defaults | shell `gh` as implicit execution transport | remove from normal path; retain only explicit recovery use where justified |
| duplicated hosted-bus I/O | repeated issue discovery/comment submission/result correlation | consolidate only if at least two clients are materially reduced in the same migration window; otherwise keep recovery-scoped and explicit |

## Frankenstein abort conditions

Stop and redesign rather than extend the paved layer if any next recut requires:

- a new mutable Journey authority/state/session/store;
- permanent dual-read or dual-write reconciliation;
- a second lifecycle or merge/mutation primitive;
- weakening UNKNOWN/BLOCKED or existing safety guards;
- a generic compatibility framework between paved and legacy models;
- a new permanent composer without a named old normal-path surface that becomes removable or demotable;
- an executor/transport bridge whose only consumer is the R6 canary;
- continued hosted-protocol duplication without a concrete R7 consolidation/demotion target;
- two consecutive recuts that add permanent orchestration without making any legacy surface eligible for demotion.

## Immediate next steps

1. Keep R7 blocked while `BLOCKED_EXECUTION_SURFACE` remains unresolved.
2. Do not provision `gh`, raw DNS/HTTP, local git, a canary workflow or a Journey executor merely to make R6 pass.
3. Treat the next technical investigation as runtime/provider seam discovery: look for a naturally available platform hook that can execute the existing public façade while binding the configured GitHub ToolSurface.
4. If a real shared executor/transport seam becomes available, require it to reduce/demote at least two existing duplicate/CLI clients in the same migration window; otherwise leave the architecture unchanged.
5. When such a natural execution surface exists, run the positive + negative R6 traversal before any R7 work.
6. Record exact traversal evidence and negative-write assertions here and in the R6 accounting.
7. Only after live R6 evidence succeeds, begin R7 promotion. R7 must change the operational default and demote at least one manual/legacy surface in the same migration window.
8. R8 remains mandatory subtraction: delete `journey_shadow` when justified and remove/private duplicated, CLI-coupled or superseded normal-path protocol surfaces.

The migration thesis remains: **one normal operational model — semantic paved intent over canonical primitives — with hosted protocol mechanics retained only where recovery/debugging genuinely requires them.**
