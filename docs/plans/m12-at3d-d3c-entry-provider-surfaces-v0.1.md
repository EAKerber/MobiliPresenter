# M12-AT3D-D3C — Agent Entry Provider Surfaces 0.1

Status: implementation slice D3C  
Baseline: `main@f525c31f7efa448ec0fb42ff17e9bc9ff68c6fba`  
ProjectState transition: `resolve-m12-at3d-d3-provider-capability-scope-v0.1`

## Purpose

D3A resolves whole-scope provider sufficiency and D3B translates observed registered
ToolSurfaces into the existing `RuntimeProviderObservations 0.1` contract. D3C connects
that derivation to the public agent entry without adding an intermediate durable file:

```text
host observes ToolSurface
  -> tools/agent.py facade
  -> RuntimeProviderObservations 0.1
  -> existing _runtime_inspection
  -> RuntimeCapabilityInspection 0.1
  -> AgentCycleContext
```

The internal begin implementation remains provider-observation based. The facade is
the concrete host/toolbox boundary and strips its ToolSurface-only flags before
delegating to the existing command parser.

## Flags

For `begin` and `doctor` only:

```text
--runtime-tool-surface <registered-tool-surface-id>
--runtime-tool-surfaces-complete
```

`--runtime-tool-surface` is repeatable. Without the completeness flag, observed
surfaces remain an incomplete inventory and D3B preserves provider UNKNOWN.

Existing `--runtime-providers <path>` remains supported unchanged as a compatibility
and explicit normalized-observation path.

## Single-writer rule

D3C must not silently choose between two observation sources for the same provider.
If a ToolSurface-derived provider is already claimed by the local probe or by the
explicit `--runtime-providers` bundle, entry fails with
`RUNTIME_PROVIDER_OBSERVATION_SOURCE_CONFLICT:<provider>`.

The existing behavior in which an explicit normalized provider bundle can overlay the
legacy local probe remains unchanged when ToolSurface flags are not involved.

## State and trust boundary

The ToolSurface overlay is process-local and ephemeral. The facade temporarily injects
it through the existing local-observation function while delegating, then restores both
the original function and `sys.argv` in `finally`.

D3C introduces no:

- schema;
- authority;
- provider profile;
- ToolSurface or LogicalCapability;
- provider selection;
- provider routing;
- mutation permission;
- Work/Coordination write;
- ProjectState side effect;
- temporary provider-observation file.

`RuntimeObservationBundle 0.1` remains a separate ProjectMachine fact boundary.

## Qualification

Focused tests prove:

1. a complete `github-connector-tools` observation reaches the existing capability
   inspector and satisfies the registered Git mutation/readback capabilities;
2. an incomplete ToolSurface inventory remains UNKNOWN;
3. overlapping provider writers fail closed;
4. facade-only flags are stripped before delegation and the derived observation is
   visible to the existing command implementation;
5. calls without the new flags preserve the established delegate path;
6. ToolSurface flags are rejected outside `begin` and `doctor`.

Repository PR/CI is the consumer scan.

## Exit interpretation

D3 is paved-path complete when D3A, D3B and D3C are qualified together and a host can
truthfully report a registered ToolSurface at entry without manually fabricating an
intermediate provider bundle. That still proves capability availability only; leases,
operation admission, CAS, planners/writers and independent readback remain separate
requirements.

ProjectState is not advanced as a merge side effect. After integration, live state is
reobserved and the D3 checkpoint transition is handled separately before entering R4.
