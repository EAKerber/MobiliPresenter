# Agent Cycle R1C — Role-visible Agent Tool Discovery 0.1

Status: implementation slice

## Objective

Separate Agent Tool discovery from current-intent admission without weakening any execution guard.

The governing rule is:

> Role determines the discoverable tool universe. Declared intent determines current relevance/admission. Runtime observations describe capability availability. Provider/surface binding remains a later resolution concern.

This slice exists because filtering the tool catalog by `allowedIntents` creates false-negative discovery: a role-valid governed path can disappear from begin context, leaving an agent more likely to improvise through a generic carrier even though the project already has a governed capability.

## Contract change

Promote `AgentToolProjection 0.1` to producer version `AgentToolProjection 0.2` while preserving read compatibility with 0.1.

Existing buckets retain their meaning:

- `available`: current-intent tools whose required capabilities are available;
- `plannable`: current-intent plan-only tools;
- `conditional`: current-intent executable tools blocked by capability availability.

0.2 adds `discoverable`, derived from the current role policy independently of the current intent. A discoverable entry contains only static policy facts:

- `toolId`;
- `effectClass`;
- `currentIntentAllowed`;
- `allowedIntents`;
- `requiredCapabilities`.

`discoverable` does not select a provider, surface, target, operation, guard proof, writer, lease, CAS precondition, or mutation authorization.

## Admission boundary

`allowedIntents` remains normative. The Agent Tool resolver must continue to reject a request with `AGENT_TOOL_INTENT_FORBIDDEN` when the current declared intent is not allowed for that role/tool pair.

Discoverability is therefore informative, not permissive.

## Readiness boundary

`AgentCycleReadiness 0.1` continues to derive tool/provider/authorization dimensions only from `available`, `plannable`, and `conditional`.

`discoverable` must not:

- promote `toolReadiness`;
- resolve a provider;
- create mutation authorization;
- change the legacy Agent Cycle status.

An intent can therefore have no currently admitted tool surface while still exposing role-valid adjacent tools for discovery.

## Runtime/provider boundary

`AgentCycleContext` already carries `runtimeCapabilities`. This slice does not add a provider resolver or Work Mode adapter.

A context may independently show that a logical capability is satisfied by `github-connector` while a role tool that could later use that capability is merely discoverable under the current intent. R5 will bind a concrete provider/surface once an operation is selected and admitted.

In particular, provider failure must remain provider-local: if an equivalent observed provider satisfies a logical capability, failure or absence of `gh-api` must not imply that the logical GitHub capability is unavailable.

## Schema compatibility repair

The structural schema at `ops/schemas/agent-tool-projection.schema.json` becomes dual-version 0.1/0.2. The schema also recognizes the already-supported runtime mode `mutation-execute`, aligning structural validation with the existing producer/resolver contract.

## Acceptance tests

1. `manager-gitops + bootstrap-discovery` exposes `git.files.mutate`, `project.inspect`, and `routine.inspect` in `discoverable` even though none is currently admitted by that intent.
2. `ui-ux + bootstrap-discovery` remains role-bounded and does not expose `routine.inspect`.
3. `discoverable` does not change readiness dimensions.
4. Direct resolution of `git.files.mutate` under `bootstrap-discovery` remains forbidden by intent.
5. Historical `AgentToolProjection 0.1` remains readable.
6. `discoverable` is deterministic, sorted, unique, and hash-bound.
7. Existing `available` / `plannable` / `conditional` behavior remains unchanged for `inspect-and-plan` and `governed-mutation`.

## Explicitly out of scope

- automatic host/Work Mode connector observation;
- provider preference or concrete provider selection;
- changing `GhApiTransport` defaults;
- changing Agent Tool target policy, guards, writer selection, leases, Git CAS, or hosted admission;
- automatic declared-intent translation or mutation of intent;
- execution through the GitHub connector.

Those concerns remain for the provider/Work Mode bridge slice.

## Rollback

Rollback is a normal branch revert of this slice. Existing 0.1 projections remain readable, and no authority or mutable operational state is changed by the projection itself.
