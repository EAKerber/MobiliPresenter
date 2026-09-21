# Paved-path migration status — 2026-09-16

Status: **R6 is live-proven through PR #328 and R7 is promoted through PR #329. R8 is active as measurable subtraction: `journey_shadow`, direct public `agent.py begin`, and duplicated hosted issue-bus I/O have been retired/demoted through PR #332; the current candidate removes the R6h/R6l historical second-close compatibility path without replacing it.**

This file is a narrative checkpoint only. Work, Coordination, Agent Cycle, Delivery, CI and Project state remain owned by their canonical structured authorities.

## Current baseline

- audited architecture baseline before the discovery annex: `main=4211732ae93097966dd74c2e1716270a43100212` after PR #311;
- reviewed documentation baseline after PR #312: `main=080e46f05dae6616827cfe1fcf72dd694c825397`;
- PR #301: migration hardening and retirement gates;
- PR #303: hardening included in permanent agent bootstrap rules;
- PR #304: clean R6a recut plan;
- PR #305: post-hardening status checkpoint;
- PR #306: clean R6a semantic hosted-entry recut;
- PR #307: R6 public-surface guard and fail-closed negative entry canary;
- PR #308: R6 migration checkpoint consolidation;
- PR #309: live-executor audit persisted `BLOCKED_EXECUTION_SURFACE`;
- PR #310: provider-first execution policy;
- PR #311: executor seam plus R7/R8 retirement plan;
- PR #312: provider-executor discovery checkpoint consolidation;
- repository-wide executor discovery annex: `docs/architecture/r6-provider-executor-discovery-audit-2026-09-16.md`.

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
| R6 surface / PR #307 | public surface guard + fail-closed negative entry canary | caller protocol identities are no longer accepted by paved surfaces | establishes cognitive/API compression precondition for live proof |
| R6 executor audit / PR #309 | exact blocked disposition without fabricated executor | prevents legacy bus mechanics or CI carriers from being mislabeled as black-box proof | no R7 promotion until real live traversal |
| Provider policy / PR #310 | provider/executor distinction made normative | removes `gh`, raw DNS/HTTP and local git as presumed paved-path requirements | CLI-coupled transport remains explicit R7/R8 debt |
| Executor plan / PR #311 | admissible executor seam and R7/R8 subtraction criteria made explicit | prevents a canary-only bridge from becoming permanent architecture | implementation requires a real platform hook and same-window subtraction |
| Discovery audit / post-#311 | repository-wide search found no in-process ChatGPT-connector binding | prevented speculative Journey expansion | historical observation retained; in-process binding is no longer an R6 requirement |
| Provider-boundary retirement / PR #315 | semantic/core paths require injected providers; named hosts select concrete GitHub transport explicitly | removes silent CLI/provider choice from the normal semantic path | qualify/integrate this recut, then rerun live R6 canaries |

## What is already proven

The normal entry caller can provide semantic Work/task intent plus observed ToolSurface inventory without constructing a raw hosted runtime envelope or selecting an Agent Cycle command version.

The integrated paved surfaces preserve the existing engine rather than reimplementing it:

- entry delegates to canonical Agent Cycle validation/handle decoding;
- ownership delegates to Coordination/write-lifecycle primitives;
- authoring delegates to Agent Tool/Remote Canonical Execution;
- delivery delegates to governed Delivery;
- finalization remains a projection of the safe Work -> release -> close order;
- UNKNOWN/BLOCKED remain fail-closed;
- no Journey authority, Journey session, Journey store, second lifecycle, new writer, new marker or new workflow was introduced.

The R6 public-surface guard also proves that normal callers are no longer required to provide issue/marker/schema/runtime-envelope/authority-head/lease-binding/comment/cycle/context identities. Incomplete ToolSurface observation blocks before unintended transport writes.

This is real cognitive/API compression. It is **not** yet a positive live end-to-end R6 traversal.

## Remaining R6 gate — live host/provider traversal

The remaining proof is a positive and negative black-box traversal beginning with semantic task/Work intent and traversing:

`entry -> ownership -> authoring -> candidate/CI -> Delivery -> COMPLETE_WORK -> RELEASE_OWNERSHIP -> CLOSE_AGENT_CYCLE`

The positive traversal must not require caller knowledge of issue #145, bus markers, protocol versions, authority-head CAS, lease/binding identities, result-comment search, raw runtime envelopes or manually predicted cycle/context identities.

The negative traversal must preserve `UNKNOWN`/`BLOCKED`, prove absence of unintended writes and must not silently fall back to shell/CLI/legacy choreography.

### Historical repository-side discovery result

