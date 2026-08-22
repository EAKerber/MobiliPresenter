# OperationalSemantics 0.3 — typed inventory and contextual entry

Status: **M10 closed. OperationalSemantics 0.3, Agent Cycle Entry and Agent Cycle Close/receipt are integrated; M11 convergence is the next infrastructure stage.**

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

Required capabilities are recorded explicitly in the SemanticFoundations contract. Unlisted matching capabilities use the closed default `relevant`.

Required capabilities remain visible even when provider observation or scope is insufficient.

## Semantic context

`AgentSemanticContext 0.1` adds the typed fields needed to avoid a broad role+intent projection: role, declaredIntent, lifecyclePhase, objects[], operations[] and scope[]. Objects and operations are policy inputs, not authorization. Scope constrains availability but never grants authority.

## AgentSemanticBrief

`AgentSemanticBrief 0.1` composes `CapabilityRelevanceProjection 0.1` and at most three EcosystemMaxims. Inputs are hash-bound to current context, registry, semantic coverage, maxims catalog, runtime capability inspection and role contracts. The brief is always read-only, non-authoritative and non-mutating.

## EcosystemMaxims

The eight maxims remain versioned in `ops/semantics/maxims.json`. Selection is deterministic. Maxims may influence recommendation ordering only; they never alter availability, eligibility, scope, authority or permission.

## Agent Cycle

`python3 tools/agent.py begin` is the composition facade for bootstrap. It builds one `AgentCycleContext 0.1` from existing canonical projections instead of requiring a worker to remember their manual order. Agent Cycle is not Routine and creates no authority.

After work, `python3 tools/agent.py close` reobserves the same ProjectMachine scope, derives `AgentCycleDelta 0.1`, verifies attributable transition/Git evidence and emits aggregate readback plus `AgentCycleReceipt 0.1`. Durable delta without attributable evidence is `UNKNOWN`, never a silent `PASS`.

See `docs/architecture/agent-cycle-0.1.md`.

## Freshness

`CAPABILITY_DISCOVERY_FRESHNESS_GUARD` binds the brief to context, OperationalSemantics, semantic coverage, EcosystemMaxims, role contract content and runtime capability observation. `STALE != FRESH` and `TAMPERED != STALE`.

Role `*-current.md` files are locators for the current versioned role contract. Mutable infrastructure direction belongs to ProjectState and must not be copied into those pointers. This prevents an already-stale pointer from disappearing from value-based freshness discovery merely because it no longer contains the current value.

## Coverage

OperationalSemantics coverage scans policy-declared Python entrypoints and workflows, registered contracts/schemas, runtime capability descriptors and provider profiles. Internal pure composition modules do not become new invocable surfaces merely because they are Python modules. The existing `semantic-cli` and `agent-cli` remain the public composition surfaces.

M11-CV1A adds `ConvergenceInspection 0.1` as an internal read-only inspection exposed through the already registered semantic CLI. It separates two questions:

- `coverageStatus`: whether all required consumer classes were observed;
- `retirementReadiness`: whether a legacy alias is actually ready to be retired.

`coverageStatus=PASS` therefore does not imply `retirementReadiness=READY`. A fully observed alias may correctly remain `MIGRATION_REQUIRED`.

## Boundaries preserved

OperationalSemantics does not become a mutation authority. `ConvergenceInspection 0.1` does not retire aliases, rewrite Coordination, alter writer topology, infer external consumers from absence of repository matches, or authorize future milestones.

M11 convergence must preserve the existing single-writer rule. `tools/lock.py` and the `lock`/`ops` aliases remain until their supported consumers are migrated and a later convergence slice proves retirement admissible.
