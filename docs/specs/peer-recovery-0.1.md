# Peer Recovery 0.1 — experimental Manager/GitOps capability

Status: **experimental / gated**. This increment does not change Scheduler semantics, `maintenance_inspect.py`, or Manager/GitOps Kickstart v0.3.

## Purpose

Peer Recovery lets two worker instances of the same logical role compare normalized operational evidence without transferring authority. The first target is `manager-gitops-a` / `manager-gitops-b` and the `Supervisor Snapshot` artifact-materialization asymmetry.

The capability separates three layers:

```text
runtime / Agent Bus / Git observations
              ↓ normalize
        WorkerObservation 0.1
              ↓
      PeerRecoveryInspection 0.1
              ↓
        PeerRecoveryPlan 0.1
              ↓
 authorized runtime adapter (later)
```

`tools/peer_recovery.py` is intentionally pure: no Gmail, network, Git mutation, task control, leases, continuations, or event sending.

## Authority boundary

A worker-health email is a signal only. Authority heads are comparable only when each normalized observation declares `authoritySource=git-observed` and provides all three SHA-1 heads:

- `control` (`main` for the current Manager/GitOps contract);
- `coordination` (`coordination/leases`);
- `continuation` (`coordination/continuations`).

`transport-claimed` heads are preserved as untrusted data but always classify as `AUTHORITY_UNVERIFIABLE`. Different verified heads classify as `AUTHORITY_DIVERGENCE`. Both paths fail closed and forbid repair/retry execution.

## Worker states

The normalized state vocabulary is deliberately small:

- `HEALTHY`
- `DEGRADED`
- `SILENT_UNKNOWN`
- `PAUSING_UNAVAILABLE`

`RECOVERY_READY` is a recovery **signal**, not a worker health state. This avoids conflating observed health with a proposed next action.

No state grants task-control authority. `PAUSING_UNAVAILABLE` explicitly does not prove that the worker paused itself or that a peer can resume it.

## Failure fingerprint

Failures use a stable structured tuple:

```json
{
  "code": "RUNTIME_ARTIFACT_MATERIALIZATION",
  "surface": "SUPERVISOR-SNAPSHOT",
  "operation": "ARTIFACT-DOWNLOAD-READ"
}
```

The fingerprint is the stable SHA-256 hash of exactly `{code, surface, operation}`. Free-form narrative is never a primary key.

## Reproduction contract

A reproduction is accepted only when:

- actor is the observer worker;
- mode is exactly `read-only`;
- `sideEffects=false`;
- the surface matches before the result can classify the peer failure;
- `PASS` carries no reproduction failure;
- `FAIL` carries a structured failure.

A matching failure on the same verified heads is `SHARED_SURFACE_FAILURE`. A healthy observer pass against the same surface/heads while the peer fails is `PEER_RUNTIME_ASYMMETRY`.

## Closed plan actions

- `NOOP`
- `OBSERVE`
- `REPRODUCE`
- `REPAIR_SHARED`
- `REQUEST_RETRY`
- `QUARANTINE`
- `NEEDS_HUMAN`

`REPAIR_SHARED` is only emitted when a read-only reproduction has identified the same shared failure and a validated remediation is explicitly scoped `shared-gitops` with `authorityBasis=canonical-policy`. The plan itself remains read-only and performs no mutation.

`REQUEST_RETRY` never means task control. It means the runtime may signal the named peer to retry if/when that worker executes and the runtime transport contract permits it.

## Self-recovery when the healthy peer is busy

For runtime-local asymmetry, the planner prefers the deficient peer as the recovery executor:

```text
classification = PEER_RUNTIME_ASYMMETRY
remediation.scope = peer-runtime
remediation.validated = true
        ↓
action = REQUEST_RETRY
signal = RECOVERY_READY
recommendedExecutor = peer
```

This allows B to consume a proven runtime-local remedy on its next execution without requiring A to perform the recovery. It does **not** allow B to reactivate its Scheduled Task, modify its prompt, assume A's identity, acquire A's lease, or take over a continuation.

If the peer remains on the same failure after one recovery attempt (`recoveryContext.attemptCount >= 1`), the planner emits `NEEDS_HUMAN` rather than bouncing recovery A↔B.

## Agent Bus envelope

Recommended transport type: `worker.health`.

Minimum body:

```json
{
  "type": "worker.health",
  "event_id": "worker.health:<worker_id>:<transition-id>",
  "worker_id": "manager-gitops-b",
  "role_id": "manager-gitops",
  "state": "DEGRADED",
  "failure": {
    "code": "RUNTIME_ARTIFACT_MATERIALIZATION",
    "surface": "SUPERVISOR-SNAPSHOT",
    "operation": "ARTIFACT-DOWNLOAD-READ"
  },
  "failure_fingerprint": "<sha256>",
  "observed_authority_heads": {
    "control": "<sha>",
    "coordination": "<sha>",
    "continuation": "<sha>"
  },
  "consecutive_failure_count": 3,
  "last_known_good": null
}
```

The bus envelope is not authority; the receiver must independently reobserve Git before marking heads `git-observed`.

Telemetry should be transition-driven, not one healthy heartbeat per run. Emit immediately on state/fingerprint transition and recovery outcome. A future liveness collector may emit bounded quiet-period checkpoints so `SILENT_UNKNOWN` can be inferred from an external expected-run source, but Scheduled Task inventory/control is explicitly outside Peer Recovery 0.1.

Repeated `event_id` values are normalized/deduplicated. Identical normalized input yields the same inspection/plan hashes and recovery key.

## Concrete B case

Normalized peer evidence:

```text
peer = manager-gitops-b
state = DEGRADED
failure.code = RUNTIME_ARTIFACT_MATERIALIZATION
failure.surface = SUPERVISOR-SNAPSHOT
peer fails = true
observer reproduction = PASS
same verified authority heads = true
validated remediation = USE_DEDICATED_WORKFLOW_ARTIFACT_DOWNLOAD
remediation scope = peer-runtime
```

Expected classification and plan:

```text
PEER_RUNTIME_ASYMMETRY
REQUEST_RETRY
RECOVERY_READY
recommendedExecutor = peer
```

This is deliberately not a canonical project failure and not a `REPAIR_SHARED` case.

## Gates

1. deterministic plan/hash;
2. same-head peer failure classification;
3. different-head comparison fails closed;
4. read-only reproduction produces classification without side effects;
5. repeated event/idempotence;
6. concrete B artifact-materialization recovery classification.

Additional negative tests cover transport-derived authority, divergent-head repair prevention, task/identity/lease/continuation takeover boundaries, side-effectful reproduction rejection, and A↔B recovery loops.

## Not in 0.1

- no Scheduler or Maintenance integration;
- no Gmail client;
- no Scheduled Task control/discovery;
- no automatic task resume;
- no lease/continuation takeover;
- no direct Git repair executor;
- no canonical promotion based on this first case;
- no Kickstart v0.3 change.