The post-#311 discovery remains valid as an observation of repository process boundaries, but PR #315 supersedes the conclusion that an in-process ChatGPT-connector-to-`Transport.request()` binding is itself required. The hosting control plane may provide the configured ToolSurface outside repository Python; repository semantic/core code now expresses that boundary by requiring explicit provider injection instead of silently choosing a local CLI transport.

The post-#311 discovery inspected the current paved and transport seams plus repository-wide provider/executor terminology. The significant findings are:

1. `tools/runtime_provider_adapter.py` observes ToolSurfaces and produces canonical provider observations; it is read-only and does not invoke provider tools.
2. `tools/coordination_remote.py` already defines the narrow injectable `Transport.request()` / `ApiResponse` contract.
3. `tools/agent_tools/journey_entry.py` accepts `transport=` injection, but its repository-local concrete fallback remains `GhApiTransport`.
4. `tools/agent_tools/dispatch_host.py` also accepts injected transport and otherwise converges on `GhApiTransport`.
5. `ops/semantics/registry.json` describes provider-boundary concepts such as `GitHubBridge`, `ProviderRequest` and `GitHubToolCallRequest`, but no repository implementation was found that executes the configured ChatGPT GitHub ToolSurface from repository Python.
6. Searches across the current tree for connector/MCP/API-tool/provider-request/bridge/executor/invocation implementations revealed no second concrete provider-backed `Transport` implementation.

Therefore provider availability and provider observation are proven, but **provider execution inside the repository process is not**.

The detailed evidence is recorded in `docs/architecture/r6-provider-executor-discovery-audit-2026-09-16.md`.

## Current architectural judgment

The migration remains on the intended simplification path. PR #315 demonstrates the smaller boundary: semantic/core/guard code does not select a concrete provider, while explicit host/CLI/live-sensor adapters may do so at their environment edge. The remaining R6 question is no longer whether repository Python can invoke the ChatGPT connector in-process; it is whether the public paved façade can complete the required live positive + negative traversal through the configured host/provider service.

The correct response to any remaining live-canary gap is **not** to add another Journey module, provider state object, runner, compatibility layer or canary workflow. Such a bridge would turn temporary scaffolding into a second operational architecture and would violate the hardening contract.

A future executable provider seam is admissible only when a concrete runtime/platform hook exists and the recut can prove before implementation that:

- it lives below Journey semantics;
- it implements/reuses the existing `Transport` contract;
- no authority, lifecycle or persistence is added;
- canonical CAS/ownership/Agent Cycle/Delivery/readback guarantees remain authoritative;
- at least two existing duplicated or CLI-coupled transport clients are materially reduced, demoted or made recovery-only in the same migration window;
- the public caller surface does not grow;
- positive and negative R6 canaries remain live and inspectable.

If those conditions cannot be filled, remaining blocked is preferable to a false architectural PASS.

## Protocol and recovery debt retained deliberately

Hosted issue discovery, comment pagination and result correlation still exist in migration-era clients. `GhApiTransport` remains a concrete transport only at explicit host/CLI/live-sensor/recovery boundaries in the inventoried R6 path; semantic/core/guard fallbacks have been retired by PR #315. Re-entry, lifecycle close inspection, obligation inspection and Coordination guard proof now require provider injection; their outer host/CLI callers supply the carrier explicitly. `project_sensors.observe_coordination(live=True)` and `project_sensors.observe_continuations_live()` are retained as explicitly classified live-environment sensor adapters. The remaining hosted-protocol duplication is bounded debt, not the desired public model.

The lifecycle discontinuity discovered during R6a remains engine/recovery behavior: after an expired write binding, the proven safe recovery is `release expired binding -> close old cycle -> begin new cycle for the same Work -> acquire new ownership`. Do not hide it with persistent Journey session state.

## Retirement ledger

| Paved surface | Old normal-path knowledge eligible for demotion after R6 | R7/R8 obligation |
| --- | --- | --- |
| JourneyProjection | manual multi-authority stage interpretation | make projection/default semantic view; demote redundant interpretation helpers |
| `journey_shadow` | none; measurement scaffolding | **retired in R8** after R6 live proof + R7 promotion; no replacement |
| `ensure_ownership` | manual lease request/CAS/binding construction | make manual lease choreography internal/recovery-only |
| authoring composition | direct canonical Git mutation/CAS plumbing | make direct request construction internal/recovery-only |
| delivery composition | manual Delivery precondition/request assembly | make manual Delivery request construction internal/recovery-only |
| R6a entry composition | issue/marker/version/runtime-envelope/begin identity mechanics | direct `agent.py begin` retired from the public façade in R8; lower-level Hosted Agent Cycle carrier remains internal/recovery-only |
| CLI-coupled defaults | shell `gh` as implicit execution transport | remove from normal path; retain only explicit recovery use where justified |
| duplicated hosted-bus I/O | repeated issue discovery/comment submission/result correlation | consolidate only when at least two clients are materially reduced in the same window |

