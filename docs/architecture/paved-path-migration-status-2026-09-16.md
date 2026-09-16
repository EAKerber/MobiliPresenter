# Paved-path migration status — 2026-09-16

Status: R6a is integrated; R6 black-box proof is in progress under the enforced migration-hardening contract.

This is a narrative checkpoint only. Work, Coordination, Agent Cycle, Delivery, CI and Project state remain owned by their canonical structured authorities.

## Current baseline

- `main`: `e41b79b346473dbb1dc24a375c7b82bf368342a9`
- PR #301: migration hardening and retirement gates merged
- PR #303: hardening made part of permanent agent bootstrap rules
- PR #304: clean R6a recut plan merged
- PR #305: post-hardening status checkpoint merged
- PR #306: clean R6a semantic hosted-entry recut merged

The historical `work/operations/r6a-hosted-entry-composition` prototype remains evidence only. The promoted implementation came from the clean recut and did not inherit the prototype branch.

## What R6a now proves

The normal entry caller can provide semantic Work/task intent plus observed ToolSurface inventory and does not need to construct a raw hosted runtime envelope or select an Agent Cycle command version.

The merged composer:

- emits only the current V0.4 begin contract;
- delegates runtime validation to the canonical Agent Cycle runtime validator;
- delegates handle decoding to `hosted_cycle_handle`;
- preserves UNKNOWN/BLOCKED fail-closed behavior;
- reuses exact pending/ready requests idempotently;
- introduces no Journey authority, session, store, workflow, marker or protocol version.

This makes the old normal-path knowledge of raw `runtimeEnvironment`, explicit command-version selection, caller-side begin identity construction and manual handle decoding eligible for R7 demotion.

## Remaining protocol debt

R6a still contains hosted issue discovery, comment pagination and result correlation. Ownership and other paved composers also retain local hosted-bus mechanics. This is accepted only as bounded migration debt.

The hardening rule remains active: a shared transport seam may be introduced only when the same recut materially reduces at least two duplicate clients. No generic compatibility framework is permitted.

## R6 proof split

R6 is intentionally split into two proof layers rather than another orchestration abstraction.

### R6 surface proof

A normal-path API guard verifies that the paved entry, ownership, authoring, delivery and finalization surfaces do not require callers to supply hosted protocol identities such as issue numbers, markers, schema/command versions, raw runtime environments, authority heads, lease/binding IDs, comment IDs, cycle IDs or context hashes.

The negative entry canary also requires incomplete ToolSurface observation to return UNKNOWN before any transport write.

This proof protects cognitive/API compression. It is necessary but not sufficient for R7 promotion.

### R6 live traversal proof

Still required: a black-box positive and negative traversal starting from semantic task/Work intent and passing through entry, ownership, authoring, candidate/CI, Delivery and safe finalization without manually supplying hosted-protocol choreography.

R6 is not complete until this live evidence exists. Unit/surface success alone must not be promoted to paved-path completion.

## Retirement ledger

| Paved surface | Old normal-path knowledge eligible for demotion after R6 | R7/R8 obligation |
| --- | --- | --- |
| JourneyProjection | manual multi-authority stage interpretation | make projection/default semantic view; demote redundant interpretation helpers |
| `journey_shadow` | none; measurement scaffolding | delete after stable positive + negative R6 equivalence evidence |
| `ensure_ownership` | manual lease request/CAS/binding construction | make manual lease choreography internal/recovery-only |
| authoring composition | direct canonical Git mutation/CAS plumbing | make direct request construction internal/recovery-only |
| delivery composition | manual Delivery precondition/request assembly | make manual Delivery request construction internal/recovery-only |
| R6a entry composition | issue/marker/version/runtime-envelope/begin identity mechanics | make direct Agent Cycle bus entry internal/recovery-only |

## Frankenstein abort conditions

Stop and redesign rather than extend the paved layer if any next recut requires:

- a new mutable Journey authority/state/session/store;
- permanent dual-read or dual-write reconciliation;
- a second lifecycle or merge/mutation primitive;
- weakening UNKNOWN/BLOCKED or existing safety guards;
- a generic compatibility framework between paved and legacy models;
- a new permanent composer without a named old normal-path surface that becomes removable or demotable;
- continued hosted-protocol duplication without a concrete R7 consolidation/demotion target.

## Immediate next steps

1. Qualify the R6 surface proof through the normal Agent Ops / Coordination / Snapshot gates.
2. If green, run the live positive + negative R6 traversal without adding a new façade or workflow solely for the canary.
3. Record the evidence here and in the PR accounting.
4. Only after both proof layers succeed, begin R7 promotion.
5. R7 must change the operational default and demote at least one manual surface in the same migration window.
6. R8 remains mandatory subtraction: delete `journey_shadow` when justified and remove/private duplicated or superseded normal-path protocol surfaces.

The migration thesis remains: one normal operational model — semantic paved intent over canonical primitives — with hosted protocol mechanics retained only where recovery/debugging actually requires them.
