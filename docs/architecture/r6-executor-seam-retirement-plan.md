# R6 executor seam and R7/R8 retirement plan

Status: **planning/control document; no executor implementation authorized by this document.**

Baseline: `main=cf79c0a60c952d4b2cd19e759cdc1d161b0851bf` after PR #310.

This plan narrows the remaining R6 problem and prepares R7/R8 subtraction without converting the migration block into a reason to add another orchestration layer.

## 1. Current disposition

R6 remains `BLOCKED_EXECUTION_SURFACE`.

The public paved surface and fail-closed cognitive/API guard are integrated. The remaining proof is a real positive + negative black-box traversal through the public façade using the configured provider-backed GitHub ToolSurface.

The block does **not** mean:

- GitHub capability is absent;
- shell `gh` must be installed;
- raw DNS/HTTP access must be restored;
- the public paved API is semantically broken;
- a canary workflow or Journey runner should be added.

It means that the currently observed hosting environment does not expose a proven execution binding from its configured GitHub ToolSurface into the repository Python façade.

## 2. Seam inventory

### 2.1 Present: semantic façade

The public path is composed from existing paved surfaces:

- entry: `tools.agent_tools.journey_entry.compose_entry`
- ownership: `tools.agent_ownership.ensure_ownership`
- authoring: `tools.agent_authoring.author_changes`
- delivery: `tools.agent_delivery.compose_delivery`
- finalization projection: `tools.agent_delivery.project_finalization`

PR #307 guards that these normal-path surfaces do not require hosted issue/marker/schema/runtime-envelope/authority-head/lease-binding/comment/cycle/context identities from the caller.

### 2.2 Present: ToolSurface observation

`tools/agent.py` accepts externally observed ToolSurfaces and `tools/runtime_provider_adapter.py` translates the complete inventory into canonical provider observations.

This layer is read-only/non-authoritative. It answers “what provider capabilities were observed?” It does not execute GitHub operations for the paved composers.

### 2.3 Present: repository transport protocol

`tools/coordination_remote.py` defines the narrow `Transport.request(method, endpoint, payload, include_headers)` protocol used by GitHub-backed authorities and composers.

`journey_entry.compose_entry()` already supports dependency injection through its `transport=` argument. This is a useful seam: Journey semantics do not require a specific executable transport implementation.

### 2.4 Legacy/recovery concrete transport

`GhApiTransport` implements `Transport` through shell `gh api`.

That implementation remains useful to existing legacy/recovery/runtime contexts, but PR #310 explicitly removes it from the paved-path promotion target. Its availability or absence cannot decide R6 PASS.

### 2.5 Missing/unproven seam

No current repository/runtime path has been observed that both:

1. executes the public paved Python façade; and
2. binds the hosting platform's configured `github-connector-tools` / GitHub API ToolSurface as the concrete `Transport.request()` implementation.

The ChatGPT-side connector can perform GitHub calls, but repository Python cannot directly invoke the chat connector tool surface. Conversely, existing GitHub Actions runners can execute repository Python, but the audited workflows do not expose the configured ChatGPT connector ToolSurface as that Python transport.

This is the exact remaining executor seam.

## 3. Non-solutions

The following do not close R6 and must not be implemented solely for this gate:

- install or depend on shell `gh`;
- restore raw GitHub DNS/HTTP access in the local container;
- use local git as an alternate paved provider;
- manually submit issue #145 markers from the black-box caller;
- invoke Hosted Agent Cycle/Tool/Write Lease carriers by their legacy protocol as the test caller;
- add a `workflow_dispatch` canary whose only purpose is to execute R6;
- add a Journey executor/runner/service;
- add a new provider registry, provider authority or provider state;
- add a transport compatibility framework with no immediate retirement effect;
- weaken the requirement for a live positive + negative traversal.

These approaches either test the legacy choreography, add a second architecture, or manufacture a promotion surface specifically for the migration.

## 4. Conditions for an admissible executor seam

A new executor/transport seam may be implemented only if all conditions below are satisfied simultaneously.

### 4.1 Architectural placement

It lives below Journey/paved-path semantics and implements/reuses an existing runtime/provider contract. Journey surfaces continue to express semantic intent and do not select providers.

### 4.2 No new authority

It adds no durable state, session, lifecycle, scheduler, writer or source of truth.

### 4.3 Existing primitive preservation

It preserves:

- canonical writers;
- CAS/preconditions;
- Coordination ownership;
- Agent Cycle lifecycle;
- Delivery gates;
- UNKNOWN/BLOCKED fail-closed behavior;
- receipts and independent readbacks.

### 4.4 Non-canary usefulness

The seam must represent a real platform/runtime capability that normal paved operations can use after R6. A bridge whose sole durable consumer is the R6 test is rejected.

### 4.5 Same-window subtraction

The same migration window must make at least two existing duplicated/legacy transport clients materially smaller, internal-only, recovery-only or removable.

Examples of eligible subtraction targets include repeated issue discovery/comment submission/result correlation and CLI-coupled transport defaults. The exact pair must be named before implementation.