## Frankenstein abort conditions

Stop and redesign rather than extend the paved layer if a future recut requires:

- a new mutable Journey authority/state/session/store;
- permanent dual-read or dual-write reconciliation;
- a second lifecycle or merge/mutation primitive;
- weakening UNKNOWN/BLOCKED or existing safety guards;
- a generic compatibility framework between paved and legacy models;
- a permanent composer without a named old normal-path surface that becomes removable/demotable;
- an executor/transport bridge whose only consumer is the R6 canary;
- continued hosted-protocol duplication without a concrete R7 consolidation target;
- two consecutive recuts that add permanent orchestration without making legacy surface eligible for demotion.

## Governance note from this documentation pass

The discovery annex itself was accidentally created directly on `main` because the connector write omitted the intended branch field. The commit is documentation-only and introduces no runtime behavior, but the bypass is retained as explicit process evidence rather than hidden or rewritten destructively.

No force-reset or compensating direct-main mutation is authorized. The reviewed PR #312 restored the normal branch/PR path and should be used as the documentation baseline. The incident reinforces the migration principle that a semantic paved path should make the safe path the easy/default path rather than depend on every caller remembering low-level mutation parameters.

PR #315 contains a second, smaller governance incident: an erroneous test call created an empty `NOOP` file/commit without a valid lease, followed immediately by a compensating revert that restored the tree. The two commits remain in history intentionally. Integration review must treat this as process evidence, not erase it through destructive history rewriting; the final tree contains no `NOOP` artifact.

## Structured authority alignment after provider-boundary recut

The durable operational state is intentionally narrower than this narrative:

- `r6-provider-boundary-retirement`: **IN_PROGRESS**, PR #315; inventory and implementation are materially complete, while qualification/integration remain.
- `r6-black-box-paved-path-canary`: **WAITING** until the provider-boundary recut integrates; its positive + negative live proof remains mandatory.
- `r6b-finalization-composition`: **WAITING** on the same live execution proof.
- R7 remains ineligible until R6 has live promotion evidence.

Transient leases/cycle handles are operational coordination, not architectural state; consult Coordination/Agent Cycle authorities live rather than this document. The provider-boundary Work must be advanced only through its canonical continuation writer after exact-head evidence is observed.

## R6Q qualification checkpoint — 2026-09-18

R6Q reconciled the expired prior ownership without bypassing Coordination: the exact historical lease was released through `remote-canonical-execution` with PASS/readback, the old Agent Cycle closed PASS, and a fresh Work-bound Agent Cycle acquired new ownership before further branch mutation. The residual semantic/guard provider defaults identified during independent review were then moved to explicit host injection or fail-closed provider requirements.

A stacked R6c qualification run subsequently exposed one missed environment edge: `project_sensors.observe_continuations_live()` still constructed `GitHubContinuationAuthority()` without an explicit provider, so live Project Machine observation became `UNKNOWN / WORK_AUTHORITY_UNAVAILABLE` after the #315 fallback retirement. The fix injects `GhApiTransport` explicitly at that live-sensor boundary, matching the already-classified Coordination sensor edge. On functional head `ff463e7a695aacc5ad3e349ab290b28395204a7f`, Coordination Guard, Agent Ops and Supervisor Snapshot all materialized real jobs and completed PASS; source and readback Project Machine observation both completed successfully. This is exact functional evidence for the provider-boundary recut, while the final documentation head must retain equivalent exact-head CI before integration.

## Immediate next steps

1. Qualify and integrate the R8 historical close-compatibility retirement with exact-head Agent Ops, Coordination Guard and Supervisor Snapshot PASS.
2. Preserve R6g BLOCKED-terminal reconciliation as canonical safety behavior; do not delete it merely because it originated during migration.
3. Observe whether R6i-R6k non-interference evidence recurs for current-generation cycles. Retain it as a safety primitive if it does; otherwise treat the remaining recovery package as the next R8 deletion candidate.
4. Re-inventory remaining CLI/provider coupling only where another independently measurable deletion or demotion exists; do not create a provider manager or replacement compatibility layer.
5. Close R8 when every remaining layer has a unique justified responsibility and no migration-only productive path remains.

The migration thesis remains: **one normal operational model — semantic paved intent over canonical primitives — with provider/guard/receipt mechanics hidden from normal-path cognitive input and legacy protocol mechanics retained only where recovery/debugging genuinely requires them.**
