# Agent Cycle R1C — Loose Ends Audit

Status: observational note only  
Date: 2026-08-27  
Scope: R1C Role-visible Agent Tool Discovery 0.1 and directly adjacent Agent Cycle contracts

## Purpose

Record contract, compatibility, documentation, and version-coupling loose ends discovered while qualifying R1C.

This file is intentionally non-corrective. It does not change runtime semantics, schemas, registry entries, admission, readiness, provider resolution, or merge topology. The findings below are candidates for later cleanup or hardening only.

The trigger for this audit was the first R1C CI failure: `tools/tests/test_agent_tool_semantic_contracts.py` consumed the public module symbol `projection.PROJECTION_FIELDS`, while the first R1C implementation had replaced it with version-specific names. R1C restored a current-contract alias instead of weakening the consumer. The remaining findings look for similar hidden coupling or drift.

## Findings

### LE-01 — Operational Semantics definition is stale relative to AgentToolProjection 0.2

`ops/semantics/registry.json` still defines `artifact.agent-tool-projection` as a begin-time projection of tools that are `available`, `plannable`, or `conditional` for the current role and declared intent.

R1C adds a fourth semantic view, `discoverable`, whose membership is role-scoped and deliberately independent of current intent admission. The registered definition therefore describes only the current-intent buckets and omits the new role-visible discovery behavior.

Risk: documentation/semantic-registry consumers can reconstruct the old mental model and incorrectly treat intent as an existence/discovery filter.

Disposition: note only. A later semantics/documentation cleanup should decide whether the registry definition is promoted in place or versioned with a stronger contract description.

### LE-02 — R1C plan text still describes a dual-version structural schema

`docs/plans/agent-cycle-r1c-role-visible-tool-discovery-v0.1.md` says the structural schema is dual-version for 0.1 and 0.2.

Qualification changed the final strategy:
- the registered JSON Schema is the current `AgentToolProjection 0.2` schema only;
- the Python semantic validator retains explicit read compatibility for historical `AgentToolProjection 0.1`.

The plan therefore documents the pre-CI implementation strategy rather than the qualified result.

Risk: a future maintainer may reintroduce `oneOf` 0.1/0.2 at the registered schema path and collide again with the repository's current semantic-contract alignment test.

Disposition: note only.

### LE-03 — Python semantic validation and JSON structural validation are not acceptance-equivalent

`tools/agent_tools/projection.py::validate_projection` is intentionally/accidentally looser than `ops/schemas/agent-tool-projection.schema.json` in several leaf validations.

Examples:
- the JSON Schema constrains hash strings by hash pattern; Python primarily verifies the computed `projectionHash` and otherwise treats several values as non-empty strings;
- the schema constrains `toolId` by ID pattern and `effectClass` by enum;
- Python entry validators primarily require non-empty strings plus the closed `mode` vocabulary.

This asymmetry predates part of R1C, but the new `discoverable` entry shape extends the same pattern.

Risk: a payload can satisfy the Python semantic validator while failing the registered structural schema, making "validated" dependent on which validation surface a caller happens to use.

Disposition: note only. Later hardening should first decide whether structural-schema validation is an obligatory precondition of every semantic validator or whether Python must independently enforce the same leaf vocabulary.

### LE-04 — `discoverable` policy facts are hash-bound but not re-derived during standalone validation

The R1C producer correctly derives `discoverable` from `AgentToolPolicyCatalog`:
- role membership determines tool discoverability;
- `allowedIntents`, `requiredCapabilities`, and `effectClass` come from policy/tool definitions.

However, standalone `validate_projection(value)` does not load the policy catalog and re-derive those facts. A caller can construct a different but internally consistent `discoverable` list, recompute `projectionHash`, and still satisfy the projection validator as long as shape/order/internal `currentIntentAllowed` consistency remain valid.

`policyHash` is carried, but the validator does not use it to resolve and replay the exact policy facts.

Risk: the artifact is tamper-evident only relative to its own hash, not semantically proven against the policy source when validated in isolation. Consumers that treat semantic validation as provenance verification could over-trust a rehashed projection.

