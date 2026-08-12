# Git Ops 1.3 experimental — Coordination Leases

Status: implementation plan / not yet policy

Base observed: `main@e4638530154841663630dbb603bed39495a4b462`

Operational branch: `ops/git-ops-1.3-coordination-leases`

Authority candidate: `coordination/leases`

Decision record: `docs/adr/0004-coordination-leases.md`

## Objective

Prove a minimal coordination layer for rare shared resources without converting the repository into a general agent scheduler and without changing product semantics.

The experiment must preserve Git Ops 1.2 as the canonical operational policy until all acceptance gates are proven.

## Invariants

- `main` remains untouched during exploration;
- `ops/state/project.json` remains Git Ops 1.2 during the experiment;
- `AGENTS.md` does not require leases yet;
- no semantic changes under `scene-core/**` or Viewer Next Engine/UI paths;
- authority is central and remote;
- lease mutation fails closed when authority cannot be observed;
- authority ref is never force-updated;
- multi-resource acquire is a single transaction;
- every mutating operation performs readback.

## Phase 0 — architecture and scaffolding

Deliverables:

- ADR-0004 with alternatives, authority, CAS, clock, identity, overlap, recovery, break-glass and rollback;
- this implementation plan;
- branch isolated from `main`.

Gate `GL13-00`:

- branch parent is the observed main SHA;
- only operational documentation changed;
- `main` head remains unchanged.

## Phase 1 — deterministic local core

Implement the state and resource engine independently from GitHub transport.

Suggested structure:

```text
tools/coordination.py
ops/schemas/coordination-state.schema.json
tools/tests/test_coordination.py
```

Core responsibilities:

1. canonical owner validation;
2. normalize `file:`, `path:` and `branch:` resources;
3. deterministic glob compiler;
4. overlap/conflict resolution;
5. batch normalization + lexical ordering;
6. logical expiration;
7. plan intent;
8. plan acquire all-or-nothing;
9. plan renew;
10. plan release / release-mine;
11. plan cleanup with owner/session guards;
12. stable transition/event description suitable for commit audit.

No network calls inside this core.

### Phase 1 tests

`GL13-01` same file conflict.

`GL13-02` file ↔ glob conflict.

`GL13-03` conservative glob ↔ glob conflict.

`GL13-04` branch namespace conflict.

`GL13-05` A+B succeeds completely or not at all.

`GL13-06` resource input order does not change canonical result.

`GL13-07` expired lease does not block.

`GL13-08` renew extends only owner session lease.

`GL13-09` release-mine removes only owner session entries.

`GL13-10` different session cannot overwrite/release foreign lease.

`GL13-11` invalid/ambiguous resource fails before state mutation.

## Phase 2 — GitHub authority transport

Create `coordination/leases` from a known durable commit after Phase 1 is green.

Initial state:

```json
{
  "schemaVersion": "CoordinationState 0.1",
  "revision": null,
  "intents": [],
  "leases": []
}
```

Implement a transport adapter around the same deterministic core:

```text
observe authority head H
observe GitHub API authorityNow
read state at H
plan transition
write new state blob/tree
create commit with parent H
advance coordination/leases force=false
readback ref
readback state
validate event/result
```

The adapter must expose explicit errors rather than retrying blindly:

- `COORDINATION_AUTHORITY_UNAVAILABLE`
- `COORDINATION_TIME_UNAVAILABLE`
- `COORDINATION_STATE_INVALID`
- `COORDINATION_REF_DRIFT`
- `COORDINATION_READBACK_MISMATCH`
- `LEASE_CONFLICT`
- `LEASE_NOT_OWNER`

A caller may reobserve and retry a ref-drift transition, but the mutation primitive itself never silently retries using stale intent.

### Phase 2 concurrency proof

Build two candidate child commits from the same head H, each acquiring the same test resource with a distinct owner.

Attempt both non-force ref advances. Acceptance requires:

- exactly one ref update succeeds;
- losing commit remains unreferenced or non-authoritative;
- readback names exactly one owner;
- loser can reobserve and receives `LEASE_CONFLICT` while winner is valid.

`GL13-12`: real single-winner CAS proof.

## Phase 3 — toolbox surface

Only after Phase 2 passes, wire experimental commands into `tools/agent.py`.

Target interface:

```bash
python3 tools/agent.py lock status --json
python3 tools/agent.py lock intent <resource...> --reason "..." --session <id> --role <role>
python3 tools/agent.py lock acquire <resource...> --reason "..." --ttl 60m --session <id> --role <role>
python3 tools/agent.py lock renew --mine --session <id>
python3 tools/agent.py lock release <resource...> --session <id>
python3 tools/agent.py lock release --mine --session <id>
```

During the experiment, `operations.commands` in `project.json` is not expanded. Experimental command availability is code-level and documented as provisional; canonical state remains 1.2 until promotion.

The official write guard will initially be callable explicitly by tooling that performs shared-resource writes. It must return:

```text
WRITE_BLOCKED_BY_LEASE
resource: ...
owner: ...
branch/pr: ...
expiresAt: ...
```

`GL13-13`: tooling blocks foreign valid lease.

`GL13-14`: tooling allows same-session owner.

`GL13-15`: authority observation failure blocks guarded write.

## Phase 4 — experimental CI gate

Add a dedicated workflow or job that:

1. checks out PR head;
2. determines base/head diff;
3. reads coordination authority remotely;
4. resolves modified shared resources;
5. evaluates valid leases at authorityNow;
6. validates lease branch/PR owner;
7. emits explicit diagnostics.

Initial behavior:

- runs on operational test PRs and selected shared surfaces;
- is not yet a repository-wide required check;
- absence of lease is informational while experimental;
- presence of a valid foreign lease over a changed resource is a failure.

`GL13-16`: bypassing tooling and committing under foreign lease produces `LOCK_OWNERSHIP_VIOLATION`.

`GL13-17`: independent resource remains green while another resource is leased.

## Phase 5 — failure recovery and cleanup

Prove:

- orphan lease expires and stops blocking;
- physical cleanup is safe after logical expiry;
- PR-closed cleanup checks PR/branch/session correspondence;
- cleanup cannot remove a still-valid foreign session;
- detached HEAD / GitHub Actions can read and evaluate authority;
- restart with same session recovers ownership;
- restart without session can observe but not impersonate owner.

`GL13-18` through `GL13-23` cover the cases above.

Break-glass is added only after ordinary ownership/release is stable and must require expected revision + explicit reason.

## Phase 6 — real UI × Engine exercise

Use a non-semantic shared test surface; do not edit product files merely to demonstrate conflict.

Scenario:

1. UI identity publishes intent and then acquires test shared resource;
2. Engine identity reads the same authority;
3. Engine conflicting acquire is rejected;
4. Engine acquires independent test resource;
5. UI releases;
6. Engine acquires formerly blocked resource;
7. readback/audit prove the sequence.

If a real integration file is used for the final demonstration, the test must avoid semantic content changes and revert any synthetic marker before integration.

`GL13-24`: real UI × Engine handoff proof.

## Phase 7 — promotion decision

Promotion to canonical Git Ops 1.3 is a separate change.

Only consider it when:

- GL13-00 through GL13-24 are green or explicitly superseded;
- operational cost is acceptable;
- no unexplained stale-lock incident remains;
- rollback has been exercised at least once in a test branch;
- UI and Engine handoff commands are concise and documented.

Promotion would then, and only then, include:

- ADR-0004 `accepted`;
- `AGENTS.md` shared-resource lease rule;
- `ops/state/project.json` phase/command update;
- schema update for canonical GitOps phase;
- required CI policy for selected shared resources.

If the experiment fails, leave Git Ops 1.2 untouched, remove provisional command/gate changes from the operational PR and archive the experiment evidence.

## Shared-resource seed set

The first production candidate set, after experimental proof, is:

```text
viewer-next/src/bootstrap.ts
viewer-next/index.html
viewer-next/package.json
viewer-next/tsconfig.json
viewer-next/src/api/**
.github/workflows/**
integration/viewer-parallel-v0.1
```

This list is not activated during Phase 1/2 tests.

## Definition of Done for the experiment

- architecture documented;
- deterministic core implemented;
- unit/concurrency tests green;
- authority branch operational;
- real CAS race demonstrated;
- toolbox commands operational;
- tooling guard demonstrated;
- CI bypass detection demonstrated;
- TTL/recovery demonstrated;
- UI × Engine exercise completed;
- zero semantic product changes;
- rollback evidence recorded;
- explicit promote/reject decision recorded.
