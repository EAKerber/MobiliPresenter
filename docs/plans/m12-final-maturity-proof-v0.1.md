# M12 Final Maturity Proof 0.1 — bounded closure plan

Status: `PLANNING / READ-ONLY EVIDENCE FIRST`  
Parent roadmap: `docs/plans/m9-m13-closure-v0.1.md`  
Observed baseline: `main@c4809c987c3aa68541b2267aab952d35dd78b121`  
Current ProjectState checkpoint: `M12-AT3D-R5A1-HOSTED-RUNTIME-OBSERVATION-INGRESS-QUALIFIED`  
Current ProjectState next transition: `resolve-m12-at3d-r5a2-work-mode-host-observation-surface-v0.1`

## 1. Decision

Do **not** start M13 yet and do **not** repeat the historical six-run S2 protocol verbatim.

The historical S2 maturity experiment executed and ended `NOT PASSED / HIGH-VALUE FAILURE`. AT2/AT3D and the later R4/R5A1 work subsequently repaired and live-qualified most of the failure modes exposed by S2, but no later artifact recomposed that evidence against the explicit M12 maturity gate and declared:

```text
checkpoint = M12-MATURITY-PROOF-0.1-PASSED
nextTransition = implement-m13-reflection-and-operational-quiescence-v0.1
```

Therefore M12 remains unclosed until one final bounded proof binds the current evidence to the original comparable invariants and runs only the probes whose evidence is still missing.

This plan is derived evidence only. It does not mutate ProjectState, Work, Coordination, Capability, policy, Registry or product state and does not authorize any mutation.

## 2. What the final proof must establish

The controlling M12-S2 gate in `m9-m13-closure-v0.1.md` requires:

1. `pavedPathCompletionRate=1.0` for the operations **currently admitted** by policy;
2. zero false PASS;
3. zero scope escape;
4. zero mutation in `main` by qualification work;
5. durable terminal disposition;
6. `residualBranchCountAfterCleanup=0` for proof-owned branches;
7. Manager/GitOps A and B converge over the same independently observed authority heads;
8. provider/carrier evidence and canonical execution remain distinct.

Historical protocol variables such as branch allocation, execution context and provider are recorded as protocol deltas. They are not silently treated as comparable invariants when the current system has evolved past S2.

## 3. Current admitted operation set

The denominator for `pavedPathCompletionRate` is derived from the current `AgentToolPolicyCatalog 0.3`, not from obsolete experiment expectations.

### Manager/GitOps

Current policy admits:

- `inspect-and-plan` read-only inspection paths;
- `governed-mutation` for `git.files.mutate` with `mutation-execute`;
- the required lifecycle/lease/CAS guards around that mutation.

The mutating path is already live-qualified by AT3C/AT3D and must be **reused as evidence**, not replayed merely to increase run count.

### UI/UX

Current policy admits:

- `bootstrap-discovery`;
- `inspect-and-plan` read-only operations;
- `git.files.mutate` only as `plan-only` under `ui-owned-git`.

There is no current UI `mutation-execute` mode. The final maturity proof therefore expects a cold UI role observation to remain read-only / `ROLE_NOOP` with no role-scoped Git write. Treating absence of an unadmitted UI mutation as a failure would make the proof contradict current policy.

## 4. Evidence matrix before new probes

No row below is promoted to final PASS merely because evidence exists. `EVIDENCE_READY` means the final proof can bind immutable existing evidence instead of replaying the operation.