Disposition: note only. A later slice should decide whether validation needs an explicit policy input, a policy-hash resolver, or whether producer-bound validation belongs at the enclosing Agent Cycle context boundary instead.

### LE-05 — Historical AgentCycleContext 0.2 compatibility test now exercises a hybrid nested version

`tools/tests/test_agent_cycle_readiness.py` creates a current context, downgrades the outer schema to `AgentCycleContext 0.2`, removes readiness, rehashes it, and validates it.

Because the current context producer now embeds `AgentToolProjection 0.2`, that test proves acceptance of:

`AgentCycleContext 0.2 + AgentToolProjection 0.2`

It no longer independently proves the historically materialized combination:

`AgentCycleContext 0.2 + AgentToolProjection 0.1`

Risk: historical-read compatibility can regress without a fixture that preserves the actual nested artifact versions once emitted by the old producer.

Disposition: note only. A later compatibility-hardening slice could keep an immutable historical fixture rather than synthesizing legacy contexts from the current producer.

### LE-06 — Previous AgentCycleContext versions do not close nested AgentToolProjection version coupling

`tools/agent_cycle.py` validates `AgentCycleContext 0.2` by passing its nested `agentTools` to the current projection validator.

Because that validator accepts both projection 0.1 and 0.2, a rehashed outer Context 0.2 can legally contain a Projection 0.2. This is related to LE-05 but is a contract behavior rather than only a test gap.

Possible interpretations:
- desirable forward-compatible nested artifact evolution; or
- unintended weakening of historical context closure.

The repository currently does not state which interpretation is normative.

Risk: version numbers stop fully describing the shape/semantic generation era of the nested context, which can complicate migrations, replay, and historical invariants.

Disposition: note only. The compatibility policy should be made explicit before tightening or relying on this behavior.

### LE-07 — Agent Cycle architecture documentation still presents the three-bucket intent-filtered model

`docs/architecture/agent-cycle-0.1.md` describes Agent Tool projection through `available`, `plannable`, and `conditional` for the current role+intent, without the R1C `discoverable` role-wide inventory or the discovery/relevance/admission separation.

The document already carries behavior from multiple later Agent Cycle revisions despite the `0.1` filename, so treating it as purely historical is ambiguous.

Risk: future work on R2–R5 can use an obsolete mental model and accidentally reintroduce intent-based hiding while implementing handle/provider/Work Mode logic.

Disposition: note only. A later documentation pass should decide whether this file is historical, living architecture, or should be split.

### LE-08 — PR #169 proof text is stale after successful qualification

The PR body still says `Remote PR CI pending`, while the final R1C head passed Agent Ops, Coordination Guard, and Supervisor Snapshot.

Risk: low runtime risk, but review/audit provenance is misleading and can make an already-qualified head appear unqualified.

Disposition: note only, per the instruction not to correct loose ends in this pass.

## Cross-cutting diagnosis

The findings cluster into three patterns:

1. **Current-contract alias/API coupling** — module-level names and tests can become de facto public contracts even when not explicitly modeled as artifacts.
2. **Current schema vs historical-read compatibility** — the repository has both "current structural contract" and "validator can read historical artifacts", but this distinction is not uniformly documented.
3. **Generated projection vs provenance validation** — a hash proves integrity of the supplied projection, while semantic provenance may additionally require replay against the exact policy/catalog that produced it.

None of these findings invalidates the R1C behavior qualified by CI. They are bookkeeping/hardening concerns that should remain visible before R2/R5 deepen identity/provider coupling.

## Suggested future ownership, without implementation

- R2 / identity-handle work: consider LE-05 and LE-06 when defining what a stable handle pins about nested artifact versions.
- R5 / provider + Work Mode bridge: keep LE-01 and LE-07 visible so provider resolution consumes a role-discoverable capability universe rather than rebuilding intent-based hiding.
- A bounded compatibility-hardening/docs slice: LE-02, LE-03, LE-04, LE-08.

No corrective action is authorized or implied by this note.
