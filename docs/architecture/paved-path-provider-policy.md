# Paved-path provider policy

Status: **normative migration addendum for R6-R8**. This document refines the provider/executor interpretation of `paved-path-migration-hardening.md`. PR #315 implements the provider-boundary retirement in the R6 recut; that implementation is a prerequisite, not R6 promotion. The live positive + negative R6 traversal remains required.

## Provider policy

The normal paved path must use the canonical provider-backed GitHub surface represented by `github-connector-tools` / the configured GitHub connector/API ToolSurface.

`gh-api-cli`, shell `gh`, raw GitHub DNS access, ad-hoc HTTP, and local git transport are **not supported paved-path providers or fallbacks for R6 promotion**. Their absence is not a migration defect and must not be repaired merely to make a black-box canary executable.

If the canonical provider-backed surface cannot be observed or bound, the existing fail-closed disposition applies (`UNKNOWN` / `BLOCKED` as defined by the owning primitive). Do not fall back to shell/CLI transport.

The semantic registry may continue to list `gh-api-cli` while explicit legacy/recovery adapters still exist. That is migration debt, not an endorsed normal-path provider. As of the PR #315 recut, paved semantic/core boundaries no longer choose `GhApiTransport` implicitly; concrete construction is confined to explicit host/CLI/live-sensor adapters that own the environment-specific GitHub carrier. Re-entry observation requires injection and the outer `tools/agent.py status` CLI selects its carrier explicitly. Hosted Agent Cycle close likewise injects its carrier into lifecycle/obligation inspection, while `project_sensors.observe_coordination(live=True)` and `project_sensors.observe_continuations_live()` are classified as live-environment sensor adapters rather than semantic/core fallbacks.

## Provider is not executor

PR #309 correctly preserved R6 as `BLOCKED_EXECUTION_SURFACE`, but missing raw DNS or `gh` must not be interpreted as the blocker to solve.

The GitHub connector/API supplies the provider-backed host surface used during the PR #315 governed mutations, while repository semantic/core functions now require an injected provider and fail closed when it is absent. What remains unproven is the **black-box public paved traversal from semantic intent through the configured host/provider surface and safe finalization**. Successful governed repository mutations prove the host/provider carrier exists; they do not, by themselves, count as the R6 public-façade canary.

Therefore:

- R6 remains blocked until the public façade performs the required positive and negative live traversal through real provider-backed ToolSurfaces;
- no `gh` installation, DNS workaround, shell fallback, canary-only workflow, Journey runner, alternate authority, or compatibility façade may be introduced to force that gate green;
- if an executor seam is genuinely missing, it must reuse the existing runtime/provider contracts below Journey semantics and satisfy the existing hardening rule: no new authority/persistence and concrete reduction/demotion of duplicated protocol surface in the same migration window;
- manually driving the legacy issue-comment bus does not count as black-box paved-path evidence.

This addendum supersedes any interpretation of the R6 live-executor audit that treats availability of `gh`, raw DNS, or local git transport as a promotion requirement. It does **not** weaken the required live evidence or change the current blocked disposition.

## Golden target for agent experience

The target experience is the same class of behavior already seen in low-friction paths such as branch hygiene and other provider-backed operations that happen invisibly: the agent asks for the semantic service and receives it without needing to understand how the service is routed internally.

The implementation may retain strong internal guards, receipts, CAS, leases, canonical writers and readbacks. Those mechanisms should not become mandatory cognitive inputs for normal-path callers.

## Future QoL: "windows into the kitchen"

After the R6-R8 migration cycle is fully closed, consider a separate quality-of-life improvement that makes invisible execution easy to inspect on demand.

The goal is not to expose implementation mechanics as required workflow. It is to let an agent or operator answer questions such as "which provider/path was used?", "which guards ran?", or "which canonical structures participated?" without reconstructing the process from scattered evidence.

Any future implementation should be:

- read-only and derived from existing receipts/proofs/authorities;
- optional and on-demand;
- non-authoritative and non-blocking for normal work;
- free of new lifecycle/state requirements;
- designed as observability of the service, not another service-selection API.

This concept is explicitly deferred until the current migration is fully closed. It is **not** an R6, R7, or R8 acceptance requirement.

## Immediate implication

The provider-boundary retirement should be qualified and integrated without reopening CLI provisioning or inventing an in-process connector bridge. After integration, rerun the genuine provider-backed public-façade positive + negative R6 traversal. Until that live canary exists, R6 remains fail-closed and R7 remains ineligible. R8 remains the mandatory subtraction/demotion phase.