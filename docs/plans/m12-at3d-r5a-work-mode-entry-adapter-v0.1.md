# M12-AT3D-R5A — Work Mode Entry Adapter Plan 0.1

Status: planned implementation sequence  
Parent refactoring track: R5 — provider bridge and Work Mode  
ProjectState selection: `plan-m12-at3d-r5a-work-mode-entry-adapter-v0.1`

## Purpose

Make the paved path materially easier for a cold-start agent in a Work Mode-like runtime without creating a second provider model, a session authority, or a provider-selection responsibility for the agent.

The target experience is:

```text
host observes environment
  -> agent supplies role + intent (+ optional Work binding)
  -> begin materializes current capabilities/tools/guards
  -> agent uses governed tools
  -> close derives remaining obligations
```

The agent should not have to remember provider ids, capability feature bundles, authority file paths, repository-local executable availability, or temporary JSON bundles when the host already knows the corresponding runtime facts.

## Biopsy result

R5 does not start from an empty provider layer. D3A/D3B/D3C already established the semantic pieces needed for a narrow bridge.

### Existing pieces to reuse

1. `RuntimeProviderObservations 0.1` is already the normalized provider observation contract.
2. `runtime_provider_adapter.observations_from_tool_surfaces(...)` already maps registered ToolSurface observations into that existing contract.
3. `agent.py begin` and `doctor` already accept repeatable ToolSurface observations through the D3C facade without a temporary provider bundle.
4. `RuntimeCapabilityInspection 0.1` already derives provider-neutral logical capability status.
5. `runtime_provider_scope.resolve_provider_scope(...)` already proves whether one provider can satisfy an indivisible runtime-observed capability set, while deliberately refusing to choose a provider.
6. Agent Tool policy already derives required capabilities and eligible ToolSurfaces; the agent does not need to duplicate either list.
7. Hosted Agent Cycle already owns the begin/close transport and exact begin artifact lifecycle.

### Concrete remaining gap

`Hosted Agent Cycle` currently invokes canonical begin as:

```text
agent begin --role <role> --intent <intent> --machine-scope live --json
```

It has no transport field through which the external runtime that requested the begin can report the ToolSurfaces it actually observes.

Therefore D3C is usable by a local/explicit caller, but not yet naturally consumable by a Work Mode caller that reaches the canonical cycle through the Hosted carrier.

### Important non-gap

The existence of `github-connector-tools` in the Work Mode runtime does **not** imply that Hosted RemoteCanonical execution should switch to that provider. The current Hosted RemoteCanonical execution path is a distinct carrier and currently defaults to `GhApiTransport` unless an explicit transport is supplied.

R5A must not conflate:

- capabilities available to the interactive agent runtime;
- provider candidates for a specific runtime-observed operation scope;
- the concrete carrier already chosen by a Hosted workflow;
- mutation authorization.

## Cold-start friction inventory

### Facts the host already knows and should not require from the agent

- which registered ToolSurfaces are actually present in the runtime;
- whether that ToolSurface inventory is complete;
- hosted machine scope (`live` for Hosted begin);
- repository identity and canonical ProjectState locator;
- provider feature expansion implied by registered ToolSurfaces;
- capability/provider ids derived from registry semantics.

### Decisions that policy/runtime must retain

- whether a capability is available, conditional, unknown, or failed;
- whether a single provider can satisfy an indivisible runtime scope;
- which Agent Tools are available/plannable/conditional for role + intent;
- whether a mutation is admitted by guards and lifecycle ownership;
- which concrete carrier executes an operation once a carrier-specific path is entered.

### Information that legitimately remains agent/user input

- role;
- declared intent;
- optional explicit Work binding when applicable;
- operation-specific target/content requested through an Agent Tool;
- user authorization where the surrounding product requires it.

## Design decision

Split R5A into a repo-owned ingress and a host-owned observation adapter.

Do not pretend that a repository fixture proves the host-side integration.

