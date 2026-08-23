# OperationalSemantics 0.3 — typed inventory and contextual entry

Status: **M10 OperationalSemantics and Agent Cycle are integrated; M11 convergence is closed. M12 remote canonical execution is the next infrastructure stage.**

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

Required capabilities are recorded explicitly in the SemanticFoundations contract. Unlisted matching capabilities use the closed default `relevant`. Required capabilities remain visible even when provider observation or scope is insufficient.

## Semantic context and AgentSemanticBrief

`AgentSemanticContext 0.1` adds role, declaredIntent, lifecyclePhase, objects[], operations[] and scope[] so relevance is not inferred from a broad role+intent projection. Objects and operations are policy inputs, not authorization. Scope constrains availability but never grants authority.

`AgentSemanticBrief 0.1` composes `CapabilityRelevanceProjection 0.1` and at most three EcosystemMaxims. Inputs are hash-bound to current context, registry, semantic coverage, maxims catalog, runtime capability inspection and role contracts. The brief is read-only, non-authoritative and non-mutating.

## EcosystemMaxims

The versioned maxims in `ops/semantics/maxims.json` are deterministic guidance. They may influence recommendation ordering only; they never alter availability, eligibility, scope, authority or permission.

## Agent Cycle

`python3 tools/agent.py begin` is the composition facade for bootstrap. It builds one `AgentCycleContext 0.1` from existing canonical projections instead of requiring a worker to remember their manual order. Agent Cycle is not Routine and creates no authority.

After work, `python3 tools/agent.py close` reobserves the same ProjectMachine scope, derives `AgentCycleDelta 0.1`, verifies attributable transition/Git evidence and emits aggregate readback plus `AgentCycleReceipt 0.1`. Durable delta without attributable evidence is `UNKNOWN`, never a silent `PASS`.

See `docs/architecture/agent-cycle-0.1.md`.

## Freshness

`CAPABILITY_DISCOVERY_FRESHNESS_GUARD` binds the brief to context, OperationalSemantics, semantic coverage, EcosystemMaxims, role contract content and runtime capability observation. `STALE != FRESH` and `TAMPERED != STALE`.

Role `*-current.md` files are locators for the current versioned role contract. Mutable infrastructure direction belongs to ProjectState and must not be copied into those pointers.

## Coverage

OperationalSemantics coverage scans policy-declared Python entrypoints and workflows, registered contracts/schemas, runtime capability descriptors and provider profiles. Internal pure composition modules do not become invocable surfaces merely because they are Python modules. The existing `semantic-cli` and `agent-cli` remain public composition surfaces.

M11 temporarily added `ConvergenceInspection` to prove migration and retirement readiness for the closed aliases `lock` and `ops`. After the final CV1C proof reported both aliases `ABSENT/PASS/RETIRED`, that migration-only inspection and its Agent Ops artifact pipeline were retired. Its historical design record remains in `docs/architecture/convergence-coverage-0.1.md`.

## M11 convergence result

M11 preserved the single-writer rule while converging the operator and branch surfaces:

- `tools/coordination_cli.py` is the canonical Coordination operator adapter;
- `coordination-executor` remains the single writer for `coordination-leases`;
- `tools/lock.py` and the semantic alias `lock` are retired;
- semantic alias `ops -> operations` is retired;
- `ops` remains only as historical branch grammar recognition, not semantic projection;
- legacy branch listeners `ops/**`, `renderer/**`, and `architecture/**` were retired only after live branch/PR/Work relations were absent;
- repository path filters such as `ops/**` remain unchanged where they refer to repository paths.

## Boundaries preserved

OperationalSemantics does not become a mutation authority. Historical convergence evidence does not authorize future milestones. Branch lifecycle planning remains under Branch Hygiene; ProjectState remains the mutable infrastructure direction authority.

M12 must preserve these boundaries while introducing the remote canonical execution bridge: provider/carrier availability may expose a path, but it cannot acquire semantic authority or bypass plan validation, expected heads, allowlists, readback, or receipts.
