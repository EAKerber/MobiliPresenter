# Agent Cycle R2A — Cycle Identity Kernel + CycleHandle 0.1

Status: **implemented and qualified on PR #171**

Base: `main@cbb6cbae91f69b4825cd845aa92e93240b66e277`

R2A is the first bounded slice of R2. It does not attempt replay fencing,
`abandon`, expiry, Work binding, async sealing, provider resolution, or a new
public handle-only command protocol.

## 1. Goal

Turn cycle identity from several compatible implementations into one canonical
definition while preserving independent validation at each trust boundary.

The current distinction remains intentional:

- `cycleId` is the deterministic fingerprint of an `AgentCycleContext` baseline;
- `cycleInstanceId` identifies one concrete hosted execution of that context.

R2A does not merge those facts. It centralizes the derivation and binding rules
that were previously repeated by Hosted Agent Cycle, trace collection, Agent
Tool, and Agent Write Lifecycle.

## 2. Single Definition / Single Writer gate

Every fact introduced or touched by this slice is classified before it is
persisted or copied:

| Fact | Class | Authority / writer | R2A rule |
|---|---|---|---|
| `cycleId` | derived context fingerprint | `AgentCycleContext` producer definition | preserve; handle only references it |
| `cycleInstanceId` | derived execution identity | no mutable authority; one kernel definition | derive only through `agent_cycle_identity` |
| begin identity | transport provenance | source hosted begin evidence | canonicalize once; revalidate at every trust boundary |
| actor identity | identity reference | existing actor/session facts | canonicalize once; do not create a cycle-owned actor authority |
| `AgentCycleHandle` | derived projection | none | read-only, reconstructible, never a writer |
| `resumeToken` | transport locator | carrier evidence | opaque locator, never credential/authority |

General gate retained for later R2–R6 slices:

```text
mutable fact
-> exactly one authority
-> exactly one canonical writer

derived fact
-> exactly one canonical definition
-> may be revalidated in N trust boundaries

projection/cache
-> never authority
-> never writer
-> reconstructible from evidence/authorities
```

A reduction in duplicate validation calls is not itself a goal. Revalidation at
an independent trust boundary remains defense in depth; duplicate *definitions*
of the fact are the target.

## 3. Identity kernel

`tools/agent_cycle_identity.py` owns the pure definitions for:

- closed actor canonicalization;
- closed begin-reference canonicalization;
- deriving the Hosted `cycleInstanceId` with the exact pre-R2A formula;
- validating begin + actor + declared instance against one Hosted manifest;
- building and validating `AgentCycleHandle 0.1`;
- binding a supplied handle back to the exact context/actor/instance.

The kernel performs no I/O and writes no authority.

Hosted, trace, Agent Tool, and Agent Write Lifecycle keep their own domain/error
boundaries and map shared identity failures back to their existing error
vocabulary.

## 4. AgentCycleHandle 0.1

Current shape:

```text
AgentCycleHandle 0.1
  repository
  cycleId
  cycleInstanceId
  context:
    schemaVersion
    contextHash
  actor:
    role
    workerId
    sessionId
  resumeToken
  readOnly = true
  semanticAuthority = false
  authorizesMutation = false
  handleHash
```

The handle is portable correlation/resume metadata, not a session authority.
Its hash proves internal integrity only. A caller may construct a different
internally valid/rehashed handle; provenance is established only by
`validate_handle_binding()` against the exact validated context and concrete
instance evidence.

This distinction deliberately carries forward the R1C lesson that hash binding
is not semantic provenance by itself.

## 5. Hosted materialization and compatibility

A current Hosted begin continues to emit the existing:

- `context.json`;
- `manifest.json`;
- `HostedAgentCycleBeginResult 0.3`.

It additionally stores:

- `handle.json`.

The existing workflow already uploads the whole begin directory, so no workflow
protocol or artifact-name change is required.

Close validates `handle.json` when it exists. Historical begin artifacts without
a handle remain readable and close through the previous manifest/context
binding. This is reader-first compatibility without dual-writing a second
manifest version.

Agent Tool and Agent Write Lease request schemas remain 0.1 in R2A. Their callers
still supply the legacy begin reference. Internally, those references are now
validated by the shared identity kernel. Removing the copied fields from callers
belongs to R2B after the handle foundation is proven.

## 6. Deliberate reduction discovered during implementation

The first implementation draft created a JSON Schema and planned an
OperationalSemantics registry entry for `AgentCycleHandle 0.1` immediately.
That was withdrawn before qualification.

R2A has no public command that accepts a handle and no external repository
consumer depends on a structural schema yet. Registering a second validation
surface now would recreate the R1C LE-03 risk (Python semantic validation vs JSON
Schema acceptance) before it buys interoperability.

