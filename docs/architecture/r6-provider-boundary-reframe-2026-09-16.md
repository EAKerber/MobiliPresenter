# R6 provider boundary reframe — 2026-09-16

Status: **active `r6-provider-boundary-retirement` recut. This checkpoint corrects the provider boundary and persists the inventory needed for implementation; it does not promote R6 by itself.**

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

## Provider-boundary inventory — completed checkpoint

The inventory distinguishes **paved semantic/core boundaries**, where provider choice must be injected explicitly, from **named hosted/recovery adapters**, where constructing the GitHub transport is itself the adapter's declared job. The retirement target is silent provider selection by paved code, not a repository-wide ban on the adapter class.

| Surface | Current observed default | Classification | R6 disposition |
| --- | --- | --- | --- |
| `tools/agent_tools/journey_entry.py` | `compose_entry(..., transport=None)` -> `transport or GhApiTransport()` | public paved entry/composition | remove silent fallback; missing live provider must fail closed |
| `tools/agent_tools/dispatch_host.py` | validation/inspection paths use `transport or GhApiTransport()` | paved dispatch/inspection semantics with hosted callers | require explicit provider at semantic functions; host adapter may pass GitHub transport explicitly |
| `tools/git_observation.py` | `observe_branch` / `observe_file` use `transport or GhApiTransport()` | shared observation primitive | require explicit provider; no local-provider inference |
| `tools/continuation_remote.py` | `GitHubContinuationAuthority(..., transport=None)` defaults to `GhApiTransport()` | GitHub authority adapter used by paved composition | make adapter construction explicit at callers; no silent fallback in a provider-neutral call chain |
| `tools/remote_canonical_execution.py` | `execute_command(..., transport=None)` uses `transport or GhApiTransport()` | named hosted execution adapter | keep GitHub construction only at explicit host/CLI boundary; core execution path should receive transport explicitly |
| `tools/agent_commands/agent_owned_git.py` | `_transport(None)` returns `GhApiTransport()` | agent-owned Git semantic/writer boundary | retire fallback; missing injected provider blocks before planning/apply |
| `tools/agent_write_lifecycle.py` | `prepare_dispatch` / `execute_dispatch` use `transport or GhApiTransport()` | lifecycle semantics plus hosted adapter | semantic preparation/execution requires provider injection; hosted carrier supplies it explicitly |
| `tools/delivery_merge.py` | `prepare` / `execute` use `transport or GhApiTransport()` | Delivery semantics plus hosted adapter | semantic Delivery functions require explicit provider; hosted Delivery carrier supplies adapter explicitly |

### Classification rule

A function is migration debt when a normal paved caller can omit provider injection and thereby cause repository code to choose a CLI/network implementation implicitly. A function is an allowed adapter when its name/hosting boundary explicitly represents GitHub/host execution and the provider construction is not observable as a choice required from the semantic caller.

Therefore the regression must **not** assert zero textual `GhApiTransport` references. It must assert that paved semantic entrypoints do not instantiate the fallback when provider injection is missing, while explicitly named host/recovery adapters remain allowed until their callers are migrated.

### Concrete retirement order

1. `journey_entry` and dispatch semantic functions: fail closed before provider-backed observation when no provider is injected.
2. shared `git_observation` and agent-owned Git writer boundary: require explicit transport and propagate a stable execution-surface blocker rather than constructing `GhApiTransport`.
3. lifecycle and Delivery semantic functions: make transport mandatory in the core path; instantiate GitHub transport only in their explicit hosted carriers.
4. Remote Canonical: preserve it as a named hosted adapter, but move/default construction to its outer host entry rather than `execute_command`.
5. Continuation GitHub authority: require explicit transport in constructor once all normal callers/adapters have been migrated.
6. add tests with a fake provider plus missing-provider tests that prove no fallback construction/mutation.

This sequence must preserve the existing planners, CAS/preconditions, authorities, Work/lease lifecycle, mutation receipts, Delivery gates and independent readback. No provider manager, provider registry, new state machine, workflow or Journey authority is introduced.

## Active retirement recut

The canonical Work `r6-provider-boundary-retirement` is the current recut for this boundary. Its responsibilities are now interpreted as:

1. `inventory-provider-boundary` — **satisfied by the durable classification above once the writer readback is PASS**;
2. `retire-implicit-gh-fallbacks` — implement the smallest explicit-injection cut across paved semantic boundaries;
3. `add-no-fallback-regression` — prove missing-provider fail-closed and fake-provider success without hidden local fallback;
4. `update-provider-policy-and-r6-status` — mark the former in-process-only interpretation superseded without erasing historical evidence;
5. qualify and integrate the recut;
6. only then rerun live positive + negative R6 canaries.

## R6 proof after boundary retirement

A positive R6 canary must start from semantic task/Work intent and traverse the canonical service through the configured host/provider path:

`entry -> ownership -> authoring -> candidate/CI -> Delivery -> COMPLETE_WORK -> RELEASE_OWNERSHIP -> CLOSE_AGENT_CYCLE`

The caller must not need issue #145, bus markers, protocol/schema versions, runtime envelopes, authority-head CAS values, lease IDs/binding hashes, result-comment correlation, shell `gh`, raw DNS/HTTP, local git transport, or a process-local connector hook.

The path must still prove the existing guards, CAS/preconditions, ownership, canonical writers, CI/Delivery gates, receipts and independent readbacks. The negative canary must preserve UNKNOWN/BLOCKED, prove no unintended mutation, and prove no fallback to local CLI/network transport.

## R7 eligibility

R7 remains **ineligible** until R6 has both live positive and negative PASS evidence after this recut integrates. Once eligible, R7 must change the normal default and demote/remove at least one legacy/manual normal-path surface in the same migration window; documentation-only default claims are insufficient.

## R8 mandatory subtraction

R8 remains mandatory after promotion and must delete or demote measurable scaffolding rather than add compatibility layers. Current named candidates remain `journey_shadow`, duplicate hosted I/O/request construction, CLI-coupled defaults, and superseded manual protocol plumbing. Every retained exception must have an owner and death condition.

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
- R8 remains a required subtraction phase after promotion.

Historical PRs and audits remain evidence. Where they state that an in-process ChatGPT-connector-to-Python binding is itself the required executor, that interpretation is superseded by this checkpoint.

## Operational handoff

This repository document plus PR #315 are the durable continuation surface if the originating chat disappears. The active Work authority remains `r6-provider-boundary-retirement`; use its structured state rather than conversational summaries. Do not reopen the parked R6/R6b Works in parallel.