## R5A1 — Hosted Runtime Observation Ingress

### Goal

Allow a Hosted begin request to carry a closed, non-authoritative observation of the caller runtime's registered ToolSurfaces and inventory completeness, then feed that observation through the already-qualified D3B/D3C path.

### Preferred shape

Introduce one current Hosted begin transport version that unifies the two current begin variants instead of adding another orthogonal wrapper.

Provisional semantic shape:

```json
{
  "schemaVersion": "HostedAgentCycleCommand 0.4",
  "requestId": "...",
  "action": "begin",
  "actor": {"role": "...", "workerId": "...", "sessionId": "..."},
  "declaredIntent": "...",
  "machineScope": "live",
  "workRef": null,
  "runtimeEnvironment": {
    "toolSurfaces": ["github-connector-tools"],
    "inventoryComplete": true
  },
  "evidenceCommentIds": [],
  "semanticAuthority": false,
  "authorizesMutation": false
}
```

`workRef` is nullable so the current begin and Work-bound begin paths converge into one current transport form. Historical 0.1/0.2/0.3 commands remain readable during migration.

The final field names are implementation details and may be reduced further if the existing parser can represent the same closed observation without widening ambiguity.

### Required behavior

For 0.4 begin:

1. validate only registered ToolSurface ids;
2. require canonical sorted/unique ids;
3. require explicit boolean inventory completeness;
4. treat the environment observation as non-authoritative runtime evidence;
5. feed it into existing D3B/D3C translation before canonical `agent begin` builds the context;
6. preserve UNKNOWN when inventory is incomplete;
7. preserve the exact same `RuntimeProviderObservations` and `RuntimeCapabilityInspection` contracts already in use;
8. do not add provider choice to AgentCycleContext;
9. do not add a second capability/provider registry;
10. do not authorize mutation.

### Trust boundary

Repository code can validate that a reported ToolSurface exists in the registry. It cannot independently prove which tools exist inside an external Work Mode runtime.

Truthfulness of `runtimeEnvironment` is therefore a responsibility of the host adapter that constructs the request. Manual/debug construction of the transport command is not equivalent to a qualified Work Mode observation.

A false host observation may affect readiness evidence but must never bypass operation guards, authority ownership, CAS, writer contracts, or readback.

## R5A2 — Work Mode Host Adapter

### Goal

Have the actual host derive the 0.4 runtime environment observation from its real available tool inventory so ordinary agents do not type provider/surface flags.

### Host contract

The adapter must:

1. inspect the host's actual available tool/connector inventory;
2. map only recognized host surfaces to registered MobiliPresenter ToolSurface ids;
3. declare inventory completeness only when the host can truthfully establish it;
4. construct the Hosted begin envelope from host observation + agent role/intent/workRef;
5. never accept arbitrary provider feature claims from the agent as a shortcut;
6. preserve the source/provenance needed to distinguish host observation from repository authority;
7. surface an incomplete observation as UNKNOWN rather than silently falling back to shell Git or another provider.

The repo should expose the smallest stable ingress needed by this adapter. It should not try to infer external connector presence from repository Python.

### Qualification boundary

R5A2 is not qualified by unit tests or a synthetic Hosted fixture alone.

Qualification requires one real Work Mode execution where the host observes its tool inventory and the resulting begin context proves the expected provider/capability observation without the agent manually naming the provider or ToolSurface.

If the current Work Mode product surface cannot expose a trustworthy tool inventory to an adapter, record R5A2 as externally blocked/UNKNOWN. Do not fabricate a PASS and do not replace the missing host capability with prompt convention.

## Provider/carrier selection

### Current rule

D3A intentionally returns deterministic complete provider candidates but does not choose one.

That remains correct for begin-time discovery.

### R5A rule

R5A does **not** add global provider selection to `AgentCycleReadiness` or Agent Tool projection.

A carrier is selected only at a concrete operation boundary where:

