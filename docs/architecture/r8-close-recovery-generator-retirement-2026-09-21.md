# R8 close recovery generator retirement — 2026-09-21

Status: **candidate measurable subtraction after PR #333 retired the historical hosted second-close runner**.

## Purpose

PR #333 removed the productive hosted compatibility retry, but the older recovery generator package remained reachable through the stable `tools.agent` façade: `agent close` resolved `agent_cycle_close` to `tools.agent_cycle_close_recovery`, whose `main()` could synthesize recovery evidence and retry an UNKNOWN canonical close.

That behavior is migration-era orchestration, not the desired post-R8 close model.

This slice makes the public close façade resolve directly to the canonical close owner:

`tools.agent close -> tools.agent_cycle_close.main`

A canonical close now returns its proven PASS / BLOCKED / UNKNOWN result without hidden recovery generation.

## Removed

- `tools/agent_cycle_close_recovery/__init__.py`;
- automatic merge-readback recovery generation;
- automatic non-interference evidence generation;
- automatic UNKNOWN -> re-close composition;
- the legacy `tools.agent.agent_cycle_close -> agent_cycle_close_recovery` alias;
- tests dedicated to the retired recovery generator.

## Preserved

- canonical `tools/agent_cycle_close` close behavior;
- `AgentCycleNonInterferenceReadback 0.1/0.2` validation in the canonical close core;
- binding validation that rejects changed Work or mismatched evidence;
- fail-closed UNKNOWN/BLOCKED semantics;
- R6g BLOCKED write-lease terminal reconciliation;
- Work, Coordination, Agent Cycle, Delivery, CAS and readback authorities.

The non-interference regression now uses static evidence fixtures. This deliberately separates the permanent safety capability — **verify supplied proof** — from the retired migration capability — **discover history and synthesize recovery proof automatically**.

## Reachability evidence

Before this slice:

- the Hosted Agent Cycle workflow no longer referenced recovery after PR #333;
- no stable toolbox command exposed a separate recovery operation;
- `project_sensors` did not use the recovery alias;
- repository runtime consumers found for the package reduced to the lazy `tools.agent.agent_cycle_close` alias;
- the remaining direct users were recovery/non-interference tests.

The alias was not dead code: `tools.agent.main()` routes the public `close` command through it. Therefore retirement requires redirecting that façade to the canonical close module before deleting the package.

## Accounting

Against `main=0c37ea75289e15d01b24bf7fe7f1e6f96ac02ad0` before documentation:

- runtime additions: 1 line;
- runtime deletions: 821 lines;
- runtime net: **-820 lines**;
- test additions: 119 lines;
- test deletions: 393 lines;
- test net: **-274 lines**;
- new runtime modules: 0;
- new public commands/APIs: 0;
- new authorities/state/lifecycles/workflows/provider selectors: 0.

## Qualification

Exact-head Agent Ops, Coordination Guard and Supervisor Snapshot must PASS with real jobs.

Regression coverage must prove:

- public `agent close` resolves to the canonical close owner;
- no recovery generator package remains;
- current and legacy non-interference evidence schemas still validate canonically;
- hash, bound-Work path, bound-Work merge and changed-Work binding failures remain fail-closed.

## Stop condition

Do not recreate automatic close recovery merely because a historical UNKNOWN can be made PASS by inspecting unrelated history. A future generator is justified only by a recurring current-generation operational case that cannot be represented as ordinary supplied evidence without adding hidden lifecycle behavior.

After integration, R8 should move to a closeout inventory rather than assume another runtime recut is required.
