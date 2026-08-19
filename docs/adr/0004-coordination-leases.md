# ADR-0004 — Coordination Leases sobre autoridade Git

- Status: **accepted**
- Current capability policy: `canonical`
- Current authority: `coordination/leases` → `ops/coordination/leases.json`
- Canonical writer: `tools.coordination_remote`
- Origin: promoted from the former Git Ops 1.3 experimental branch during M6-K knowledge salvage.

## Context

Path ownership answers who normally owns a semantic area; it does not answer who is writing a shared resource now. Parallel workers can therefore remain semantically isolated and still collide on a shared file, path or branch before integration.

The project needs temporary write ownership without introducing an external lock service or another product-semantic authority. Coordination must remain operational: acquiring a lease never grants authority over UI, Engine, Scene Core or product decisions.

## Decision

Use a dedicated Git-backed authority for temporary write coordination:

```text
authority branch: coordination/leases
state path:       ops/coordination/leases.json
schema:           CoordinationState 0.1
```

The authority contains current intents and leases only. Its Git commit history is sufficient audit history; no parallel event log in `main` is required.

The current capability record in `ops/capabilities/coordination-leases.json` governs capability policy. The Semantic Registry declares the authority and canonical writer. This ADR records rationale and invariants; it is not a second source of mutable state.

## Mutation protocol

Mutations follow the repository-wide significant-operation contract:

```text
observe authority head
→ validate current state and remote time when required
→ build complete next state
→ create child commit of the observed head
→ advance authority ref non-forced
→ readback
```

A concurrent writer that advances the ref first causes the losing mutation to fail and reobserve. Force updates are not part of the normal protocol.

## Resources

Canonical resource forms are:

```text
file:<repo-relative-path>
path:<repo-relative-glob>
branch:<branch-name>
```

Paths are repository-relative and normalized. File resources do not accept glob metacharacters. Path globs use the bounded grammar implemented by `tools.coordination`. Branch resources form their own namespace.

File/path leases are repository-global rather than feature-branch-local because their purpose is to expose write contention before integration.

## Conflict and acquisition semantics

- acquisition is all-or-nothing for the requested resource set;
- resources are normalized, deduplicated and sorted before evaluation;
- same-file and same-branch ownership conflicts directly;
- file/path overlap is detected deterministically;
- path/path overlap fails conservatively when disjointness cannot be proven;
- no partial acquisition is held while waiting for another resource.

These rules avoid a hold-and-wait cycle between partially acquired batches.

## Lease lifetime

Current runtime constants are:

- default lease TTL: **60 minutes**;
- maximum lease TTL: **4 hours**;
- default intent TTL: **30 minutes**.

Expiration is part of conflict evaluation. Renew/release remain owner-scoped operations. Cleanup of stale material must not silently break a lease owned by another session.

## Owner identity

A lease owner contains the operational identity needed for safe renew/release and CI correlation:

```json
{
  "role": "...",
  "session": "...",
  "branch": null,
  "pr": null
}
```

`session` identifies the temporary owner. Branch/PR, when present, are correlation evidence; neither substitutes for session ownership of mutations.

## Intent

Intent is advisory. It may expose planned overlap, but it is not a lease and does not authorize or block a write by itself.

## Failure behavior

Operations that require the lease authority fail closed when the authority, required timing information, expected revision or readback cannot be established. Absence of an observed lease must never be fabricated from an unavailable authority.

Administrative break/recovery is an explicit GitOps operation and must preserve expected-revision, reason and readback guards. It is not an implicit overwrite path.

## Relationship to Work

Work and Coordination answer different questions:

```text
Work        → what persistent unit should be done, by whom, with what dependencies
Lease       → who temporarily owns an exact write resource now
```

A WorkItem does not become a lease, and a lease does not create persistent work. Future paved paths may derive lease resources from a mutation/work plan, but the authorities remain distinct unless a later migration proves the distinction unnecessary.

## Non-goals

Coordination Leases do not provide:

- product or domain arbitration;
- a scheduler or global work queue;
- automatic ownership of every file touched by a branch;
- branch retention policy;
- publication policy;
- permission to bypass Transition Protocol, Git mutation guards or semantic ownership.

## Current source precedence

If this ADR and the implementation ever diverge, current operational truth is resolved from:

1. the Semantic Registry for authority topology and canonical writer;
2. the capability record for current capability policy;
3. the executable schema/runtime for current state and validation behavior;
4. this ADR for accepted rationale and architectural intent.

Historical Git Ops 1.3 probe scripts and experimental evidence remain historical and are not required for normal bootstrap.
