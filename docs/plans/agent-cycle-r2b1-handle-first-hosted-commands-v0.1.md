# Agent Cycle R2B-1 — Handle-First Hosted Commands

Status: **implementation plan only — no runtime change in this branch**

Base: `main@d0db6fc0507f292b0a35e8d9c73cff70d3928aa4`

Predecessor: R2A merged through PR #171. R2A established one executable definition
for actor/begin/cycle-instance identity and materialized `AgentCycleHandle 0.1` in
Hosted begin artifacts without changing mutation admission.

ProjectState remains authoritative and unchanged:

- phase: `between-increments`;
- checkpoint: `M12-AT3D-D2-CONVERGED-GIT-MUTATION-LIVE-QUALIFIED`;
- next transition: `resolve-m12-at3d-d3-provider-capability-scope-v0.1`.

This refactoring slice does not replace or advance that transition.

## 1. Why R2B is recut into B1 and B2

The older R2 roadmap grouped three concerns under one label:

1. handle-first caller ergonomics;
2. canonical operation identity;
3. replay fences for begin/execute/close.

The current code shows these are related but not the same proof problem.

The caller-side problem is mechanical: Hosted Cycle close, Hosted Agent Tool and
Hosted Agent Write Lease still require the caller to reconstruct facts that the
new handle already binds. The replay problem is behavioral: the mutation
pipeline already has partial fences through deterministic remote execution IDs,
CAS/expected-head guards, `dispatchHash`, attempt comments and terminal-result
inspection. Replacing or extending those fences in the same PR that changes the
caller contract would make regressions hard to attribute.

Therefore:

- **R2B-1** makes the handle pay for its existence by removing caller-side
  identity reconstruction while preserving runtime semantics;
- **R2B-2** will introduce canonical operation identity and consolidate replay
  fences after B1 proves that handle binding is behavior-preserving.

This is a scope reduction, not a roadmap reversal.

## 2. Current biopsy at the R2A merge baseline

### 2.1 Handle already contains the facts the caller keeps copying

`AgentCycleHandle 0.1` contains:

```text
repository
cycleId
cycleInstanceId
context.schemaVersion
context.contextHash
actor
resumeToken
handleHash
```

The Hosted `resumeToken` already encodes a carrier locator containing:

```text
artifactName
runId
sourceSha
issueNumber
beginCommentId
contextHash
cycleInstanceId
```

The core correctly treats `resumeToken` as opaque. Hosted code currently owns
its concrete `hosted-v1:` encoding.

### 2.2 Caller-facing duplication that remains

The current public Hosted paths still make the caller send equivalent facts:

- Cycle close sends `begin.runId`, `begin.sourceSha`, `begin.contextHash`, plus
  actor/intent/scope copied from begin-time knowledge;
- Agent Tool request 0.1 sends `begin` + `actor`;
- Agent Write Lease request 0.1 sends `begin` + `actor`;
- workflows parse those copied fields merely to derive the begin artifact run
  and semantic host SHA.

This is exactly the mechanical reconstruction R2A was intended to make
removable.

### 2.3 Replay is already partially fenced and must not be casually duplicated

The current mutation path already provides meaningful replay defenses:

- Agent Tool Git commands use an execution ID derived from request hash;
- remote mutation is bound to an exact expected branch head;
- dispatch host scans terminal results and attempt evidence before execution;
- a prior attempt without terminal evidence produces `UNKNOWN`, not a replay;
- Coordination lifecycle uses deterministic transition IDs derived from request
  IDs plus authority/branch head preconditions;
- lease and Git CAS guards are revalidated at execution time.

R2B-1 must leave these semantics intact. B2 will decide which identities should
become transport-independent replay keys.

## 3. Goal

Provide a new handle-first caller path where a caller can perform the following
without reconstructing hosted begin mechanics:

```text
begin(...) -> Hosted begin result containing CycleHandle

close(handle, evidence?)
execute_tool(handle, toolId, target, input)
write_lease(handle, action, branch, expected heads/binding, ttl?)
```

For equivalent inputs, the new path must materialize the same canonical inner
contracts, plans, guard proofs, remote commands and mutation admission as the
legacy 0.1 path.

The handle is correlation/resume evidence only. It never becomes authority,
lease, Work binding, provider choice, mutation authorization or a substitute for
readback.

## 4. Success criterion

R2B-1 is successful only if all three Hosted consumers can use the handle while
new callers omit all of these fields:

