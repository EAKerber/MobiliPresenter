# OperationalSemantics 0.3 — typed inventory

Status: **M10-OS1A inventory contract implemented; AgentSemanticBrief runtime
remains M10-OS1B scope**.

## Purpose

OperationalSemantics 0.3 is the closed, read-only semantic map used to discover
current operational components and provider-neutral capabilities. It replaces
the 0.2 registry without implicit compatibility and adds the descriptors needed
by the future AgentSemanticBrief.

The registry remains a repository contract. It is not an authority, runtime
availability claim, assignment source, permission surface, or writer.

## Typed inventory

The 0.3 registry separates:

- repository components;
- managed mutable authorities;
- immutable resources and structural contracts;
- provider-neutral logical capabilities;
- static provider profiles;
- concrete tool surfaces;
- typed relevance facets;
- coverage policy and justified exclusions.

Capability descriptors use typed facets for role, DeclaredIntent class,
lifecycle phase, operation, object, risk and required scope. Free tags do not
participate in eligibility.

Each capability also declares one availability class:

- `runtime-observed`: availability is resolved from normalized provider
  observations;
- `repository-static`: the implementation is covered by the checked
  repository inventory;
- `contextual`: availability depends on authority, scope, plan, lease or
  another operation-specific precondition.

Only `runtime-observed` descriptors are evaluated by
`RuntimeCapabilityInspection 0.1`. Contextual and repository-static entries
must not be promoted to PASS merely because their modules exist.

## Provider and tool-surface boundary

A provider profile states which features can be observed for a carrier. It does
not claim that the provider is currently present. A tool surface binds a
provider to exact components, workflows or connected entrypoints and to the
logical capabilities they expose.

`tools/runtime_capabilities.py` now reads provider profiles and
`runtime-observed` capability requirements from the registry. The previous
hard-coded semantic inventory is removed. Alternative providers remain
acceptable only when every feature required by that provider descriptor was
observed; one absent provider never erases the logical capability.

## EcosystemMaxim catalog

`ops/semantics/maxims.json` is the versioned source for the initial eight
EcosystemMaxims. Each entry carries:

- stable id and statement;
- justification and operational question;
- misread risk;
- application facets and related contracts;
- editorial owner;
- replacement, review or death condition.

The catalog and every item are mechanically bounded by:

```text
semanticAuthority = false
authorizesMutation = false
overridesContract = false
```

The catalog is complete for this slice, but contextual selection of at most
three maxims is deferred to M10-OS1B.

## Deterministic coverage

`tools.semantics.coverage.build_inspection` scans the policy-declared Python
entrypoint and workflow globs and cross-checks them against:

- registered components and Python tool-surface bindings;
- workflow bindings or explicit justified exclusions;
- every structural schema and registered contract;
- runtime capability descriptors;
- provider profiles consumed by runtime discovery;
- the registry's referential and writer invariants.

The resulting `OperationalSemanticsCoverage 0.1` is deterministic,
hash-bound, read-only, non-authoritative and non-mutating. Missing entrypoints,
bindings, schemas or runtime descriptors are explicit findings. Silence is not
coverage.

The two product CI workflows are explicit exclusions because this slice maps
operational capabilities rather than product-domain validation. Each exclusion
has an owner, rationale and death condition; neither is silently omitted.

## Boundaries preserved

M10-OS1A does not:

- generate or persist an AgentSemanticBrief;
- select maxims for a role or intent;
- implement CAPABILITY_DISCOVERY_FRESHNESS_GUARD;
- alter Routine Layer;
- create a semantic authority or writer;
- change ProjectState or declare M10 closed;
- admit M11, Scheduled Tasks, PCS-01B or product work.

M10-OS1B must consume this inventory to implement deterministic capability
projection, brief hashing, stale/tamper rejection and additive bootstrap
discovery before the M10 checkpoint can close.