- the required runtime-observed capability scope is known;
- one provider must satisfy that whole scope;
- the selected execution adapter actually corresponds to that provider;
- guards and authorization remain independently satisfied.

If a later R5 slice needs provider selection, it must consume `runtime_provider_scope` at that concrete operation boundary rather than inferring a provider from individually PASS capabilities.

Hosted RemoteCanonical remains its existing carrier unless explicitly refactored in a separate qualified slice.

## Implementation surface expected for R5A1

Likely:

- `tools/hosted_agent_cycle.py` — current begin transport validation + D3C ingress reuse;
- `.github/workflows/hosted-agent-cycle.yml` — accept the current begin marker/version;
- focused transport/Hosted tests;
- D3C equivalence tests proving identical runtime capability inspection for identical ToolSurface observations.

Potentially no change is needed to:

- AgentCycleContext schema;
- RuntimeProviderObservations schema;
- RuntimeCapabilityInspection schema;
- semantic registry;
- Agent Tool policy;
- RuntimeObservationBundle;
- ProjectMachine;
- Work authority;
- Coordination authority;
- RemoteCanonical execution.

Any need to change one of those surfaces is a reason to re-evaluate the implementation before expanding scope.

## Explicit non-goals

R5A does not:

- create `WorkModeProvider` or `ProviderAuthority`;
- create a mutable environment/session registry;
- create a provider-selection authority;
- copy ToolSurface feature mappings outside the semantic registry;
- let the agent self-assert arbitrary provider features;
- turn provider observation into mutation authorization;
- make connector availability imply Hosted workflow carrier selection;
- fall back from connector to shell Git implicitly;
- solve arbitrary multi-provider composition;
- change Work/lease semantics;
- change R4 ordering/seal semantics;
- promote Agent Cycle touched-resource provider coverage before a real host bridge is qualified.

## Qualification plan

### R5A1 unit/contract

Required cases:

1. current Hosted begin with complete `github-connector-tools` observation yields the same normalized provider observation/capability inspection as D3C direct entry;
2. incomplete inventory preserves provider/capability UNKNOWN;
3. unknown ToolSurface fails closed;
4. duplicate/non-canonical ToolSurface ids fail closed;
5. no provider features can be supplied directly through the new transport;
6. Work-bound and unbound current begin use the same current command form;
7. historical 0.1/0.2/0.3 commands remain readable;
8. current close remains handle-first and does not need runtimeEnvironment to rebind the exact begin;
9. context remains non-authoritative and non-mutating;
10. RuntimeProviderObservations and RuntimeCapabilityInspection hashes match the established D3C path for equivalent input.

Run the full Agent Ops semantic/test suite and Supervisor Snapshot/Coordination guards through PR CI.

### R5A1 Hosted smoke

Use a dedicated qualification branch/workflow fixture to prove the Hosted carrier parses the current begin envelope and materializes a begin context with the expected runtime capability observation.

This proves repo-side ingress only. Label the evidence accordingly; it is not Work Mode host proof.

### R5A2 actual Work Mode smoke

Required before claiming Work Mode bridge qualification:

1. fresh agent/runtime with no project-history memory;
2. host observes available tools/connectors itself;
3. agent supplies only role + intent (+ Work id if explicitly assigned);
4. no provider id, ToolSurface id, feature list, temp provider bundle, authority path, or Git credential diagnosis is manually supplied by the agent;
5. Hosted begin context contains the expected provider/capability evidence;
6. unavailable/incomplete host observation produces UNKNOWN rather than false PASS;
7. one governed read-only action and, if authorized, one mutation-plan path are discoverable without shell-Git fallback;
8. close remains the same handle-bound canonical close.

## Cold-start success metric

For the ordinary Work Mode paved path, count agent-authored mechanical inputs before useful work begins.

Target after R5A2:

```text
required from agent:
  role
  declared intent
  optional assigned Work id

required mechanical provider inputs from agent:
  0
```

The metric fails if the agent must know or type any of:

