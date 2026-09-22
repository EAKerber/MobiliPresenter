# E3 — Shared governed mutation host

Status: **candidate execution-composition promotion after E2/E2b**.

## Purpose

The normal Agent Tool mutation path already had the required semantics but the execution core lived inside Hosted Agent Tool dispatch.

E3 extracts that core once and makes the existing hosted path consume it immediately. The same core also exposes a direct host function for a future ToolSurface binding.

This is not a second mutation engine.

## Shared core

`tools.agent_tools.mutation_host.execute_plan(...)` owns exactly:

1. validate a READY Manager/GitOps `git.files.mutate` plan and its canonical command;
2. validate portable execution provenance before mutation;
3. re-observe all admission guards;
4. assert execution admission;
5. execute through the existing Agent-owned Git writer;
6. preserve per-mutable-call Coordination ownership enforcement;
7. validate the canonical RemoteCanonicalExecutionReceipt;
8. classify failure as BLOCKED when no mutation is evidenced, UNKNOWN after ambiguous durable mutation;
9. return a hash-bound non-authoritative host outcome.

It does not acquire/renew/release leases and does not create Work, Agent Cycle or Delivery authority.

## Hosted consumer

Hosted dispatch keeps the mechanics that are genuinely hosted:

- artifact/bundle validation;
- original request readback;
- hosted policy readback;
- attempt comment fencing;
- duplicate/prior-attempt protection;
- hosted terminal envelope.

After validating the attempt, it builds hosted-comment provenance and calls the shared mutation host.

The old inline reproof/write/classification block is removed from `dispatch_host.execute_dispatch()`.

## Direct consumer

`mutation_host.execute_request(...)` composes:

`resolver.resolve_request(execute=False) -> shared execute_plan -> AgentToolResult`

It requires an already supplied lifecycle result/reference plus a transport. The lifecycle result is verified through the portable E2 proof path.

Direct provenance is:

`kind=agent-tool-host / ref=agent-tool-request:<requestHash>`

No issue/comment identity is required.

## Admission

`collect_guard_proofs()` now accepts exactly one lifecycle evidence carrier:

- hosted lifecycle context; or
- portable lifecycle result context.

Supplying both is fail-closed.

All other guards use the same providers as before.

## Ownership invariant

The shared host calls the existing `execute_agent_owned_git()` writer. Its `LeaseEnforcingTransport` re-proves current ownership before every mutable provider call.

Therefore direct hosting does not convert a one-time admission proof into write authority.

## Result boundary

The shared host emits `AgentToolGovernedMutationHostOutcome 0.1`, a non-authoritative evidence object containing:

- request/plan/command lineage;
- execution proof set;
- canonical remote receipt on PASS;
- mutable provider call count;
- observed branch head;
- BLOCKED/UNKNOWN classification;
- portable source provenance.

Hosted dispatch projects this outcome into its existing mutation result/terminal schema.

Direct execution projects the same outcome into the existing generic AgentToolResult schema.

## Non-goals

E3 adds no:

- CLI;
- workflow;
- provider manager;
- lease acquisition;
- retry/rebase;
- PR/CI/merge behavior;
- persistent host session;
- new authority or state machine.

The direct function is a host binding seam, not yet a ChatGPT ToolSurface.

## Promotion gate

Exact-head Agent Ops, Coordination Guard and Supervisor Snapshot must pass.

Regression must prove:

1. hosted execute delegates to the shared host;
2. pre-mutation guard failure stays BLOCKED with zero mutable calls;
3. post-mutation ambiguity becomes UNKNOWN;
4. PASS uses the existing Agent-owned writer and canonical receipt;
5. direct execution uses portable lifecycle evidence and agent-tool-host provenance;
6. no issue/comment metadata is required by the shared/direct host.

## Next

After E3, the remaining step is product/tool integration: expose the direct host seam as a native ToolSurface action when an appropriate plugin/connector capability can call it without adding a repository workflow or bridge.
