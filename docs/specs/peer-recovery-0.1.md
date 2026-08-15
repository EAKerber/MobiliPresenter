# Peer Recovery 0.1 — experimental Manager/GitOps capability

Status: **experimental / gated / supervisor-isolated**. Scheduler routing semantics remain canonical and unchanged. `maintenance_inspect.py` now recognizes explicit capability participation so an isolated experiment can be present without changing its recommendation, and Manager/GitOps v0.4 defines the bounded scheduled shadow protocol while preserving v0.3 as historical/versioned contract.

## Purpose

Peer Recovery lets two worker instances of the same logical role compare normalized operational evidence without transferring authority. The first target is `manager-gitops-a` / `manager-gitops-b` and the `Supervisor Snapshot` artifact-materialization asymmetry.

The capability separates deterministic planning from transport/runtime execution:

```text
runtime / Agent Bus / Git observations
              ↓ normalize
        WorkerObservation 0.1
              ↓
      PeerRecoveryInspection 0.1
              ↓
        PeerRecoveryPlan 0.1
              ↓
      peer_recovery_bus.py
   deterministic envelopes only
              ↓
 authorized runtime transport adapter
```

`tools/peer_recovery.py` is intentionally pure: no Gmail, network, Git mutation, task control, leases, continuations, or event sending.

`tools/peer_recovery_bus.py` is also pure. It derives and validates idempotent `worker.health` / `peer.recovery` envelopes but does not send them. Gmail remains an external non-authoritative transport layer.

## Capability participation

`peer-recovery` is registered as:

```text
policy=experimental
supervisorParticipation=isolated
```

`supervisorParticipation` is a lifecycle-controlled field with two values:

- `active`: existing/default behavior; experimental gate review may affect Maintenance findings;
- `isolated`: capability remains discoverable, gated and auditable, but its experimental gates do not alter the canonical Maintenance recommendation or SchedulerPlan.

The default for legacy capability manifests without this field is `active`, preserving current behavior.

Changing participation is a deterministic `supervisor-participation` capability transition with replayable evidence. This prevents a peer experiment from silently entering Scheduler routing merely because its manifest exists.

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

For the concrete B case, the read-only remediation has been proved against the real GitHub Actions workflow surface:

1. observe the current `main` head;
2. select a successful `Supervisor Snapshot` run on `main` whose `head_sha` exactly matches it;
3. list artifacts for that exact run;
4. require the unexpired artifact named exactly `supervisor-snapshot`;
5. download it through the dedicated workflow-artifact operation;
6. materialize the ZIP read-only;
7. validate its `scheduler-snapshot.json` against independently observed control/coordination/continuation heads.

This route is `USE_DEDICATED_WORKFLOW_ARTIFACT_DOWNLOAD`. It is a runtime transport-path remediation, not a Scheduler semantic change.

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

Manager/GitOps v0.4 additionally allows one bounded self-retry of the exact known Supervisor Snapshot artifact-materialization failure using the dedicated read-only artifact route. This lets B recover the runtime path on its own scheduled execution even when A is occupied. The self-retry alone does not assert `PEER_RUNTIME_ASYMMETRY`; cross-peer classification still requires comparable independently observed authority heads and peer evidence.

Neither form allows B to reactivate its Scheduled Task, modify its prompt, assume A's identity, acquire A's lease, or take over a continuation.

If the peer remains on the same failure after one recovery attempt (`recoveryContext.attemptCount >= 1`), the planner emits `NEEDS_HUMAN` rather than bouncing recovery A↔B.

## Agent Bus envelopes

### `worker.health`

The runtime normalizes its own `WorkerObservation 0.1` and asks `tools/peer_recovery_bus.py health` for a deterministic envelope.

Minimum semantic content includes:

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

The transport envelope is not authority; the receiver must independently reobserve Git before marking heads `git-observed`.

Telemetry is transition-driven rather than a healthy heartbeat every run. An initial healthy baseline may be emitted once. Unchanged transitions are suppressed. Repeated identical failures are bounded into counts 1, 2 and 3; additional repetitions do not generate a new transition until state or fingerprint changes.

### `peer.recovery`

A planner result with a non-`NONE` signal may be rendered by `tools/peer_recovery_bus.py recovery`. The envelope carries classification, action, signal, plan/inspection/recovery hashes, target worker and explicitly false task/identity/lease/continuation takeover flags.

The envelope is a shadow recommendation. It is not Scheduler dispatch and does not wake a Scheduled Task.

Both event types require exact `event_id` search before send plus send → readback → validation/correlation. Repeated event IDs are no-op/reuse, never duplicate sends.

## Scheduled A/B shadow protocol

Manager/GitOps v0.4 defines how scheduled workers exercise this experimental capability while it remains `supervisorParticipation=isolated`:

1. bootstrap and validate the canonical Scheduler path normally;
2. normalize own health from current observations;
3. emit/reuse a transition-driven `worker.health` event when the external Scheduled Task guard opts into the shadow transport exception;
4. validate recent peer health signals structurally;
5. independently reobserve current Git heads before treating transported heads as comparable;
6. reproduce a structured peer failure read-only when safe;
7. run `peer_recovery.py` and, when applicable, derive a deterministic `peer.recovery` shadow envelope;
8. never reinterpret/retarget SchedulerPlan and never use peer recovery as authority for task/identity/lease/continuation takeover.

The task configuration remains an external guard. Repository policy does not silently relax stricter Scheduled Task transport restrictions.

## Concrete B case

Normalized peer evidence:

```text
peer = manager-gitops-b
state = DEGRADED
failure.code = RUNTIME_ARTIFACT_MATERIALIZATION
failure.surface = SUPERVISOR-SNAPSHOT
failure.operation = ARTIFACT-DOWNLOAD-READ
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

Initial deterministic gates:

1. deterministic plan/hash;
2. same-head peer failure classification;
3. different-head comparison fails closed;
4. read-only reproduction produces classification without side effects;
5. repeated event/idempotence;
6. concrete B artifact-materialization recovery classification.

Additional negative tests cover transport-derived authority, divergent-head repair prevention, task/identity/lease/continuation takeover boundaries, side-effectful reproduction rejection, and A↔B recovery loops.

The scheduled shadow experiment additionally seeks evidence for:

- no Scheduler recommendation drift while `supervisorParticipation=isolated`;
- real `worker.health` transition/send/readback idempotence across scheduled A/B runs;
- same-head peer classification from independently reobserved Git authorities;
- B bounded self-retry through the dedicated artifact route;
- no A↔B recovery loop or ownership/task takeover.

## Not in 0.1

- no canonical Peer Recovery participation in Scheduler routing;
- no Scheduler retargeting from Peer Recovery;
- no Gmail client inside the deterministic tools;
- no Scheduled Task control/discovery capability for peers;
- no automatic task resume;
- no lease/continuation takeover;
- no arbitrary prompt/memory/identity repair;
- no direct Git mutation by the planner or bus envelope tool;
- no canonical promotion based on the first B case or the first successful scheduled run.
