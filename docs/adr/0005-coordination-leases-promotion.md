# ADR-0005 — Promotion of Coordination Leases

- Status: accepted
- Date: 2026-08-13
- Scope: GitOps only
- Supersedes for policy: ADR-0004 experimental status

## Context

ADR-0004 defined Coordination Leases as an executable experiment over a dedicated Git authority branch. The experiment remained deliberately outside canonical policy until concurrency, recovery, enforcement and rollback were proven.

The capability completed its declared Gates. Evidence includes real single-winner CAS, all-or-nothing acquisition, remote-time TTL/renew/release, foreign-owner tooling and CI rejection, orphan recovery, session restart recovery, audited break-glass, closed-PR cleanup, parallel UI × Engine contention/reconciliation, and a formal rollback exercise proving that canonical GitOps remains functional when coordination modules are absent.

Capability Gates round 1 is recorded in `ops/evidence/capability-gates-coordination-leases-round-1-2026-08-13.json`.

## Decision

Promote the **coordination-leases capability** to canonical operational capability.

This is a capability promotion, not a requirement to treat a GitOps version number as the durable interface.

Canonical authority remains:

```text
authority branch: coordination/leases
state path:       ops/coordination/leases.json
mutation rule:    observe -> plan -> validate -> CAS apply (force=false) -> readback
```

The authority branch remains independent of `main` and carries no product semantics.

The supported operator entrypoint is:

```bash
python3 tools/lock.py ...
```

`tools/agent.py lock` is not required. Capability discovery may expose or route to the dedicated entrypoint later without duplicating its parser.

## Usage policy

Canonical means supported and governed; it does **not** mean every repository write must acquire a lease.

Use a lease when:
- parallel workers may touch the same file/path/branch;
- a shared or high-risk operational surface needs temporary exclusive write ownership;
- a workflow or handoff explicitly declares lease ownership.

The capability never grants semantic authority over UI, Engine, Scene Core or product decisions.

Unknown authority state, remote time, CAS result or readback fails closed for mutations and guards.

## CI enforcement

`Coordination Guard` reobserves the authority for pull requests and rejects changed paths or branch mutation covered by a valid foreign lease.

Absence of a lease is not itself an error. The mechanism prevents conflicting ownership; it does not require blanket locking of the repository.

## Rollback

Rollback remains operationally simple:
1. release/expire active leases;
2. disable the Coordination Guard;
3. stop invoking the dedicated tooling;
4. preserve the authority branch as audit evidence if needed.

The canonical `tools/agent.py doctor/verify` path has been tested with the coordination modules physically absent.

## Scheduler boundary

Coordination Leases resolve temporary write ownership only. They are not a scheduler, work queue, dependency router, worker-health system or semantic arbitrator. The Agent Bus/scheduling layer remains separate.
