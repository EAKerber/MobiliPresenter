# R6 provider boundary reframe — 2026-09-16

Status: **architectural correction checkpoint for the active `r6-provider-boundary-retirement` Work. Documentation-only; no runtime behavior change and no R6 promotion by itself.**

## Decision

R6 must prove the canonical provider-backed operational path that a normal agent actually uses. The absence of shell `gh`, raw GitHub DNS/HTTP, a process-local connector hook, or local git transport is **not** an R6 blocker and must not be repaired merely to make the canary executable.

The configured GitHub ToolSurface (`github-connector-tools`) is the normal provider boundary. The hosting control plane may execute that provider outside the repository Python process. R6 does **not** require repository Python to invoke the ChatGPT connector in-process as an acceptance criterion.

A test that succeeds only because an unwanted local dependency exists is not valid promotion evidence.

## What prior evidence still means

PRs #309-#314 correctly established several facts: provider availability and executor availability are distinct; the ChatGPT host can invoke the configured GitHub connector/API ToolSurface; no in-process repository implementation was found that turns that host connector directly into `Transport.request()`; shell `gh`, raw DNS/HTTP, local git and canary-only workflows are not acceptable paved-path fallbacks; and the public Journey surfaces must preserve canonical Agent Cycle, Coordination, Agent Tool, Delivery, CAS, receipt and readback guarantees.

Those observations remain useful historical evidence. The interpretation now superseded is narrower: **lack of an in-process connector binding is not, by itself, proof that R6 lacks an executor**. The acceptance boundary is the host/provider-backed service exposed to the agent, not the address space in which the provider call is made.

## Correct executor boundary

```text
semantic agent intent
        |
        v
public paved facade
        |
        v
existing canonical primitive contracts
        |
        v
host/provider execution binding
        |
        v
configured GitHub ToolSurface
        |
        v
canonical guards / CAS / authorities / receipts / independent readback
```

The host/provider boundary may be external to repository Python. Provider selection, issue markers, protocol versions, lease IDs, authority heads, comment correlation and transport mechanics must remain hidden from the normal semantic caller.

The repository must not silently substitute a local CLI/network provider when the host/provider binding is absent. Missing required provider injection must remain fail-closed (`BLOCKED_EXECUTION_SURFACE` or the owning primitive's equivalent UNKNOWN/BLOCKED disposition).

## Implicit fallback inventory observed on `main`

At this checkpoint, observed examples include:

- `tools/agent_tools/journey_entry.py`: `compose_entry(..., transport=None)` falls back to `GhApiTransport()`;
- `tools/agent_tools/dispatch_host.py`: dispatch/inspection paths fall back to `GhApiTransport()`;
- `tools/continuation_remote.py`: `GitHubContinuationAuthority(..., transport=None)` defaults to `GhApiTransport()`;
- `tools/git_observation.py`: `observe_branch` / `observe_file` fall back to `GhApiTransport()`;
- `tools/remote_canonical_execution.py`: `execute_command(..., transport=None)` falls back to `GhApiTransport()`;
- `tools/agent_commands/agent_owned_git.py`: agent-owned Git execution falls back to `GhApiTransport()`;
- `tools/agent_write_lifecycle.py`: lifecycle dispatch preparation falls back to `GhApiTransport()`.

These defaults are migration debt. Their existence must not be confused with the canonical provider contract.

## Active retirement recut

The canonical Work `r6-provider-boundary-retirement` is the current recut for this boundary. Its intended direction is:

1. inventory implicit CLI/network fallbacks at the normal-path boundaries;
2. require explicit provider-neutral transport where a live provider is required;
3. fail closed when provider injection is absent;
4. retain `GhApiTransport` only for explicitly named legacy/recovery consumers until their last legitimate use is migrated;
5. add regression coverage proving that normal paved paths do not silently fall back to `gh`, raw DNS/HTTP or local git;
6. update provider policy and R6 status so the previous in-process-only interpretation is recorded as superseded rather than erased.

This recut must not introduce provider state, a provider manager, authority, workflow, Journey runner, canary-only executor or fallback inference.

## R6 proof after boundary retirement

A positive R6 canary must start from semantic task/Work intent and traverse the canonical service through the configured host/provider path:

`entry -> ownership -> authoring -> candidate/CI -> Delivery -> COMPLETE_WORK -> RELEASE_OWNERSHIP -> CLOSE_AGENT_CYCLE`

The caller must not need issue #145, bus markers, protocol/schema versions, runtime envelopes, authority-head CAS values, lease IDs/binding hashes, result-comment correlation, shell `gh`, raw DNS/HTTP, local git transport, or a process-local connector hook.

The path must still prove the existing guards, CAS/preconditions, ownership, canonical writers, CI/Delivery gates, receipts and independent readbacks. The negative canary must preserve UNKNOWN/BLOCKED, prove no unintended mutation, and prove no fallback to local CLI/network transport.

## Decision rule for any future executor seam

Do **not** add another layer merely because repository Python cannot invoke the host connector directly.

First remove/demote the implicit local fallbacks and exercise the actual canonical host/provider path. If that traversal works while preserving all primitive contracts, no new executor layer is required.

Only if that exercise exposes a concrete missing invariant or callable boundary should a new lower-level seam be considered. Any such seam must live below Journey semantics, add no authority/lifecycle/persistence, reuse existing primitive contracts, preserve fail-closed behavior and readbacks, avoid provider selection in the public API, materially reduce/demote at least two duplicated or CLI-coupled clients in the same migration window, and have normal operational value beyond making one canary pass.

## Structured authority disposition

This document does not mark R6 complete.

- `r6-provider-boundary-retirement` is the active recut for correcting provider-boundary semantics and retiring implicit fallbacks.
- `r6-black-box-paved-path-canary` remains WAITING until this recut integrates and the live positive + negative traversal is rerun.
- `r6b-finalization-composition` remains WAITING until the same execution boundary is proven.
- R7 remains ineligible until R6 has live promotion evidence.

Historical PRs and audits remain evidence. Where they state that an in-process ChatGPT-connector-to-Python binding is itself the required executor, that interpretation is superseded by this checkpoint.

## Operational note

The provider boundary is an implementation detail of the service, not a cognitive requirement for the normal caller. The target remains one normal operational model: semantic paved intent over canonical primitives, executed through the configured provider surface, with legacy CLI/network mechanics retained only for explicit recovery/debugging where justified.