| M12 maturity obligation | Current disposition | Evidence / reason |
|---|---|---|
| Manager governed mutation reaches canonical apply/readback/close | `EVIDENCE_READY` | AT3D D2 live qualification; PR #164 records Hosted close PASS + multi-path GitMutationBundle readback PASS |
| Lease lifecycle acquire/release is attributable and clean | `EVIDENCE_READY` | AT3C live qualification/fix lineage; PR #161 records acquire -> two mutations -> release -> post-release block, with `RELEASED` and `leases=[]` before close attribution fix |
| Delayed result does not force replay/new begin | `EVIDENCE_READY` | R4A Hosted qualification: stable seal + late correlated result + retry PASS, no replay |
| Waiting is honest and does not poll/replay | `EVIDENCE_READY` | R4B Hosted qualification: first close WAITING, late result -> same-cycle PASS, polling=0, replay=0 |
| Release cannot overtake pending mutation | `EVIDENCE_READY` | R4C Hosted qualification: predecessor WAITING before attempt/write; UNKNOWN fail-closed; disjoint branch clear |
| Provider observation and carrier execution remain distinct | `EVIDENCE_READY` | R5A1 Hosted qualification + RemoteCanonical carrier contract; R5A1 explicitly proves ingress, not Work Mode discovery or carrier selection |
| Same-head classification fails closed on divergence | `EVIDENCE_READY_SUPPORTING` | peer-recovery canonical lifecycle gates include same-head classification and different-head fail-closed; this is mechanism evidence, not a substitute for two current worker observations |
| Manager A/B current convergence on same authority heads | `PROBE_REQUIRED` | no current M12 closure binds two independent current observations as the maturity gate requires |
| Current UI role confinement / ROLE_NOOP under current policy | `PROBE_REQUIRED` | historical S2 UI remained untested; current policy is now explicitly plan-only for UI mutation |
| Final completion-rate calculation over current admitted proof cases | `PROBE_REQUIRED` | must be calculated from the final evidence set rather than inferred from scattered qualifications |
| Final terminal disposition persisted | `PROBE_REQUIRED` | final composite proof itself needs an explicit terminal closure; prior operation receipts are inputs, not the M12 closure |
| Final proof branch cleanup = zero residual | `PROBE_REQUIRED` | must be read back after final qualification branches are collected |

## 5. R5A2 disposition relative to M12

R5A2 remains `UNKNOWN` because the Work Mode host does not currently expose a repository-observable, trustworthy complete per-run ToolSurface inventory and completeness fact.

That is **not** the historical M12 RemoteCanonical provider gap.

M12-RP1/S2 required a canonical remote execution carrier with plan/apply/readback and fail-closed provider behavior. AT2/AT3D/R4 subsequently produced and qualified that path. R5A2 is a later ergonomics/integration boundary for automatic Work Mode host observation.

Therefore:

- do not mark R5A2 PASS;
- do not fabricate Work Mode discovery;
- do not make R5A2 a retroactive blocker for currently admitted Hosted/GitHub operations whose carrier is already explicit and qualified;
- preserve the R5A2 host-side re-entry condition independently of the M12 maturity result.

## 6. Minimal new live probes

### Probe A/B — independent same-head convergence

Purpose: satisfy the only worker-convergence obligation not already bound by later evidence.

Use the registered Agent Ops carrier on a dedicated qualification branch. Do not create a new unregistered workflow because that can perturb OperationalSemantics coverage.

Run **independent jobs** for:

- `manager-gitops-a`;
- `manager-gitops-b`.

Each job must freshly observe and record, at minimum:

- exact `main` head;
- exact Coordination authority head;
- exact Continuation/Work authority head;
- ProjectState hash;
- ProjectMachine/source inspection hash or equivalent deterministic composed observation;
- role + declared intent;
- status and blockers;
- `semanticAuthority=false` / no mutation authority from the projection.

The comparison PASS condition is:

- both jobs independently report the same pinned authority heads;
- both derive compatible status/plan over those heads;
- no job writes Git/Work/Coordination/ProjectState;
- no transport claim substitutes for Git observation;
- disagreement or an unobserved head is `UNKNOWN`/FAIL, never coerced to convergence.

This probe is read-only. It does not repeat the already-qualified Manager mutation lifecycle.

### Probe UI — cold role confinement

Run a third independent Agent Ops job as `ui-ux-a` using the same pinned `main` baseline.

Require:

- cold `begin`/discovery from current role + `inspect-and-plan` intent;
- read-only operations available according to current policy;
- `git.files.mutate` is not mutation-executable for UI under current policy;
- no product/ViewerNext/authority mutation;
- explicit `ROLE_NOOP`/read-only disposition for the maturity probe;
- zero branch/path mutation.

A UI mutation is **not** introduced merely to imitate historical S2. If policy later admits UI mutation-execute, that is a new protocol revision and must be qualified separately.

