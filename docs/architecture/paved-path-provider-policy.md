# Paved-path provider policy

Status: **normative migration addendum for R6-R8**. This document refines the provider/executor interpretation of `paved-path-migration-hardening.md` and the R6 live-executor checkpoint without changing the current `BLOCKED_EXECUTION_SURFACE` disposition.

## Provider policy

The normal paved path must use the canonical provider-backed GitHub surface represented by `github-connector-tools` / the configured GitHub connector/API ToolSurface.

`gh-api-cli`, shell `gh`, raw GitHub DNS access, ad-hoc HTTP, and local git transport are **not supported paved-path providers or fallbacks for R6 promotion**. Their absence is not a migration defect and must not be repaired merely to make a black-box canary executable.

If the canonical provider-backed surface cannot be observed or bound, the existing fail-closed disposition applies (`UNKNOWN` / `BLOCKED` as defined by the owning primitive). Do not fall back to shell/CLI transport.

The semantic registry may continue to list `gh-api-cli` while legacy/recovery callers still exist. That is explicit migration debt, not an endorsed normal-path provider. CLI-coupled defaults such as `GhApiTransport` are R7/R8 demotion/removal candidates once black-box evidence proves the provider-backed paved path.

## Provider is not executor

PR #309 correctly preserved R6 as `BLOCKED_EXECUTION_SURFACE`, but missing raw DNS or `gh` must not be interpreted as the blocker to solve.

The GitHub connector/API already supplies a provider-backed transport surface. What remains unproven is a **black-box executor surface that invokes the public paved façade while binding the real configured ToolSurfaces**. Connector availability proves that GitHub can be observed/mutated through the configured provider; it does not, by itself, prove that the repository's Python façade has been executed live through that provider.

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

Continue to preserve `BLOCKED_EXECUTION_SURFACE` until a genuine provider-backed public-façade run exists. The next technical investigation should target the executor seam, not CLI provisioning. R7 remains ineligible until the live R6 evidence exists; R8 remains the mandatory subtraction/demotion phase.