```text
begin.runId
begin.sourceSha
begin.contextHash
actor.role
actor.workerId
actor.sessionId
```

Those facts may still exist in internally derived legacy-compatible artifacts
while compatibility is active. The success criterion is that **callers no
longer assemble them**.

If the implementation cannot remove these fields from the new public request
surface without weakening a trust boundary, public promotion of the handle must
be re-evaluated rather than compensated with another compatibility layer.

## 5. Single Definition / Single Writer gate

| Fact | Class | Definition / authority | B1 rule |
|---|---|---|---|
| Handle structure | public derived contract | `tools.agent_cycle_identity` | one semantic definition + one current structural schema |
| Handle hash | derived integrity | `agent_cycle_identity.build_handle` | never treated as provenance by itself |
| Hosted resume locator | carrier-derived locator | hosted adapter | parse in one Hosted helper; never in YAML/callers |
| Actor | existing identity reference | handle bound back to manifest/context | derive; caller does not resupply |
| Begin reference | transport provenance | validated begin manifest | derive from manifest after artifact readback |
| Cycle instance | derived execution identity | identity kernel + manifest | exact equality required |
| Project/Work/Coordination facts | mutable authorities | existing canonical writers | unchanged |
| Git/Coordination expected heads | mutation preconditions | live observation / request-specific planning | still explicit where they are actual concurrency guards |

Important distinction:

```text
handle integrity != handle provenance
```

A rehashed but semantically altered handle can be internally well-formed. It is
trusted for a concrete cycle only after binding to the downloaded manifest and
context.

## 6. Public handle admission

R2A intentionally did not register a JSON Schema because the handle was not yet
public input. B1 crosses that boundary, so schema/registry work becomes
mandatory.

### 6.1 Add current structural schema

Add:

`ops/schemas/agent-cycle-handle.schema.json`

for literal current `AgentCycleHandle 0.1`.

The schema must match Python semantic acceptance, including:

- closed top-level and nested fields;
- cycle/cycle-instance/hash patterns;
- closed actor fields;
- `readOnly=true`;
- `semanticAuthority=false`;
- `authorizesMutation=false`;
- opaque non-empty `resumeToken`.

The core schema must **not** encode `hosted-v1:` internals. The token remains
provider/carrier opaque at the core boundary.

### 6.2 OperationalSemantics registration

Add concept:

`artifact.agent-cycle-handle`

and contract:

```text
agent-cycle-handle
  owner = operations-core
  semanticValidator = tools.agent_cycle_identity.validate_handle
  structuralSchema = ops/schemas/agent-cycle-handle.schema.json
```

Do not declare a new mutable resource or authority.

### 6.3 LE-03 parity gate

Because R1C exposed Python-vs-JSON-Schema acceptance asymmetry, B1 must add a
shared positive/negative fixture corpus proving that current structural and
semantic validation agree on all tested boundaries.

A payload must not be considered qualified when it passes only one validator.

## 7. Hosted resume locator adapter

Introduce one Hosted-only helper boundary, candidate:

`tools/hosted_cycle_handle.py`

It is a library, not a CLI and not a new authority component.

Responsibilities:

1. call `agent_cycle_identity.validate_handle()`;
2. decode only the supported `hosted-v1:` resume token;
3. validate the locator is canonical and closed;
4. prove locator fields agree with the handle:
   - repository;
   - context hash;
   - cycle instance;
   - artifact name/run relationship;
5. expose the exact `runId` and `sourceSha` required by the existing GitHub
   artifact/checkout carrier;
6. after artifact download, bind the handle against `context.json` +
   `manifest.json` using the R2A kernel;
7. derive the canonical legacy begin reference and actor for compatibility
   adapters.

It must not:

- authorize mutation;
- observe or choose providers;
- read Work/ProjectState/Coordination;
- silently repair a malformed token;
- infer missing fields from repository defaults;
- turn an artifact lookup failure into a different cycle.

## 8. Begin result: make the handle reachable

Current begin materializes `handle.json`, but the compact begin result does not
return the handle. A caller therefore still needs artifact mechanics to obtain
the object intended to hide artifact mechanics.

B1 should promote the current Hosted begin result to a new literal version,
candidate:

`HostedAgentCycleBeginResult 0.4`

and include the exact validated handle:

```text
handle: AgentCycleHandle 0.1
```

During compatibility, retain the current convenience fields (`runId`,
`sourceSha`, `artifactName`, `cycleId`, `cycleInstanceId`, `contextHash`) so old
field-oriented consumers are not broken merely by the promotion. New examples
and caller paths must use `handle` as the normative continuation token.