- `github-connector`;
- `github-connector-tools`;
- provider feature names;
- `--runtime-providers` paths;
- `--runtime-tool-surface` flags;
- ProjectState/Coordination authority file paths;
- local `gh`/Git fallback choices.

Those may remain available for debugging/compatibility during migration, but they are not the paved path.

## Compatibility and retirement

Keep existing explicit runtime provider/surface CLI inputs as compatibility and test surfaces through R5 qualification.

R6 may retire a compatibility path only after:

- the Work Mode adapter is actually qualified;
- all observed current consumers have migrated;
- equivalent diagnostics exist;
- rollback is documented.

Legacy Hosted command readers may remain longer than the public producer; remove only with zero observed consumers.

## Re-evaluation triggers

Re-evaluate before implementation if any of the following becomes true:

- Work Mode cannot expose an actual tool inventory or completeness fact to the host adapter;
- current Hosted transport cannot carry the observation without making agent-authored data indistinguishable from host observation;
- implementation requires a second provider registry or authority;
- AgentCycleContext would need to carry provider selection rather than provider-neutral evidence;
- provider observation would alter RemoteCanonical carrier semantics implicitly;
- a real operation demonstrates that D3A provider-scope evidence must be consumed earlier than the concrete execution boundary.

## Planned sequence

```text
R5A plan (this document)
  -> R5A1 Hosted Runtime Observation Ingress
  -> Hosted ingress qualification
  -> R5A2 actual Work Mode host adapter
  -> real Work Mode cold-start qualification
  -> evaluate remaining R5 provider/carrier-selection needs
  -> R6 consolidation/retirement only after evidence
```

## Proposed next ProjectState transition after plan qualification

`implement-m12-at3d-r5a1-hosted-runtime-observation-ingress-v0.1`

This intentionally selects the repo-owned prerequisite first. It does not claim that the Work Mode host adapter already exists or is qualified.

---

## Post-R5A1 evidence amendment — 2026-08-30

This amendment records observed state after implementation and **supersedes forward-looking status/sequence statements above where they conflict with the evidence below**. The original plan is retained in place so the design intent and re-evaluation conditions remain auditable.

### Current disposition

- **R5A1 — QUALIFIED + MERGED.**
- **R5A2 — UNKNOWN / external host-observation boundary unresolved.**
- **R5A as a whole is not complete.**
- R6 compatibility retirement remains ineligible because the real Work Mode adapter has not been qualified.

### R5A1 integrated evidence

R5A1 was implemented in PR `#206` and squash-merged into `main` as:

`18ae88fe3707c1d157512b25d2e429394842fd04`

The integrated repo-owned boundary is `HostedAgentCycleCommand 0.4`, carrying only the closed non-authoritative runtime observation:

```json
{
  "runtimeEnvironment": {
    "toolSurfaces": ["github-connector-tools"],
    "inventoryComplete": true
  }
}
```

The Hosted carrier validates registered ToolSurface ids and reduces the observation to the existing D3B/D3C path. It does not add provider features, provider selection, mutation authority, a second registry, or provider state to `AgentCycleContext`.

Final Hosted qualification used the registered Agent Ops carrier rather than an unregistered ad-hoc workflow, because an earlier qualification workflow correctly exposed that adding an unregistered workflow perturbs OperationalSemantics coverage and can create a false-negative readiness result.

Final qualification evidence:

- qualification branch: `work/operations/m12-at3d-r5a1-hosted-qualification-20260830`;
- qualification head: `036f0c51d2b420226dfd1a68338f2f27fd742c3a`;
- Agent Ops run: `33333952520` — PASS;
- artifact: `r5a1-hosted-runtime-ingress-qualification`;
- artifact id: `9738453196`;
- artifact SHA-256: `f9808ac42e5cc3a931cadd14d59ec764208378ccf209cb2d7cc2d71d48192429`;
- Hosted begin status: `READY`;
- raw Agent Cycle begin status: `READY`, `blockingUnknowns=[]`;
- `github.git-data.write = PASS` via `github-connector`;
- `github.expected-head-write = PASS` via `github-connector`;
- `github.mutation-readback = PASS` via `github-connector`;
- `runtimeEnvironment` did not leak into `AgentCycleContext`;
- `semanticAuthority=false`;
- `authorizesMutation=false`.

