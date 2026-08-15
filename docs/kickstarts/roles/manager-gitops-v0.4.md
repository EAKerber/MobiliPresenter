# MobiliPresenter

## Kickstart — Manager / GitOps v0.4

**Peer Recovery shadow experiment · additive over v0.3**

This document is the current versioned runtime contract for the `manager-gitops` role. It normatively imports [`manager-gitops-v0.3.md`](./manager-gitops-v0.3.md); every v0.3 rule remains in force unless this document explicitly narrows or extends it.

The v0.4 increment adds a bounded **Peer Health / Peer Recovery shadow protocol**. It does not grant task-control authority, semantic product authority, peer identity takeover, lease takeover, or continuation takeover.

## 1. Capability participation

Capabilities may declare `supervisorParticipation`:

- `active` — default when the field is absent; experimental gates may participate in Maintenance/Scheduler recommendations under the existing rules.
- `isolated` — the capability remains discoverable, gated and auditable, but its experimental gates do **not** alter the canonical Maintenance recommendation or SchedulerPlan.

The field is lifecycle-controlled. Change it only through the deterministic `supervisor-participation` capability transition with evidence/readback.

`peer-recovery` starts as:

```text
policy=experimental
supervisorParticipation=isolated
```

Therefore Peer Recovery shadow work must never be inferred from `SchedulerPlan.focus` and must never retarget the canonical SchedulerPlan.

## 2. Supervisor Snapshot connector fallback — dedicated artifact route

For connector-backed fallback, use the dedicated GitHub Actions artifact surface instead of generic page/file materialization whenever that surface is available.

The validated sequence is:

1. independently observe current `main`, `coordination/leases`, and `coordination/continuations` heads;
2. find the newest successful **Supervisor Snapshot** workflow run on `main` whose `head_sha` equals the observed current `main` head;
3. list artifacts for that exact run;
4. require an unexpired artifact named exactly `supervisor-snapshot`;
5. download that artifact through the dedicated workflow-artifact download operation;
6. materialize the ZIP locally/read-only;
7. require the expected snapshot payload, including `scheduler-snapshot.json`;
8. validate `scheduler-snapshot.json` with `tools/scheduler_snapshot.py` against the three independently observed authority heads;
9. use only the validated embedded SchedulerPlan.

A generic artifact-read/materialization failure does not authorize reconstruction of the snapshot. If the dedicated artifact route succeeds, it is a read-only peer-runtime remediation for the concrete materialization boundary; if it fails, remain fail-closed.

The dedicated route has been independently proven against the real `supervisor-snapshot` artifact produced by the canonical workflow. This is a transport/runtime-path correction, not a change to Scheduler semantics.

## 3. Peer Recovery shadow probe

Run this probe only when all are true:

```text
peer-recovery policy = experimental
peer-recovery supervisorParticipation = isolated
worker execution guard permits read-only observation/validation
```

The probe runs **after** canonical bootstrap/Scheduler validation when that validation succeeds. If the canonical bootstrap itself fails at the Supervisor Snapshot materialization boundary, the worker may still execute only the health-event portion needed to report that structured runtime failure, provided the Agent Bus remains available.

The probe is not Scheduler work and does not change SchedulerPlan.

### 3.1 Own WorkerObservation

Normalize the current worker into `WorkerObservation 0.1` using `tools/peer_recovery.py` schemas.

Use `authoritySource=git-observed` only for heads independently observed from Git during the current execution.

For the concrete artifact boundary, use exactly this structured failure when applicable:

```json
{
  "code": "RUNTIME_ARTIFACT_MATERIALIZATION",
  "surface": "SUPERVISOR-SNAPSHOT",
  "operation": "ARTIFACT-DOWNLOAD-READ"
}
```

Do not use free-form email text as a failure key.

### 3.2 `worker.health` emission

Use `tools/peer_recovery_bus.py health` to derive the envelope. The tool is pure and does not send email.

Before generating a new envelope, search the Agent Bus for the latest structurally valid `worker.health` event from the same `worker_id` and use it as `--previous` when available.

The emission algorithm intentionally suppresses unchanged transitions and bounds repeated identical failures: failure counts 1, 2 and 3 may produce distinct transition events; counts above 3 remain on the same transition key until state/fingerprint changes.

If `shouldEmit=true`:

1. search Gmail for the exact `event_id`;
2. if already present, do not resend;
3. otherwise send exactly one email to `mobilipresenterchatbuss@gmail.com` whose body contains the generated event JSON without semantic rewriting;
4. read back the message and validate the exact envelope;
5. failure of send/readback/correlation means transport is blocked, not authority failure.

A healthy baseline may be emitted once when no prior health event exists. Do not emit a healthy heartbeat on every scheduled execution.

## 4. Receiving peer health

A received `worker.health` message is transport evidence only.

1. validate its structure with `tools/peer_recovery_bus.py validate-health` when executable;
2. never mark its transported heads `git-observed` merely because they appear in email;
3. independently observe all current Git authority heads;
4. only after exact equality between independently observed heads and the event's claimed heads may the runtime construct the peer observation used for comparison with `authoritySource=git-observed`;
5. preserve the failure as `failureSource=agent-bus` unless independently reproduced locally.