Before changing the writer, characterize repository consumers of literal begin
result 0.3. If a strict external repository consumer exists, preserve a reader
or dual-output boundary explicitly rather than silently changing it.

## 9. New Hosted request surfaces

Do **not** immediately version the canonical inner Agent Tool and Write Lease
contracts. They are already registered, tested and consumed deeply by planners,
guards and dispatchers. B1 should add thin carrier-level handle-first envelopes
and derive the existing 0.1 inner request after artifact validation.

This keeps behavior change at the transport boundary.

### 9.1 Hosted Cycle close 0.2

Candidate new close shape under the existing cycle bus:

```text
HostedAgentCycleCommand 0.2
  requestId
  action = close
  handle
  evidenceCommentIds
  semanticAuthority = false
  authorizesMutation = false
```

The close caller no longer supplies:

- actor;
- declaredIntent;
- machineScope;
- begin ref.

Flow:

```text
parse request
-> validate handle integrity
-> decode Hosted resume locator
-> emit begin_run_id/source_sha for carrier
-> download exact artifact
-> checkout exact semantic host
-> bind handle to context+manifest
-> derive effective legacy close identity
-> run existing close logic
```

Begin command may remain on the current shape in B1 because no handle exists
before begin. B2 may later address begin replay identity separately.

### 9.2 Hosted Agent Tool request 0.2

Candidate outer shape:

```text
HostedAgentToolRequest 0.2
  requestId
  handle
  toolId
  target
  input
  semanticAuthority = false
  authorizesMutation = false
```

After exact artifact materialization and handle binding, the Hosted adapter
derives an **in-memory canonical AgentToolRequest 0.1**:

```text
begin <- manifest
actor <- handle/manifest binding
toolId <- outer request
target <- outer request
input <- outer request
requestId <- outer request
```

Then existing resolver/admission/plan/result/dispatch semantics run unchanged.

The original outer request must remain preserved in evidence so a future B2
operation/replay layer can distinguish semantic operation identity from
transport materialization.

### 9.3 Hosted Agent Write Lease request 0.2

Candidate outer shape:

```text
HostedAgentWriteLeaseRequest 0.2
  requestId
  handle
  action
  branch
  expectedAuthorityHead
  expectedBranchHead
  expectedBindingHash
  ttlSeconds
  semanticAuthority = false
  authorizesMutation = false
```

After artifact binding, derive the current AgentWriteLeaseRequest 0.1 and reuse
all existing lifecycle/Coordination logic.

Expected heads remain explicit because they are mutation preconditions, not
begin mechanics. `expectedBindingHash` and TTL semantics also remain unchanged.

## 10. Marker and workflow compatibility

Introduce request markers with explicit new carrier version, candidates:

```text
MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_2
MOBILIPRESENTER_AGENT_TOOL_REQUEST_V0_2
MOBILIPRESENTER_AGENT_WRITE_LEASE_REQUEST_V0_2
```

During migration, workflows must accept both legacy V0_1 and new V0_2 request
markers.

The parser, not YAML, owns payload/version interpretation.

For both versions, the parser should expose the same carrier outputs when a
begin artifact is needed:

```text
begin_run_id
begin_source_sha
```

For V0_1 these come from the legacy begin ref. For V0_2 they come from the
validated Hosted resume locator.

This lets the artifact download and exact-SHA checkout steps remain nearly
unchanged.

Do not parse `resumeToken` in shell, YAML expressions or inline workflow Python.
That would create another definition.

## 11. Preserve canonical inner contracts in B1

The following remain literal 0.1 in this recut unless characterization proves a
hard blocker:

- AgentToolRequest;
- AgentToolPlan;
- AgentToolExecutionResult;
- AgentToolMutationDispatch;
- AgentWriteLeaseRequest;
- AgentWriteLeaseDispatch;
- AgentWriteLeaseResult;
- AgentWriteLeaseBinding;
- AgentCycleExecutionTrace;
- RemoteCanonicalCommand/Receipt.

This is deliberate. The new Hosted envelopes are adapters that remove mechanical
caller input. They do not force a synchronized version bump across every
internal artifact.

## 12. Request readback and trace implications

The mutation dispatch host currently verifies the original Agent Tool request by
reading the request comment and comparing it to the canonical request artifact.
That logic must become version-aware without becoming permissive.

