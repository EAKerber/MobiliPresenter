# Semantic Foundations 0.1

Status: **M9-SF1 contract closed; runtime brief generation remains M10 scope**.

## Purpose

This increment closes the vocabulary and authority boundaries required before
`OperationalSemantics 0.3` can generate an `AgentSemanticBrief`.

The machine-readable contract is `ops/semantics/foundations.json`. It is a
read-only repository contract, not a new authority, writer, inventory or brief.
Its structural schema is `ops/schemas/semantic-foundations.schema.json` and its
semantic validator is `tools.semantics.foundations.validate_foundations`.

## Closed vocabulary

The Technical Dictionary distinguishes:

- `EcosystemCapability` from `LogicalCapability`;
- `ToolSurface` from `Provider`;
- both from `Authority`;
- `Role` from worker identity and semantic ownership;
- `DeclaredIntent` from `CoordinationIntent`;
- `Projection` from source of truth;
- `Maxim` from policy.

New contracts must use the specific class whenever the generic word
`capability` would change meaning.

## Semantic scope

`AgentSemanticBrief` is a future contextual projection composed of a
`CapabilityRelevanceProjection` and a bounded selection of `EcosystemMaxim`.
It does not replace the complete inventory, RuntimeCapabilityInspection, role
contracts, Work, Coordination, leases, planners or writers.

The capability projection keeps these buckets explicit:

```text
required
relevantAvailable
conditional
requiredUnavailable
```

Required capability coverage cannot disappear because observation is missing.
`inventoryCount`, `selectedCount`, `omittedCount` and `missingCoverage` expose
the larger inventory and any incomplete projection.

## Determinism boundary

Every future brief field is classified as one of:

1. factual deterministic;
2. deterministic policy;
3. non-authoritative recommendation.

Heuristics may order recommendations. They may not change authority,
availability, eligibility, mutation permission or scope.

All covered artifacts remain mechanically bounded by:

```text
readOnly = true
semanticAuthority = false
authorizesMutation = false
```

`EcosystemMaxim` additionally requires `overridesContract=false` and must carry
an editorial owner, justification, operational question, misread risk, related
contracts and a review/replacement/death condition.

## Freshness and invalidation

The future brief is invalidated when its context, role/scope, lifecycle phase,
DeclaredIntent, relevant authorities or leases, provider observation, registry
or role contract changes. A stale brief is informative only and cannot prove
availability. Missing or unverifiable inputs remain `UNKNOWN`.

The guard identifier reserved for M10 is
`CAPABILITY_DISCOVERY_FRESHNESS_GUARD`.

## Roadmap freshness

M9-FG1 is implemented alongside this contract by
`tools/roadmap_freshness.py`. It is a separate read-only inspection over
ProjectState base/head and an explicit hash-bound consumer coverage record.
It does not edit narrative or claim that reviewed prose is semantically correct.

## Deferred to M10

This increment intentionally does not:

- promote OperationalSemantics to 0.3;
- create a brief generator or runtime validator;
- create the versioned maxim catalog;
- rank recommendations with a model;
- create a new authority or writer;
- inject a static tool list into Kickstarts.