If any authority head differs or cannot be observed, Peer Recovery must classify/fail closed; do not repair or request retry.

## 5. Read-only reproduction

For a structured peer failure on comparable heads, reproduce only the failing surface and only read-only.

For the B artifact case, reproduction means attempting the dedicated Supervisor Snapshot workflow-artifact route from section 2 and validating the resulting snapshot payload without mutation.

Normalize reproduction as `PeerReproduction 0.1`:

```text
mode=read-only
sideEffects=false
surface=SUPERVISOR-SNAPSHOT
```

If the peer failed and the observer passes on the same verified heads, `tools/peer_recovery.py` should classify `PEER_RUNTIME_ASYMMETRY`.

If both fail with the same failure fingerprint, classify the shared failure path; do not infer a project-wide failure from email alone.

## 6. Recovery recommendation transport

Feed normalized observations plus reproduction into `tools/peer_recovery.py`; then use `tools/peer_recovery_bus.py recovery` to derive any transport envelope.

`peer.recovery` is a **non-authoritative shadow recommendation**, not Scheduler dispatch and not task wake-up.

If `shouldEmit=true`, use the same `event_id` search → single send → readback → exact validation discipline as `worker.health`.

Never emit or consume a recovery event to transfer identity, leases, continuations or task control. The envelope validator requires all takeover/task-control flags to remain false.

## 7. Peer-local recovery when the other peer is busy

A deficient worker does not need to wait for another peer merely to use a read-only runtime path that is already defined by this Kickstart.

For the exact `RUNTIME_ARTIFACT_MATERIALIZATION / SUPERVISOR-SNAPSHOT / ARTIFACT-DOWNLOAD-READ` failure, the worker may make **one bounded self-retry per current failure episode** using the dedicated workflow-artifact route from section 2.

This self-retry:

- is read-only;
- does not reactivate or edit the Scheduled Task;
- does not alter Git, ProjectState, leases or continuations;
- does not classify `PEER_RUNTIME_ASYMMETRY` unless comparable peer evidence exists;
- on success, permits the worker to continue canonical snapshot validation and emit a HEALTHY transition;
- on repeated failure, remains DEGRADED/fail-closed and eventually requires peer/human diagnosis rather than looping.

Thus B can recover the known runtime-local artifact path even if A is occupied, while A remains useful for independent asymmetry diagnosis.

## 8. Guards and transport exception

During `READ_ONLY_PREFLIGHT` or `SHADOW_SUPERVISOR`, the only additional effects authorized by this v0.4 experiment are the idempotent Agent Bus sends described here:

- `worker.health` transition evidence;
- `peer.recovery` shadow recommendation evidence.

They are transport-only and never authorize functional work, task wake-up, Git mutation, ownership transfer or semantic decisions.

If the Scheduled Task's own configuration contains a stricter transport guard, that external task configuration must explicitly opt into this v0.4 transport exception before these events may be sent. Repository policy does not silently override a stricter external task guard.

## 9. Anti-loop and fail-closed rules

- Same recovery correlation after one attempted peer recovery must not bounce A↔B indefinitely.
- Heads different/unverifiable → no recovery execution.
- Email-only heads → no recovery execution.
- Side-effectful reproduction → reject.
- Unknown remediation → no arbitrary prompt/memory/runtime mutation.
- `REQUEST_RETRY` never means resume/enable Scheduled Task.
- `PAUSING_UNAVAILABLE` never proves who paused a task or who can resume it.

## 10. Scheduled-test output additions

While this experiment is enabled, append these compact fields to the existing worker receipt when observable:

```text
PEER_RECOVERY_CAPABILITY  EXPERIMENTAL_ISOLATED|N/A|BLOCKED
PEER_HEALTH_EVENT         EMITTED|REUSED|NO_CHANGE|BLOCKED
PEER_EVENT_SEEN           <event_id|none>
PEER_HEAD_COMPARISON      SAME|DIFFERENT|UNVERIFIABLE|N/A
PEER_REPRODUCTION         PASS|FAIL|NOT_ATTEMPTED
PEER_CLASSIFICATION       <classification|N/A>
PEER_RECOVERY_SIGNAL      RECOVERY_READY|RETRY_RECOMMENDED|NEEDS_HUMAN|NONE|N/A
SELF_RETRY                PASS|FAIL|NOT_ATTEMPTED
```

These fields supplement rather than replace the v0.3 canonical Scheduler/authority receipt.

## 11. Promotion boundary

Successful A/B scheduled runs do not automatically make `peer-recovery` canonical and do not automatically change `supervisorParticipation` to `active`.

First collect representative evidence for:

- same-head asymmetry;
- different-head fail-closed behavior;
- Agent Bus idempotence/readback;
- no Scheduler recommendation drift while isolated;
- B self-retry behavior;
- no recovery loops/takeover.

Promotion/activation remains an explicit lifecycle decision with evidence.
