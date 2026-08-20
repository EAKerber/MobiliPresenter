# MobiliPresenter — Runtime Observation Boundary 0.1

Status: provider-neutral read-only live observation contract for M9-0C.

## Purpose

The runtime capability model distinguishes a logical capability from any concrete provider. Live ProjectMachine observation must preserve the same separation.

A concrete provider may be `gh-api`, a connector-backed runtime, a workflow artifact reader, or another future transport. ProjectMachine must not interpret provider identity as project semantics.

```text
provider/runtime
      ↓ factual observation
RuntimeObservationBundle 0.1
      ↓ validation / canonical projection
ProjectMachineInspection 0.5
```

The boundary is read-only. It does not select providers, acquire leases, route mutations, create authorities, or authorize any write.

## RuntimeObservationBundle 0.1

A bundle is a closed set of four remote observation classes required by the current live ProjectMachine:

- `control`;
- `pullRequests`;
- `coordination`;
- `continuations`.

Every observation declares:

- epistemic `status`: `PASS`, `UNKNOWN`, or `FAIL`;
- `code` when status is not `PASS`;
- `source.providerId` as an open stable string, not a central provider enum;
- `source.capability` describing the logical read function used;
- domain-specific factual `data`.

The bundle itself declares `readOnly=true`, `semanticAuthority=false`, repository identity, and a deterministic `bundleHash`.

Provider provenance belongs to the bundle. It is intentionally projected out of ProjectMachine so equivalent factual observations from different providers produce equivalent canonical sensors and inspection hashes.

## Closed-input rule

When `ProjectMachine --live --observations <bundle>` is selected, the bundle is the complete remote observation input for that inspection.

ProjectMachine must not silently call `gh`, `GhApiTransport`, `GitHubContinuationAuthority`, or any other live adapter to fill a missing or unknown observation. Missing observation coverage is invalid. An explicit `UNKNOWN` remains unknown.

The legacy no-bundle path remains supported:

```text
ProjectMachine --live
  → existing local/live adapters
```

This is compatibility, not a fallback from a supplied bundle.

## Domain projection ownership

Providers transport facts; repository code retains domain semantics.

### Control

The provider supplies control branch and observed SHA. Repository code checks branch identity and SHA form, then emits the existing control sensor projection.

### Pull requests / CI

The provider supplies PR identity, refs, head SHA, CI classification/evidence, and workflow facts. Repository code validates and sorts them into the existing PR sensor projection. Duplicate or malformed observed evidence is `FAIL`, not `UNKNOWN`.

### Continuations / Work

The provider supplies the authority branch/head and raw current ContinuationState items. Repository code validates each item through the canonical Continuation contract and only then derives its operational Work projection.

A provider never decides the meaning of `DONE`, `HANDOFF`, `dependsOn`, blockers, or worker identity.

### Coordination

The provider supplies authority branch/head, raw CoordinationState, and trusted remote time when available. Repository code validates state and performs canonical expiry compaction.

Trusted remote time remains a separate invariant. If state/head are observed but trusted remote time is absent, the canonical sensor is:

```text
UNKNOWN
TRUSTED_REMOTE_TIME_UNAVAILABLE
```

Local clock substitution is forbidden.

## Epistemic rule

The implementation follows:

```text
observed evidence is invalid → FAIL
required evidence is not observable → UNKNOWN
valid complete evidence → PASS
```

A provider may report a payload as observed while the repository projection downgrades the domain result when a repository-owned invariant is missing. The important example is Coordination without trusted remote time.

## Determinism

The key proof is provider neutrality:

```text
provider-a facts == provider-b facts
               ↓
canonical sensors equal
               ↓
ProjectMachineInspection equal
               ↓
inspectionHash equal
```

`providerId` and `source.capability` therefore do not appear in ProjectMachine.

## Boundaries

M9-0C does not introduce:

- provider-backed mutation;
- a universal transport abstraction;
- a new Coordination or Work writer;
- a new authority;
- Scheduler, Maintenance, Routine or ProjectState changes;
- automatic provider selection;
- a new operational action vocabulary.

`RuntimeCapabilityInspection` answers **what the runtime can do**. `RuntimeObservationBundle` records **what the runtime actually observed**. They remain separate contracts.

## CLI

Validate a materialized bundle:

```bash
python3 tools/runtime_observations.py validate runtime-observations.json --json
```

Consume it as the closed live input:

```bash
python3 tools/project_machine.py inspect \
  --live \
  --observations runtime-observations.json \
  --json
```

Using `--observations` with `--local` or `--base` is invalid.

## Acceptance proof

A runtime without local `gh` may externally observe:

```text
control          PASS
pullRequests     PASS
continuations    PASS
coordination     UNKNOWN: TRUSTED_REMOTE_TIME_UNAVAILABLE
```

The resulting ProjectMachine must preserve those statuses independently. It must not collapse the result into a global GitHub transport failure and must not elevate Coordination to `PASS` by using local time.