### 4.6 Public surface does not grow

Normal callers still provide semantic intent. They do not gain a provider selector, executor selector, transport object requirement, marker/version parameter or runtime-envelope parameter.

## 5. Trigger for implementation

Do not create an executor recut merely because this plan exists.

Implementation becomes eligible only when discovery identifies a concrete platform hook that can bind a configured ToolSurface to repository Python while satisfying Section 4.

At that point, the recut proposal must contain:

- the concrete runtime hook;
- the existing contract it implements/reuses;
- the two or more legacy/duplicate clients reduced in the same window;
- proof that no authority/lifecycle is added;
- positive and negative R6 canary procedure;
- rollback/readback behavior;
- explicit deletion/demotion follow-up.

If those fields cannot be filled before implementation, remain blocked.

## 6. R6 proof package once an executor exists

The first use of an admissible executor seam is the R6 proof, not a feature expansion.

### Positive traversal

Start from semantic task/Work intent and exercise:

`entry -> ownership -> authoring -> candidate/CI -> Delivery -> COMPLETE_WORK -> RELEASE_OWNERSHIP -> CLOSE_AGENT_CYCLE`

Evidence must show:

- no caller-supplied issue/marker/protocol identity;
- no caller-supplied authority head, lease ID or binding hash;
- no caller-side result-comment search;
- canonical guards/readbacks preserved;
- exact Work/branch/PR/main identities observed at relevant gates;
- terminal cycle closure evidence preserved.

### Negative traversal

Use an intentionally incomplete or stale observation that should block before mutation.

Evidence must show:

- terminal `UNKNOWN` or `BLOCKED` as appropriate;
- no unintended write;
- no fallback to shell/CLI/legacy bus;
- diagnostic evidence preserved.

### Promotion decision

R6 becomes PASS only if both positive and negative evidence are live and inspectable. One cannot compensate for the other.

## 7. R7 ready plan — promotion and demotion

R7 remains ineligible until R6 PASS, but its subtraction targets are already known.

R7 must change the normal operational default, not just documentation wording.

Candidate sequence after R6 PASS:

1. make semantic paved entry the documented/default normal entry;
2. make JourneyProjection the default semantic read view where it has sufficient coverage;
3. mark manual Hosted Agent Cycle request construction normal-path-ineligible;
4. mark manual lease request/CAS/binding construction normal-path-ineligible;
5. mark direct canonical Git request assembly normal-path-ineligible when `author_changes` applies;
6. mark manual Delivery request assembly normal-path-ineligible when `compose_delivery` applies;
7. retain legacy/manual surfaces only with explicit recovery/debugging labels and tests proving paved defaults.

R7 acceptance requires at least one of these legacy surfaces to become concretely internal/recovery-only in the same PR/window. A preference statement alone is not promotion.

## 8. R8 ready plan — measurable subtraction

R8 is not optional cleanup. It tests whether the scaffolding was a bridge or a permanent second architecture.

Priority subtraction candidates:

1. delete `journey_shadow` once R6/R7 evidence makes ongoing shadow comparison unnecessary;
2. delete or centralize repeated hosted issue discovery/comment pagination/result-correlation code when the consolidation rule can reduce at least two clients;
3. remove CLI-coupled defaults from paved modules; keep explicit CLI transport only where recovery callers still require it;
4. privatize/delete manual Agent Cycle request-construction helpers no normal-path caller uses;
5. privatize/delete manual ownership request-construction helpers superseded by `ensure_ownership`;
6. privatize/delete direct authoring request assembly superseded by `author_changes`;
7. privatize/delete manual Delivery request assembly superseded by `compose_delivery`;
8. remove migration-only documentation/tests whose death condition has been met, while retaining durable invariants as regression tests.

R8 should report before/after counts for public normal-path entry points and migration scaffolding. Raw LOC reduction is useful evidence but not the authority; the primary requirement is one normal operational model.

## 9. Frankenstein detection at the executor boundary

Stop and redesign if any executor proposal requires:

- a new Journey state/session/authority;
- a provider selector in the public semantic API;
- permanent dual transport reconciliation;
- a second lifecycle or mutation engine;
- protocol-version branching inside Journey composers beyond canonical host delegation;
- retaining both old and new transport clients as equal normal paths indefinitely;
- a bridge whose main justification is “otherwise R6 cannot run”;
- weakening a guard/readback because the platform connector behaves differently.

A blocked R6 is preferable to a false architectural PASS.

## 10. Current action

At the baseline recorded above:

- no executor implementation is authorized by this plan;
- no R7 promotion is authorized;
- no R8 deletion is yet authorized by R6 evidence;
- provider/executor discovery may continue read-only;
- documentation should remain synchronized with any newly observed natural execution surface;
- once a suitable platform hook exists, re-evaluate this plan before writing code.

The desired end state remains one invisible semantic service over canonical primitives, with provider/guard/receipt mechanics available for observability and recovery rather than required as normal-path cognitive input.
