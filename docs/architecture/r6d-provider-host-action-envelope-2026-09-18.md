# R6d — Provider host action envelope

Status: **implementation slice in progress**.

## Problem

R6c made cross-intent Work continuation semantic and reentrant, but the outer CLI host still executes through an explicit `GhApiTransport`. That is acceptable as a bounded CLI/recovery adapter, but it does not by itself provide the normal Work-mode path where the configured provider is `github-connector-tools`.

The same host/execution gap already appeared independently in CI re-entry: `ci.workflow.rerun` could produce an exact plan while the outer host still needed to translate that plan into the configured provider operation.

This means the missing abstraction is not another Journey executor. It is a bounded handoff between a semantic plan and one exact provider-side operation.

## Contract

R6d introduces `ProviderHostActionPlan 0.1`.

The artifact is:

- read-only and non-authoritative;
- bound to `github-connector-tools`;
- limited to one provider operation per plan;
- hash-bound to exact arguments/preconditions/readback;
- never a queue, retry loop, workflow, state machine, authority or provider selector.

Initial operations are deliberately narrow:

- `issue-comment.create`, used by the existing Hosted Agent Cycle / write-lease buses;
- `workflow-run.rerun`, used by the existing CI re-entry Agent Tool plan.

The envelope may expose transport details internally to the host adapter. Those details do not become public cognitive inputs to the semantic caller.

## R6c integration

For `agent continue`, the turnover composer still derives exactly one semantic primitive.

When running in plan mode, the host adapter now also emits the exact `ProviderHostActionPlan` required to submit that primitive through the configured GitHub provider. Existing begin/close request deduplication is preserved; write-lease release/acquire request submission is also made idempotent so an interruption between comment creation and hosted result cannot silently duplicate the request.

Direct CLI apply remains an explicit CLI adapter. It is not the R6 promotion provider.

## CI integration

The existing `ci.workflow.rerun` plan keeps its exact-head/run-set semantics and now emits one host-action plan per required workflow run. The action preserves the observed head and prior run attempt as preconditions and requires a later run attempt on the same head for readback.

If the connected provider does not expose the required feature, the action remains unexecuted. The envelope does not authorize a fallback to rerun-failed-jobs, workflow dispatch, shell `gh`, raw HTTP or a new workflow.

## Re-entry and failure model

A host executes at most one action, performs the declared readback, then returns to the semantic layer for re-observation.

No host-action result becomes authority. Canonical Work, Coordination, Agent Cycle, CI and GitHub refs remain the source of truth.

An acknowledgement without the declared readback is insufficient. Provider absence or feature mismatch remains UNKNOWN/BLOCKED.

## Why this is not a generic compatibility layer

The layer exists because two independent paved-path surfaces reached the same boundary:

1. R6c intent turnover needs an exact provider-side issue-comment creation after semantic planning.
2. CI re-entry needs exact provider-side workflow rerun calls after semantic planning.

The layer is intentionally constrained to a single provider action plus readback. It does not model arbitrary workflows or normalize arbitrary transports.

## Death condition

R8 should delete or collapse this layer if the platform later exposes a direct semantic executor that can consume the existing plans without an intermediate host-action artifact.

If the layer remains, it must remain small: adding retries, durable state, generic branching, provider selection, orchestration graphs or alternate authority is an abort/redesign trigger.