The qualification intentionally labels its input as `host-input-fixture` and records:

`provesWorkModeDiscovery=false`

Therefore R5A1 proves the **repo-owned ingress and reduction path on a real hosted runner**. It does not prove that Work Mode itself can discover and supply the observation.

### Activated re-evaluation trigger for R5A2

The plan's explicit trigger is now active:

> Work Mode cannot expose an actual tool inventory or completeness fact to the host adapter.

More precisely, current investigation found **no publicly documented Work/product surface that repository-owned Python or GitHub Actions can use to truthfully observe the complete per-run Work tool/connector inventory and its completeness**. This is not evidence that such a surface can never exist; it means the repo currently has no observed host API on which R5A2 can be implemented and qualified without fabrication.

The current ChatGPT host may itself know which tools/connectors are available. That host knowledge is not equivalent to a repository-visible observation source and must not be inferred from:

- the presence of `gh` or `git` in a runner;
- environment variables;
- prompt convention;
- manually typed `github-connector-tools`;
- a synthetic provider bundle;
- historical memory that a connector was available in another run.

Accordingly, the absence of a repo-visible host inventory surface is **UNKNOWN**, not `PASS` and not evidence that the connector itself is `FAIL`.

### R5A2 current boundary

Until an actual host observation source is available, the repo-owned implementation stops at `HostedAgentCycleCommand 0.4`.

Do **not** add a repository-side wrapper whose only behavior is to hard-code or ask the agent to supply the ToolSurface that R5A2 is supposed to discover. Do not create a second provider registry, WorkModeProvider authority, mutable session registry, or implicit shell fallback to make the status appear complete.

R5A2 may re-enter implementation only when the host/product surface can provide enough observed information to satisfy this contract truthfully:

1. actual available host tool/connector surfaces for the current run;
2. a defensible completeness fact, or explicit incompleteness;
3. mapping to registered MobiliPresenter ToolSurface ids without arbitrary provider feature claims;
4. provenance sufficient to distinguish host observation from repository authority;
5. construction of the existing Hosted 0.4 begin envelope without agent-authored provider mechanics.

If the host can expose only a partial inventory, the correct result remains incomplete observation / `UNKNOWN`; R5A2 must not promote it to complete.

### Revised sequence

Observed sequence is now:

```text
R5A plan
  -> R5A1 Hosted Runtime Observation Ingress        DONE
  -> Hosted ingress qualification                  PASS
  -> R5A1 integration                              DONE
  -> reconcile ProjectState with R5A1 evidence     NEXT REPO-OWNED STEP
  -> R5A2 actual Work Mode host adapter             UNKNOWN / HOST-SIDE RE-ENTRY CONDITION
  -> real Work Mode cold-start qualification        NOT YET ELIGIBLE
  -> evaluate remaining R5 provider/carrier needs   only without claiming Work Mode qualification
  -> R6 retirement                                  NOT YET ELIGIBLE
```

### ProjectState implication

The prior proposed transition:

`implement-m12-at3d-r5a1-hosted-runtime-observation-ingress-v0.1`

is now historical and must not remain the selected next transition after R5A1 integration.

The next repo-owned action is a **separate ProjectState reconciliation** using the canonical ProjectState transition/apply tooling. That reconciliation must:

- record R5A1 as qualified/integrated;
- retain R5A2 as unresolved/UNKNOWN rather than marking R5A complete;
- avoid inventing a host capability or false Work Mode qualification;
- derive the exact checkpoint and `nextTransition` strings from canonical transition conventions before writing ProjectState.

This amendment intentionally does not choose those strings itself; ProjectState remains a separate authority with its own writer/validation path.