For V0_2:

1. read back the exact original outer comment;
2. validate the outer handle-first request;
3. bind its handle to the bundle manifest/context;
4. derive the canonical inner AgentToolRequest 0.1;
5. require exact equality with the bundled inner request.

A V0_2 request must never be accepted by stripping unknown fields or by matching
only request ID/hash.

Trace/result markers should remain unchanged in B1 unless required for exact
lineage. The trace sees the same inner plans, dispatches and results after
normalization.

## 13. Explicitly deferred to R2B-2

Do not add these in B1:

- `operationId` contract;
- deterministic request ID enforcement;
- a new replay store;
- begin replay returning an existing cycle instance;
- transport-independent attempt identity;
- close replay state machine;
- `PENDING`/`WAITING`;
- seal/late-result behavior;
- sequence/dependency ordering;
- `abandon`;
- artifact expiry;
- Work binding;
- provider selection/Work Mode adapter.

B1 may characterize the existing replay behavior and add tests that freeze it,
but must not silently strengthen or weaken it.

## 14. Implementation order

### Phase 0 — Consumer characterization

Before mutation:

- locate all repository consumers of:
  - Hosted begin result 0.3;
  - Cycle request V0_1 marker;
  - Agent Tool request V0_1 marker;
  - Write Lease request V0_1 marker;
  - `begin_run_id` / `begin_source_sha` workflow outputs;
- capture golden legacy request -> inner artifact -> plan/dispatch/result fixtures;
- confirm no current consumer treats handle hash as authority.

If an unknown strict consumer is found, stop and update the compatibility plan
before changing the writer.

### Phase 1 — Public handle contract

- materialize JSON Schema;
- add OperationalSemantics concept/contract;
- add structural/semantic parity tests;
- do not alter runtime callers yet.

Gate: semantics/coverage fully green before proceeding.

### Phase 2 — Hosted locator helper

- extract canonical Hosted token decode/binding into one library helper;
- move `_hosted_resume_token` construction/validation behind the helper as
  appropriate;
- preserve the exact R2A token bytes for existing handles.

Gate: existing R2A handle fixtures remain byte-for-byte compatible.

### Phase 3 — Begin result 0.4

- expose exact handle in begin result;
- retain old convenience fields during compatibility;
- prove result handle equals artifact `handle.json` exactly.

Gate: existing begin behavior and mutation readiness unchanged.

### Phase 4 — Handle-first Cycle close

- add V0_2 parser path;
- derive artifact locator from handle;
- bind after download;
- reuse current close implementation.

Gate: V0_1 and V0_2 equivalent close inputs produce equivalent closure/receipt
semantics.

### Phase 5 — Handle-first Agent Tool

- add outer HostedAgentToolRequest 0.2;
- preserve raw outer request evidence;
- derive exact inner AgentToolRequest 0.1 after binding;
- update request-comment readback to prove derivation;
- leave resolver/admission/dispatch contracts unchanged.

Gate: same semantic operation yields the same inner request, plan and remote
command as the legacy path when transport metadata is held constant.

### Phase 6 — Handle-first Write Lease

- add outer HostedAgentWriteLeaseRequest 0.2;
- derive exact inner lifecycle request 0.1;
- reuse current Coordination planning/dispatch/guard path.

Gate: same semantic lifecycle operation yields the same inner request, command,
transition ID and preconditions as V0_1.

### Phase 7 — Workflow migration

- accept both request markers;
- keep download/checkout transport steps shared;
- remove any need for V0_2 callers to populate begin/actor data;
- do not add workflow-side contract logic.

### Phase 8 — Qualification and evidence

- full unit suite;
- semantic contracts;
- OperationalSemantics check + coverage;
- roadmap freshness;
- capability lifecycle guard;
- Doctor/coherence;
- Coordination Guard;
- Supervisor Snapshot;
- workflow boundary tests;
- at least one Hosted round-trip fixture or bounded live qualification proving
  the returned handle can drive a subsequent handle-first request.

No merge while the final head has pending or failing required checks.

## 15. Required tests

At minimum:

1. current handle positive corpus passes Python + JSON Schema;
2. every negative handle fixture fails both boundaries for the same class of
   reason;
