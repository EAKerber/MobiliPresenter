# E2 — Portable write-lifecycle admission proof

Status: **candidate boundary extraction for post-R8 governed mutation ergonomics**.

## Purpose

`git.files.mutate` is already a mutation-execute Agent Tool for Manager/GitOps under the governed-mutation intent. Git CAS, Coordination ownership, GitMutationPlan, GitMutationBundle and provider readback are already transport-neutral.

The remaining admission asymmetry was `agent-write-lifecycle-bound`: its proof producer discovered the lifecycle result by reading Hosted Agent Bus issue comments and built the semantic proof in the same function.

E2 separates those responsibilities without adding a new execution path.

## Change

- current producer schema becomes `AgentWriteLifecycleGuardProof 0.2`;
- `prove_binding_result(...)` accepts an already discovered lifecycle result plus an opaque provenance reference;
- the core validates lifecycle result binding, ACTIVE state, expiry and exact current Coordination lease;
- hosted `prove_active_binding(...)` remains the existing caller but becomes discovery/adapter only;
- hosted provenance is represented as `{"kind":"hosted-comment","value":"<id>"}`;
- proof 0.1 remains validation-only compatibility for historical evidence;
- no new producer emits 0.1.

The provenance reference is not authority and is not consulted to decide whether the binding is active. It only identifies where the supplied lifecycle result came from.

## Invariants

The portable verifier still requires:

- exact cycle instance;
- exact Agent Cycle begin identity;
- exact actor;
- exact branch;
- a valid `AgentWriteLeaseResult`;
- binding state ACTIVE;
- unexpired binding at Coordination authority time;
- exactly one active lease with the binding lease ID, branch resource and expected owner;
- current Coordination authority observation;
- proof/readback hashes.

UNKNOWN/BLOCKED semantics are not relaxed.

## Boundary

The portable verifier does not know:

- issue number;
- comment ID;
- Hosted Agent Bus markers;
- hosted record windows;
- workflow/run IDs.

Hosted discovery continues to know those mechanics and delegates the semantic proof to the portable verifier.

## Compatibility

`validate_active_binding_proof` accepts:

- 0.2 with `lifecycleResultRef`;
- historical 0.1 with `lifecycleResultCommentId`.

Compatibility is read-only. New proofs are 0.2.

Death condition for 0.1 validation: remove only after current runtime/tests and retained evidence no longer require historical proof validation.

## Non-goals

E2 does not add:

- direct mutation host;
- new ToolSurface;
- new CLI/workflow;
- automatic lease acquisition;
- lifecycle state/session/store;
- provider selection;
- retry/replay behavior.

## Promotion gate

Exact-head CI must prove Agent Ops, Coordination Guard and Supervisor Snapshot for the PR head.

Regression must prove:

1. an already supplied lifecycle result can produce a valid proof without issue/comment discovery;
2. branch/cycle/actor mismatches fail closed;
3. released and expired bindings fail closed;
4. zero or multiple matching active leases fail closed;
5. hosted discovery delegates to the portable verifier;
6. proof 0.1 remains readable;
7. the portable verifier source contains no hosted-discovery contract.

## Next slice

If E2 integrates cleanly, E3 may add a thin direct governed-mutation host that composes the existing resolver, guard proof collection/admission and remote canonical executor. E3 must not duplicate lifecycle proof semantics or introduce a second authorization path.
