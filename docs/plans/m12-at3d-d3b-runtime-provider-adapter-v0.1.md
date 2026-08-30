# M12-AT3D-D3B — Runtime ToolSurface Provider Adapter 0.1

Status: implementation slice D3B  
Baseline: `main@37593be7df8f6e8d209b6ef8d55e30312e564bb2`  
ProjectState transition: `resolve-m12-at3d-d3-provider-capability-scope-v0.1`

## Purpose

D3A proved that a multi-capability request passes only when one provider can satisfy
the whole scope. D3B closes the immediately upstream gap without creating another
capability catalog:

> translate externally observed registered `ToolSurface` presence into the existing
> `RuntimeProviderObservations 0.1` contract, using OperationalSemantics as the only
> provider/feature definition.

The adapter is read-only. It does not discover runtime tools by itself, select a
provider, admit or execute an operation, authorize mutation, or change an authority.

## Existing definitions remain authoritative

D3B derives from `ops/semantics/registry.json` for `ToolSurface.provider` and
`ToolSurface.features`, `tools/runtime_capabilities.py` for provider observations and
inspection, and `tools/runtime_provider_scope.py` for whole-scope sufficiency.

No provider profile, LogicalCapability, ToolSurface, schema, provider registry,
mutable authority, or second feature vocabulary is added.

## Adapter boundary

`tools/runtime_provider_adapter.py::observations_from_tool_surfaces()` accepts a list
of registered ToolSurface ids observed by the external runtime and an explicit
`inventory_complete` fact. It returns the existing `RuntimeProviderObservations 0.1`
shape.

When the inventory is complete, observed ToolSurfaces contribute exactly their
Registry-declared features to their Registry-declared provider. Provider `PASS`
means surface observation completed; capability sufficiency is still decided by
`RuntimeCapabilityInspection`.

When discovery is incomplete, the provider remains `UNKNOWN`, emits no verified
features, and carries `TOOL_SURFACE_INVENTORY_INCOMPLETE`. The current provider
observation contract cannot safely express partial verified features plus unknown
undiscovered surface coverage, so D3B preserves UNKNOWN instead of widening it.

Unknown ToolSurface ids and duplicates fail closed.

## Work Mode / connector relationship

The GitHub connector already has provider `github-connector` and ToolSurface
`github-connector-tools`. D3B does not create a second action-to-feature table.
Concrete runtime actions establish that the registered ToolSurface is present; the
repository-side semantic translation begins at that registered surface and derives
features from the Registry.

A complete observed `github-connector-tools` surface can feed
`RuntimeCapabilityInspection`; D3A can then prove one-carrier scopes including
`github.git-data.write`, `github.expected-head-write`, and
`github.mutation-readback`.

This evidence never authorizes mutation. Target policy, leases, CAS, planners,
writers and independent readback remain mandatory.

## RuntimeObservationBundle remains separate

`RuntimeObservationBundle 0.1` is unchanged. It carries external ProjectMachine facts
and is not a provider selector. D3B does not merge these trust boundaries.

## Qualification

Tests prove complete connector surface derivation from the live Registry, D3A Git
scope PASS through one connector carrier, UNKNOWN preservation for incomplete
discovery, no invention of unobserved providers, determinism, fail-closed invalid
surface input, and reuse of the existing provider-observation contract.

Repository PR/CI remains the consumer scan.

## Non-goals

D3B does not choose among complete providers, execute through the connector, add
transport introspection inside repository Python, alter Agent Tool admission/dispatch,
promote Agent Cycle provider coverage, change close policy, solve R4 ordering, or
update Work, Coordination or ProjectState.

## Exit interpretation

```text
external runtime observes registered ToolSurfaces
  -> RuntimeProviderObservations 0.1
  -> RuntimeCapabilityInspection 0.1
  -> D3A provider scope
```

After qualification, D3 is re-evaluated against the live environment. The host/runtime
must still truthfully report the registered surfaces it can invoke; repository code
must not fabricate that fact.