## 7. Qualification topology

Use a dedicated qualification branch derived from the then-current `main`.

Preferred shape:

```text
existing Agent Ops workflow
  -> manager-a independent job
  -> manager-b independent job
  -> ui independent job
  -> aggregate read-only maturity evidence
  -> ordinary regression/semantic gates
```

Qualification-only scripts may exist on the qualification branch but are not product/runtime surfaces and must not survive into the final semantic tree unless a reusable repo-owned need is independently justified.

No Scheduled Tasks are required merely to reproduce historical timing. Scheduled timing was an experimental carrier variable; the remaining gates concern current independent observations and the already-qualified lifecycle semantics.

## 8. Aggregate evidence and completion rate

The qualification artifact should contain a derived, non-authoritative summary with at least:

```text
baseline main / coordination / continuation heads
existing evidence references consumed
managerA observation
managerB observation
ui observation
admitted proof cases
completed proof cases
pavedPathCompletionRate
falsePassCount
scopeEscapeCount
mainMutationCount
terminalDisposition
proofOwnedBranches
residualBranchCountAfterCleanup
providerCarrierSeparation
```

No new durable schema is justified yet. The qualification JSON may remain a workflow artifact. The durable result is a reviewed closure document that cites the immutable run/artifact/PR evidence.

`pavedPathCompletionRate` is:

```text
completed admitted proof cases / admitted proof cases
```

Only cases admitted by the current policy are in the denominator. A correctly blocked/unavailable operation counts as completed only when the expected contract is fail-closed and the observed blocker is the intended terminal result; UNKNOWN never becomes PASS.

## 9. Cleanup and closure

The final proof uses two separate branches when needed:

1. a disposable qualification branch for the Agent Ops probes;
2. a normal closure branch containing only the reviewed M12 closure document (and ProjectState later, in a separate state-only transition).

Sequence:

1. run qualification and retain run/artifact ids;
2. close/delete qualification-only PR if one was needed;
3. let Branch Hygiene collect the disposable qualification branch through its normal writer;
4. independently read back that all proof-owned disposable branches are gone;
5. materialize `docs/experiments/m12-final-maturity-proof-closure-v0.1.md` with the evidence matrix and final metrics;
6. run normal CI on the closure PR;
7. only if every M12 gate is PASS, reconcile ProjectState separately with the canonical writer to:

```text
checkpoint = M12-MATURITY-PROOF-0.1-PASSED
nextTransition = implement-m13-reflection-and-operational-quiescence-v0.1
```

If any required gate is UNKNOWN or FAIL, keep M12 open and record the precise blocker. Run count alone never promotes the milestone.

## 10. Death conditions

Stop and do not promote M12 if the proof requires any of the following:

- direct mutation in `main` as a probe;
- weakening UI policy to create a mutation just for the experiment;
- a new provider/router/authority solely for proof orchestration;
- shell/Contents fallback that bypasses the canonical path;
- treating R5A2 UNKNOWN as PASS;
- treating a deterministic unit test as the two-worker live observation;
- silently changing the admitted operation denominator after observing failures;
- keeping qualification scaffolding as production runtime without independent justification;
- advancing ProjectState before qualification cleanup/readback is complete.

## 11. Implementation decision

The next implementation is **not** a persistent `m12_maturity_inspect.py` unless the qualification shows a reusable deterministic aggregation need beyond this one closure.

Start with qualification-only code attached to the registered Agent Ops carrier. Prefer removal after evidence generation. Only promote an evaluator to repo runtime if a later M13/M14 consumer proves the same ownership, lifecycle and trust boundary.

This follows the repository maxim: remove/derive/unite before creating another persistent component.

## 12. Proposed operational sequence

```text
plan qualification
  -> run A/B independent same-head probe
  -> run UI cold confinement probe
  -> aggregate existing + new evidence
  -> Branch Hygiene cleanup/readback
  -> reviewed M12 final closure
  -> canonical ProjectState transition if and only if all gates PASS
  -> M13 RQ1/RQ2 implementation
```

Until that sequence reaches the state transition, the current ProjectState remains authoritative and unchanged.
