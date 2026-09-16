# R6 provider executor discovery audit — 2026-09-16

Status: **evidence annex; no runtime behavior change and no executor implementation authorized.**

Baseline audited: `main=4211732ae93097966dd74c2e1716270a43100212` after PR #311.

This audit records the repository-side discovery requested by `r6-executor-seam-retirement-plan.md`. It is evidence for the existing control documents, not a replacement architecture or a new migration plan.

## 1. Question under test

Does the current repository already contain a natural, reusable executor below Journey semantics that can bind the hosting platform's configured GitHub ToolSurface to the existing `Transport.request()` protocol used by the paved façade?

A positive result would make an R6 executor recut eligible only if it also satisfied the hardening and same-window subtraction gates. A negative result keeps R6 at `BLOCKED_EXECUTION_SURFACE` and forbids manufacturing a Journey-specific bridge merely to make the canary runnable.

## 2. Repository surfaces inspected

The discovery covered the current public paved path and the lower-level transport/provider surfaces, including:

- `tools/runtime_provider_adapter.py`
- `tools/coordination_remote.py`
- `tools/agent_tools/journey_entry.py`
- `tools/agent_tools/dispatch_host.py`
- `tools/agent_tools/adapters/remote_git_files.py`
- `ops/semantics/registry.json`
- the recursive `main` tree and code-search terms related to provider execution, including `connector`, `mcp`, `api_tool`, `GitHubBridge`, `ProviderRequest`, `GitHubToolCallRequest`, `executor`, `invoke`, `Transport` and `ApiResponse`.

The purpose was not to prove that a platform connector exists — that is already observed externally — but to find a repository-owned executable binding from that capability into Python.

## 3. What exists

### 3.1 Provider observation exists

`runtime_provider_adapter` converts observed ToolSurfaces into canonical provider observations. It is read-only and non-authoritative. It describes provider availability; it does not invoke provider tools.

### 3.2 A narrow injectable transport contract exists

`coordination_remote` defines the repository `Transport.request()` seam and its `ApiResponse` shape. GitHub-backed repository authorities and composers already use this abstraction.

This is the correct architectural level for any future executable provider binding: below Journey semantics and above the canonical remote authorities.

### 3.3 Public and hosted clients already accept transport injection

`journey_entry.compose_entry()` accepts an injected `transport=`. `agent_tools.dispatch_host` also accepts transport injection and forwards it through existing guarded execution paths.

Therefore the repository does not need another Journey façade or another semantic operation model to become provider-backed.

### 3.4 The concrete repository-local fallback remains CLI-coupled

When no executable transport is injected, the audited paths converge on `GhApiTransport`, which implements the same protocol through shell `gh api`.

That path remains useful for explicit legacy/recovery environments but is not the R6 paved-path promotion target under `paved-path-provider-policy.md`.

### 3.5 Provider request concepts exist without an in-process executor

The semantic registry contains provider-boundary concepts such as `GitHubBridge`, `ProviderRequest` and `GitHubToolCallRequest`, while retaining mutation authority inside the canonical tool/remote execution surfaces.

The audit found no repository implementation that turns those concepts, or an observed ChatGPT GitHub ToolSurface, into executable calls from the repository Python process.

## 4. What was not found

At this baseline, no in-repository implementation was found that simultaneously:

1. receives the hosting platform's configured GitHub ToolSurface or equivalent executable provider handle;
2. invokes that provider from repository Python;
3. normalizes the response to the existing `ApiResponse`/`Transport.request()` contract; and
4. preserves the existing Remote Canonical Execution / Agent Tool / Coordination / Delivery authority and guard chain.

Searches for connector-, MCP-, API-tool-, provider-request-, bridge-, executor- and invocation-oriented implementations did not reveal such a binding. The known consumers of the transport seam remain injectable, but the executable ChatGPT-provider implementation itself is outside the repository.

This is a discovery result, not proof that no future platform hook can exist. It means only that no such hook is present in the audited repository generation.

## 5. Architectural disposition

R6 remains **`BLOCKED_EXECUTION_SURFACE`**.

The block is now narrower than an ordinary implementation backlog:

- the semantic paved façade exists;
- provider observation exists;
- transport injection exists;
- canonical mutation/ownership/delivery authorities exist;
- the missing component is the runtime/platform binding that would make the externally configured provider callable from repository Python without exposing legacy choreography to the semantic caller.

No repository-side Journey expansion is justified by this absence.

## 6. Freeze imposed by this audit

Until a real executable provider hook becomes available or a deliberate architectural re-evaluation changes the migration thesis:

- do not add another Journey module to bridge this gap;
- do not add a canary-only workflow, runner or service;
- do not add provider state, provider authority or a provider registry merely to make R6 executable;
- do not route the normal paved path back through manual issue markers/comment correlation;
- do not install or require `gh`, raw DNS/HTTP or local git as the hidden definition of provider success;
- do not promote R7 by documentation alone;
- do not start R8 deletion that depends on unproven positive R6 traversal.

Read-only discovery, platform-capability investigation and documentation synchronization remain allowed.

## 7. Re-entry trigger

Re-open executor implementation only when a concrete runtime/platform hook can be named that can actually invoke the configured GitHub provider from the execution context used by the public façade.

Before code is written, the recut must identify:

- the concrete callable runtime hook;
- how it implements the existing `Transport` contract rather than introducing a parallel semantic API;
- how canonical authority/guards/readbacks remain unchanged;
- at least two existing transport clients or duplicated hosted/CLI paths that become smaller, internal-only, recovery-only or removable in the same migration window;
- the positive and negative R6 black-box proof procedure;
- the rollback/readback behavior;
- the R7/R8 demotion/deletion consequence.

If these fields cannot be filled, the correct disposition remains blocked.

## 8. Retirement consequence

This audit strengthens rather than weakens the R7/R8 retirement plan.

The desired future provider executor should be shared below Journey semantics so that it can replace normal-path CLI/default transport behavior in more than one consumer — at minimum the public entry and Agent Tool/dispatch paths — while leaving explicit recovery transports available where justified.

If the only proposed executor would add one more client next to all existing clients, it fails the hardening gate even if it can make the R6 canary pass.

## 9. Current decision

At `main=4211732ae93097966dd74c2e1716270a43100212`:

- no natural in-repository provider executor binding was found;
- no runtime code change is authorized by this audit;
- R6 remains blocked on the execution surface, not on semantic composition;
- R7 remains ineligible;
- R8 remains a planned subtraction phase contingent on real R6/R7 evidence;
- the next valid unblock must come from an actual runtime/provider capability or an explicit redesign decision, not another compatibility layer.

The migration thesis remains unchanged: **one normal operational model — semantic paved intent over canonical primitives — with provider/guard/receipt mechanics hidden from normal-path cognitive input and legacy protocol mechanics retained only for recovery/debugging where they are genuinely needed.**