3. Hosted token decoder preserves exact current `hosted-v1:` canonical encoding;
4. locator/handle context mismatch fails before artifact is trusted;
5. locator/handle cycle-instance mismatch fails;
6. rehashed handle with altered actor cannot bind to original manifest;
7. begin result 0.4 embeds exactly the uploaded handle;
8. V0_1 Cycle close remains accepted;
9. V0_2 Cycle close needs only handle + close-specific fields;
10. V0_1 and V0_2 close produce equivalent closure semantics;
11. V0_1 Agent Tool remains accepted;
12. V0_2 Agent Tool rejects explicit copied `begin`/`actor` as unknown fields;
13. V0_2 Agent Tool derives exact legacy inner request after binding;
14. V0_1/V0_2 equivalent tool calls produce identical canonical plan/command;
15. dispatch-host original-comment readback validates V0_2 by derivation, not
    by loose matching;
16. V0_1 Write Lease remains accepted;
17. V0_2 Write Lease derives exact legacy lifecycle request;
18. equivalent V0_1/V0_2 lifecycle calls retain exact authority/branch head
    guards and transition identity;
19. handle-first paths do not alter mutation admission;
20. no handle validator or resume-token parser is duplicated in workflows.

## 16. Candidate implementation paths

Expected touched runtime paths, subject to characterization:

```text
tools/agent_cycle_identity.py
+ tools/hosted_cycle_handle.py

tools/hosted_agent_cycle.py
tools/hosted_agent_tool.py
tools/hosted_agent_write_lease.py
tools/agent_tools/dispatch_host.py

.github/workflows/hosted-agent-cycle.yml
.github/workflows/hosted-agent-tool.yml
.github/workflows/hosted-agent-write-lease.yml

ops/schemas/agent-cycle-handle.schema.json
ops/semantics/registry.json

tools/tests/test_agent_cycle_identity_r2a.py
+ tools/tests/test_agent_cycle_handle_public_r2b1.py
+ carrier compatibility tests as needed
```

Files such as `tools/agent_tools/contracts.py` and
`tools/agent_write_lifecycle.py` should remain unchanged unless implementation
proves the thin-adapter strategy impossible. Touching them is a signal to
re-evaluate scope before proceeding.

## 17. Leeway and stop conditions

The implementation may adjust names and exact envelope fields if tests expose a
better smaller boundary, but it must preserve these invariants.

Stop and re-plan if any of the following occurs:

- a new mutable session/cycle authority becomes necessary;
- a handle-first request needs to weaken manifest/context binding;
- the carrier cannot locate the artifact without treating unverified handle
  fields as authority;
- Agent Tool or Write Lease canonical contracts need a synchronized breaking
  change merely to accommodate the Hosted envelope;
- structural and semantic handle validation cannot be made equivalent without
  changing R2A semantics;
- old V0_1 callers cannot coexist without dual-writing mutable facts;
- workflow YAML needs to implement resume-token semantics;
- B1 requires changing replay/mutation behavior to work.

If one of these appears, record the evidence and reconsider the recut rather
than widening the PR opportunistically.

## 18. Single-writer negative gates

Qualification must continue proving:

- ProjectState has one writer;
- Continuations/Work has one writer;
- Coordination has one writer;
- no Hosted carrier gains direct authority writes;
- no handle/result/projection becomes mutable authority;
- Agent Tool mutation still requires existing proof set + canonical remote host;
- Write Lease mutation still goes through canonical Coordination transition;
- exact expected heads and independent readback remain required.

## 19. B1 death condition and handoff to B2

B1 compatibility code is transitional.

The legacy V0_1 Hosted request paths may be retired only after:

1. V0_2 has completed a qualified Hosted round trip;
2. repository consumers of V0_1 are inventoried;
3. no required active caller depends on manual begin/actor fields;
4. a removal PR carries explicit consumer-zero evidence.

R2B-2 is admitted when B1 proves:

- public handle input is structurally and semantically stable;
- the same handle can resume across distinct Hosted workflow runs;
- handle-first and legacy paths are behaviorally equivalent;
- callers no longer need begin/actor reconstruction.

B2 should then define a canonical **operation identity independent of transport
comment/run IDs** and consolidate the already existing partial replay fences.
It should prefer reusing current deterministic remote execution IDs, CAS,
attempt evidence and terminal readback instead of adding a new replay authority.

## 20. Expected paved-path improvement

Before B1:

```text
begin -> copy run/source/context/actor -> construct tool/lease/close request
```

After B1:

```text
begin -> handle
handle + operation -> Hosted adapter derives mechanics -> existing governed path
```

This is the first R2 slice whose value should be directly visible to an agent or
Work Mode caller while preserving the underlying authority and mutation model.
