# OperationalSemantics 0.3 — typed inventory and contextual entry

Status: **M10-OS1A inventory implemented; M10-OS1B Agent Cycle Entry implemented on this branch; M10 remains open for OS1C closure**.

## Purpose

OperationalSemantics 0.3 is the closed, read-only semantic map used to discover current operational components and provider-neutral capabilities. The registry remains a repository contract. It is not an authority, runtime availability claim, assignment source, permission surface, or writer.

## Typed inventory

The 0.3 registry separates repository components, mutable authorities, resources/contracts, logical capabilities, provider profiles, tool surfaces, typed relevance facets and coverage policy.

Capability descriptors retain three availability classes:

- `runtime-observed`;
- `repository-static`;
- `contextual`.

Only runtime-observed descriptors are resolved by `RuntimeCapabilityInspection 0.1`. Repository-static availability requires complete semantic coverage. Contextual capabilities remain conditional until their operation-specific preconditions are satisfied.

## Explicit requirement policy

An intent facet says that a capability is semantically relevant to an intent; it does not by itself mean the capability is mandatory.

M10-OS1B therefore records required capabilities explicitly in the SemanticFoundations contract. Unlisted matching capabilities use the closed default `relevant`.

Required capabilities remain visible even when provider observation or scope is insufficient.

## Semantic context

`AgentSemanticContext 0.1` adds the typed fields needed to avoid a broad role+intent projection: role, declaredIntent, lifecyclePhase, objects[], operations[] and scope[]. Objects and operations are policy inputs, not authorization. Scope constrains availability but never grants authority.

## AgentSemanticBrief

`AgentSemanticBrief 0.1` composes `CapabilityRelevanceProjection 0.1` and at most three EcosystemMaxims. Inputs are hash-bound to current context, registry, semantic coverage, maxims catalog, runtime capability inspection and role contracts. The brief is always read-only, non-authoritative and non-mutating.

## EcosystemMaxims

The eight maxims remain versioned in `ops/semantics/maxims.json`. Selection in OS1B is deterministic. Maxims may influence recommendation ordering only; they never alter availability, eligibility, scope, authority or permission.

## Agent Cycle Entry

`python3 tools/agent.py begin` is now the intended composition facade for bootstrap. It builds one `AgentCycleContext 0.1` from existing canonical projections instead of requiring a worker to remember their manual order. Agent Cycle is not Routine and creates no authority. See `docs/architecture/agent-cycle-0.1.md`.

## Freshness

`CAPABILITY_DISCOVERY_FRESHNESS_GUARD` binds the brief to context, OperationalSemantics, semantic coverage, EcosystemMaxims, role contract content and runtime capability observation. `STALE != FRESH` and `TAMPERED != STALE`.

## Coverage

OperationalSemantics coverage continues to scan policy-declared Python entrypoints and workflows, registered contracts/schemas, runtime capability descriptors and provider profiles. Internal pure composition modules do not become new invocable surfaces merely because they are Python modules. The existing `agent-cli` remains the public entrypoint.

## Boundaries preserved

M10-OS1B does not create semantic authority or a new canonical writer, persist an open-cycle state marker, implement executable `agent close`, alter Routine semantics, admit M11/M12/M13 work, retry Scheduled Task maturity proofs, or reopen PCS-01B.

M10-OS1C owns Agent Cycle Closure 0.1. Only after that slice may the M10 checkpoint close.
