# R8 historical close compatibility retirement — 2026-09-21

Status: **candidate measurable subtraction after PR #332 integrated shared hosted issue-bus I/O**.

## Purpose

R6h and R6l introduced a narrow hosted compatibility route so one historical Agent Cycle could be re-observed with the then-current carrier after its first canonical close returned a bounded historical failure signature.

The fresh R6 canary later proved the current stack end to end, R7 promoted the semantic paved path, and R8 is now removing migration-only machinery. The historical second-close route is no longer part of the desired runtime model.

This slice restores a single hosted close path:

`current begin artifact -> canonical hosted close once -> PASS / WAITING / BLOCKED / UNKNOWN`

A non-PASS close may still be projected as WAITING when current read-only observation proves a named terminal is pending. It is not re-executed through a second compatibility runner.

## Removed

- workflow eligibility matching for historical compatibility signatures;
- checkout of the current hosted carrier solely to re-run an older close;
- `python -m tools.agent_cycle_close_recovery.hosted close`;
- `tools/agent_cycle_close_recovery/hosted.py`;
- the R6l recovery-diagnostic path owned only by that runner;
- dedicated hosted compatibility workflow/diagnostic regressions.

## Preserved

- R6g write-lease BLOCKED-terminal reconciliation remains canonical safety behavior;
- `agent_cycle_close_recovery` read-only proof primitives remain available;
- R6i-R6k `AgentCycleNonInterferenceReadback` validation/generation remains provisionally retained because unrelated authority drift can be a legitimate concurrent-close case;
- canonical Agent Cycle close, Work/Coordination/Delivery authorities, CAS/readback and UNKNOWN/BLOCKED semantics remain unchanged;
- WAITING remains observational and non-replaying.

No replacement runtime module, authority, lifecycle, state, workflow, public command, compatibility wrapper or provider selector is added.

## Accounting

Compared with `main=6f64fd3a07a1780a0de6cb7f32f8832a1eab494b` before documentation:

- runtime/workflow additions: 5 lines;
- runtime/workflow deletions: 372 lines;
- runtime/workflow net: **-367 lines**;
- dedicated tests removed: 153 lines;
- new runtime modules: 0;
- new public APIs: 0;
- new authorities/state/lifecycles/workflows: 0;
- productive close executions in the hosted workflow: **2 -> 1**.

## Qualification

Exact-head Agent Ops, Coordination Guard and Supervisor Snapshot must PASS with real jobs.

Regression coverage must prove:

- the hosted workflow contains exactly one canonical close invocation;
- no `close_recovery` branch or hosted compatibility runner remains;
- current close failures remain fail-closed or become WAITING only through the existing observational classifier;
- canonical non-interference evidence continues to validate independently of the retired hosted runner.

## Stop condition

If a current-generation cycle created and closed entirely by the current stack requires a second productive close invocation to reach the correct result, this retirement is invalid and the recurring semantic need must be modeled explicitly. Historical compatibility alone is not sufficient reason to restore the runner.

After integration, observe real recurrence of non-interference. Keep R6i-R6k as safety primitives if current cycles use them; otherwise they become the next deletion candidate. Do not delete R6g merely because it originated during R6.
