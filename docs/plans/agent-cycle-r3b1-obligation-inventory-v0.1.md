# Agent Cycle R3B1 — Obligation Inventory 0.1

Status: implementation slice.

Baseline: `main@038d1ccc03df17c93600cb06c3c44b874d7e9b70`.

## Intent

Promote the R3A touched-resource shadow projection into a structurally registered,
cycle-instance-bound semantic input and derive a bounded read-only obligation
inventory without changing Agent Cycle close judgment.

R3B1 remains shadow. It does not resolve obligations, mutate domain authorities,
introduce async lifecycle states, or authorize close enforcement.

## Reduction before addition

Before creating an obligation consumer, R3B1 reduces the current touched-resource
surface:

- remove `sourceSummary`; consumers must inspect canonical resources instead of a
  redundant aggregate whose `originCount` semantics were ambiguous;
- remove dormant `pull-request-slot` and `pull-request` kinds from the current
  semantic resource contract because there is no strongly cycle-bound runtime
  producer for them;
- exclude AMBIENT direct RemoteCanonical records from the promoted semantic
  resource set; they remain observable through `hosted_cycle_records` but cannot
  create obligations;
- make incomplete provider/Work Mode coverage explicit instead of interpreting an
  absent resource as proof that no operation happened.

History remains recoverable in Git. No compatibility reader is added for the
shadow-only `AgentCycleTouchedResourceSet 0.1`.

## Contracts

### AgentCycleTouchedResourceSet 0.2

Top-level fields:

- `schemaVersion`
- `repository`
- `cycleInstanceId`
- `resources`
- `coverage`
- `readOnly=true`
- `semanticAuthority=false`
- `authorizesMutation=false`
- `resourceSetHash`

Current semantic resource kinds:

- `git-branch`
- `git-path`
- `domain-subject`
- `lease-scope`
- `coordination-lease`

Coverage is explicitly epistemic:

```json
{
  "status": "UNKNOWN",
  "scope": "strong-hosted-records",
  "reasonCode": "AGENT_CYCLE_PROVIDER_COVERAGE_INCOMPLETE"
}
```

This status is not a failure and does not change close judgment. R5 owns the
provider/Work Mode bridge required before absence can be meaningful.

### AgentCycleObligationInventory 0.1

The inventory is a deterministic read-only projection of the promoted resource
set plus the optional explicit `workRef` from `AgentCycleContext 0.4`.

It contains:

- exact `cycleInstanceId` and `resourceSetHash` binding;
- optional exact `workRef`;
- inherited coverage;
- a canonical list of obligations;
- `enforcementEligible=false`;
- non-authoritative/read-only flags;
- `inventoryHash`.

Bounded obligation kinds:

- `git-branch-disposition`
- `work-disposition`
- `write-lifecycle-disposition`

Derivation:

- explicit `workRef` -> one `work-disposition`;
- `git-branch` and `git-path` -> one deduplicated branch disposition per branch;
- explicit `continuation/continuation` domain subject -> `work-disposition`;
- `lease-scope` -> `write-lifecycle-disposition`;
- `coordination-lease` is evidence for R3B2, not an additional obligation;
- unknown/generic domains do not receive inferred disposition semantics.

The inventory does not contain resolution/disposition state. R3B2 owns that.

## Hosted materialization

Reuse the existing successful Hosted close observation. The same comments snapshot
materializes both:

- `agent-cycle-touched-resources.json`
- `agent-cycle-obligation-inventory.json`

Both remain best-effort shadow artifacts. A projection failure writes a diagnostic
and must never alter trace/lease/closure judgment. No extra polling/fetch is
introduced.

## Explicit exclusions

R3B1 does not:

- change `AgentCycleClosure 0.1`;
- introduce `PENDING` or `WAITING`;
- seal the cycle or order late events;
- resolve Work/lease/branch lifecycle;
- create PR obligations;
- infer Work from branch, worker or PR;
- make artifact expiry a domain disposition;
- create a writer, CAS surface or mutable cycle authority.

## Qualification gates

- resource schema and Python validator structural parity;
- obligation schema and Python validator structural parity;
- deterministic ordering and dedupe;
- `workRef` produces exactly one work obligation;
- branch/path collapse to branch-level disposition;
- generic domain subject remains non-obligating;
- lease scope produces one lifecycle obligation;
- coordination lease alone does not duplicate the lifecycle obligation;
- AMBIENT RemoteCanonical cannot enter the promoted resource set;
- create/merge PR projection fails explicitly until a strong producer exists;
- rehashed authority/enforcement tampering fails semantic validation;
- inventory binds exact resourceSetHash/cycleInstanceId;
- Hosted shadow materialization reuses one comments observation;
- full existing toolbox/semantic/workflow gates remain green.

## Admission to R3B2

R3B2 is admitted when R3B1 is integrated and the live Hosted close can materialize
both artifacts without changing close behavior. Resolution must reuse existing
domain inspectors and remain shadow.