Therefore R2A has one executable definition: `tools.agent_cycle_identity`.
Schema/OperationalSemantics registration is a **R2B admission condition** when a
handle becomes an actual public input/output contract consumed outside the
Hosted begin artifact. At that point structural and semantic acceptance must be
qualified together.

This is intentional subtraction, not missing qualification.

## 7. Compatibility boundaries

Preserved without wire-version changes:

- Hosted Agent Cycle command 0.1;
- Hosted begin manifests 0.1 / 0.2 / 0.3;
- Hosted begin result 0.3;
- Agent Tool request/plan/result 0.1;
- Agent Write Lease request/dispatch/result/binding 0.1;
- existing trace schema and result correlation;
- old begin artifacts that contain only context + manifest.

R2A preserves the exact historical Hosted formula for `cycleInstanceId`, so
existing manifests continue to validate.

## 8. What R2A does not solve

R2A is primarily a **Single Definition** slice. It does not claim completion of
single-writer/source-of-truth work across the project.

Still later:

- R2B — handle-first commands, operation identity, replay fences, reduction of
  manually copied run/source/context/actor fields;
- R2C — abandon, artifact expiry/retention and impossible-resume disposition;
- R3 — progress/touched resources/obligations must remain derived projections,
  not a second source of Work/lease/branch truth;
- R4 — seal and async status derived from request/result evidence;
- R5 — provider observations stay evidence/carriers, never authorities;
- R6 — remove compatibility paths only after observed consumers are zero.

`PENDING` / `WAITING` are deliberately not introduced by R2A. There is no new
async lifecycle behavior here that needs those states.

## 9. Historical version coupling

R1C loose ends LE-05 and LE-06 remain visible. R2A pins the current context
`schemaVersion + contextHash` inside a handle, but it does not retroactively
decide whether every historical outer `AgentCycleContext` version must pin the
exact historical nested `AgentToolProjection` version.

That policy remains an explicit compatibility decision, not an incidental side
effect of the handle implementation.

## 10. Qualification gates

R2A is qualified only if all of the following hold:

1. the shared kernel reproduces the exact pre-R2A Hosted instance formula;
2. two begins over the same context may share `cycleId` but receive distinct
   concrete `cycleInstanceId`s;
3. cross-instance and cross-actor bindings fail closed;
4. handle tampering fails internal validation;
5. a separately rehashed handle still cannot satisfy a different authoritative
   context/instance binding;
6. current Hosted begin materializes `handle.json` alongside existing artifacts;
7. historical begin directories without a handle remain readable;
8. Agent Tool / Write Lifecycle / Trace keep their own trust-boundary checks but
   delegate identity definition to the kernel;
9. no authority, canonical writer, capability, provider, workflow protocol, or
   mutation admission is added;
10. full Agent Ops, semantic checks, OperationalSemantics coverage, roadmap
    freshness, capability lifecycle, Coordination Guard and Supervisor Snapshot
    remain green.

### Qualification result

The first PR qualification found three pre-existing synthetic fixtures that
mocked higher-level validators and therefore supplied incomplete or invented
identity facts: one partial context omitted `repository/schemaVersion`, one
partial manifest omitted hosted source correlation fields, and one Agent Tool
fixture hard-coded an arbitrary `cycleInstanceId`.

No runtime compatibility fallback was added. The fixtures were made
identity-complete and now derive the concrete instance through the canonical
kernel. This is an intentional application of the Single Definition gate: tests
may mock a trust boundary, but they do not get a second private definition of
cycle identity.

Qualified runtime head before this documentation-only record:
`3716e00ce6286082f540cd122e4a360841943783`.

PASS:

- Agent Ops run #1207 (`33177526998`): Toolbox unit tests, Semantic Contracts,
  Operational Semantics coverage, roadmap freshness, capability lifecycle,
  Doctor/coherence, Project Machine, routine, maintenance, Scheduler,
  integration-reconcile and handoff evidence all passed;
- Coordination Guard run #412 (`33177527052`);
- Supervisor Snapshot run #1001 (`33177526996`).

This documentation-only qualification record must itself be requalified before
promotion.

## 11. R2B admission / death condition

R2A is a foundation, not the final paved-path payoff. R2B is admitted only after
R2A qualification proves the handle can survive a Hosted round trip without
changing mutation admission.

R2B should then make the handle pay for its existence by removing caller-side
mechanics: begin run/source/context IDs and repeated actor/correlation fields
should be derived from a validated handle wherever the carrier already knows
them.

If R2B cannot remove meaningful manual correlation without weakening a trust
boundary, the persistence/public promotion of `AgentCycleHandle` must be
re-evaluated rather than preserved merely because R2A introduced it.
