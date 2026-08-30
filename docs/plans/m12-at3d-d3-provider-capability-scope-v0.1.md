# M12-AT3D-D3 — Provider Capability Scope 0.1

Status: implementation slice D3A  
Baseline: `main@391e6deeb1e8252695c2dcd78bcfb33d3869570b`  
ProjectState transition: `resolve-m12-at3d-d3-provider-capability-scope-v0.1`

## Purpose

Resolve one narrow question that sits between per-capability runtime observation and a
future productive provider adapter:

> Given a set of runtime-observed LogicalCapabilities and one
> `RuntimeCapabilityInspection 0.1`, is there at least one **single provider** that
> can satisfy the whole provider-dependent scope?

D3A is a read-only derivation. It does not select a provider, execute an operation,
authorize mutation, write Work or Coordination, or change Agent Cycle close policy.

## Existing definitions remain authoritative

D3A reuses, rather than duplicates:

- `ops/semantics/registry.json` for `LogicalCapability`, provider profiles and
  `providerRequirements`;
- `tools/runtime_capabilities.py` for `RuntimeProviderObservations 0.1` and
  `RuntimeCapabilityInspection 0.1`;
- each capability's `satisfiedProviders` and provider evaluation outcomes.

`RuntimeObservationBundle 0.1` is deliberately not widened. It remains an external
fact carrier for ProjectMachine observations and is not a provider selector.

No new schema, authority, provider profile, capability, session object or persistent
provider-scope artifact is introduced in D3A.

## Derived scope semantics

`tools/runtime_provider_scope.py::resolve_provider_scope()` accepts a validated
`RuntimeCapabilityInspection 0.1` and a canonical set of runtime-observed logical
capability ids.

For every requested capability it derives:

- **satisfied provider** — the existing inspection already proved that provider's
  complete feature bundle for that capability;
- **possible provider** — the provider is either satisfied or its observation is
  still `UNOBSERVED_OR_INCOMPLETE`.

The provider scope is the intersection across the requested capabilities.

### PASS

At least one single provider is in the satisfied intersection.

A known complete carrier is enough for PASS even when another supported provider is
still UNKNOWN. Multiple complete providers remain an ordered candidate set; D3A does
not choose among them.

### UNKNOWN

No provider is complete yet, but at least one single provider remains in the
possible intersection because incomplete observation could still satisfy the whole
scope.

`UNKNOWN` is not promoted to PASS and is not collapsed to FAIL merely because a
particular local provider is missing.

### FAIL

The current evidence leaves no single supported provider in the possible
intersection.

Two capabilities that are individually PASS through different, incompatible
providers do **not** compose into a PASS scope.

## Trust boundary

The derived result contains:

- requested runtime-observed capabilities;
- status and reason code;
- complete provider candidates;
- still-possible provider candidates;
- the source `inspectionHash`;
- `authorizesMutation=false`.

This answers provider sufficiency only. It does not imply:

- role authorization;
- owned lease;
- Work readiness;
- CAS validity;
- branch ownership;
- operation admission;
- provider preference;
- execution success.

Those remain owned by their existing authorities and guards.

## D3A non-goals

D3A must not:

- create `WorkModeProvider`, `ProviderAuthority` or a parallel registry;
- combine partial providers into one fictional carrier;
- write ProjectState, Work, Coordination or Git authorities as a semantic side
  effect;
- promote `AgentCycleTouchedResourceSet 0.2` provider coverage from UNKNOWN;
- alter `AgentCycleClosure 0.1`;
- implement the productive Work Mode bridge;
- solve seal, late delivery, ordering or asynchronous result ownership.

## Qualification

Focused tests prove:

1. one provider must satisfy the whole multi-capability scope;
2. split PASS capabilities across different providers produce scope FAIL when no
   common provider remains possible;
3. a common incomplete provider preserves UNKNOWN;
4. one known complete provider yields PASS even if an alternate remains UNKNOWN;
5. multiple complete providers remain candidates without implicit selection;
6. resolution is deterministic and bound to the source `inspectionHash`;
7. non-runtime-observed capabilities are rejected rather than silently reclassified;
8. empty or duplicate scopes fail closed.

Repository PR/CI is the consumer scan for semantic, operational, capability lifecycle,
Agent Ops, Coordination and branch hygiene regressions.

## Relationship to R4 and R5

D3A resolves provider capability scope only.

The productive Work Mode/provider adapter remains downstream of the Agent Cycle
resource/obligation work and the R4 seal/async-ordering boundary. A later consumer
may use this resolver to prove a complete carrier, but must still satisfy the
existing operation-specific authority, admission, CAS, lease and readback contracts.

D3A therefore does not alter ProjectState as a side effect. After qualification, the
live authorities and roadmap are reobserved before deciding whether the next bounded
slice is R4 or another strictly contractual D3 step.
