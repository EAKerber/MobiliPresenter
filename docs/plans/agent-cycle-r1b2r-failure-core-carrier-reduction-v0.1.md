# Agent Cycle R1B-2R — Failure Core Adoption / Carrier Reduction 0.1

Status: **implemented candidate; qualification pending**

Base: `main@5d45d88c127642575d63ef9267f38c60905e15ae`

This slice supersedes the additive implementation shape previously planned as
"R1B-2 — Hosted Agent Cycle Failure 0.2". The target behavior remains: preserve
structured root causes, phase, recovery, and mutation state across the Hosted
Agent Cycle boundary. The implementation deliberately reduces rather than adds
failure-domain infrastructure.

## 1. Reduction

The semantic failure contract remains exactly:

- `AgentFailureCore 0.1`

The Hosted Agent Cycle now emits a small transport shell:

- `HostedAgentCycleFailure 0.2`

The shell is not registered as a second Operational Semantics contract and no
new JSON Schema or helper module is introduced. Its job is only to bind:

- optional validated request correlation;
- the carrier-level operational `BLOCKED` status;
- one embedded, validated `AgentFailureCore 0.1`;
- a stable `failureHash` over that transport shell.

The old duplicated top-level fields are not emitted in 0.2:

- `blockers`;
- `detail`;
- `semanticAuthority`;
- `authorizesMutation`.

Blockers and negative authority boundaries live only in `failureCore`. Human
exception detail remains observable in process/workflow logs and is not part of
semantic identity.

## 2. Reader-first compatibility

`tools.agent_failure` reads:

- `AgentFailureCore 0.1` directly;
- `HostedAgentCycleFailure 0.2` by validating the shell and returning the
  embedded core;
- historical `HostedAgentCycleFailure 0.1` through the existing legacy
  normalization path, with explicit external `phase`;
- the other three historical 0.1 carriers unchanged.

Historical Hosted Cycle tests now use a literal, hash-bound 0.1 fixture rather
than calling the current producer. This keeps historical-read compatibility
independent from producer evolution.

No historical artifact is rewritten.

## 3. Producer behavior

### Begin

When canonical `agent begin` returns a structurally valid non-ready
`AgentCycleContext`, all valid `blockingUnknowns` are preserved in order as
Agent Cycle causes and the Hosted wrapper is appended last:

`<blockingUnknowns...> -> HOSTED_AGENT_BEGIN_NOT_READY`

If the canonical output cannot be validated strongly enough to preserve the
structured cause set, the producer emits:

`HOSTED_AGENT_CANONICAL_BEGIN_FAILED -> HOSTED_AGENT_BEGIN_NOT_READY`

with `lossyProjection=true`.

No root code is reconstructed from human text.

### Close

The Hosted carrier loads close evidence and attempts to validate a returned
`AgentCycleClosure` before allowing process return code to collapse the
failure. For a structurally valid non-PASS closure, `receipt.blockers` are
preserved before the Hosted wrapper:

`<receipt.blockers...> -> HOSTED_AGENT_CLOSE_NOT_PASS`

If no valid closure can be established, the fallback is:

`HOSTED_AGENT_CANONICAL_CLOSE_FAILED -> HOSTED_AGENT_CLOSE_NOT_PASS`

with `lossyProjection=true`.

### Trace

Structured trace errors remain structured. In particular:

`EXECUTION_TRACE_INCOMPLETE -> HOSTED_AGENT_EXECUTION_TRACE_INCOMPLETE`

is preserved root-to-wrapper.

### Agent Write Lifecycle

A valid close report contributes its structured `blockers` before the hosted
state wrapper. Guard exceptions with an explicit code are transported directly
as structured causes.

## 4. Recovery and mutation semantics

For this Hosted Agent Cycle slice:

- `surface=AGENT_CYCLE`;
- `mutationState=NOT_APPLICABLE`;
- `recovery.operationReplay=NOT_APPLICABLE`;
- `recovery.observationRetry=UNKNOWN`.

The slice does not introduce a retry-policy table.

The shell stays `status=BLOCKED` for operational workflow compatibility.
The embedded core can retain `BLOCKED` or `UNKNOWN` from validated Agent Cycle
evidence.

## 5. Correlation

`requestId` and `commandHash` are emitted together only when the supplied
Hosted command validates canonically. If a command is malformed, both fields
are `null`.

This prevents failure materialization from failing recursively while attempting
to hash an invalid command.

## 6. Explicit phase boundary

The manual `failure` subcommand requires `--phase`. The workflow supplies:

- parse materialization: `PARSE`;
- artifact upload/download/checkout transport failures: `TRANSPORT`.

The `begin` and `close` subcommands use their own known `BEGIN`/`CLOSE` phases.

There is no `error-code -> phase` inference table.

## 7. Explicit non-additions

This slice does **not** create:

- `tools/hosted_agent_cycle_failure.py`;
- `ops/schemas/hosted-agent-cycle-failure.schema.json`;
- a `hosted-agent-cycle-failure` registry contract;
- `AgentFailureCore 0.2`;
- a provider resolver;
- `PENDING` / `WAITING`;
- a generalized outcome contract.

These remain unnecessary for the behavior implemented here.

## 8. Tests / acceptance

The candidate adds or updates coverage for:

- literal historical Hosted Cycle 0.1 readability;
- 0.2 reader behavior without external phase;
- shell/core hash tampering;
- all-or-nothing request correlation;
- invalid command failure materialization;
- unexpected exception text not becoming semantic code;
- begin blockers preserved root-to-wrapper;
- close blockers preserved before process return-code collapse;
- no duplicated top-level blockers/detail/authority fields.

Full Agent Ops, Operational Semantics, roadmap freshness, capability lifecycle,
Coordination Guard, and Supervisor Snapshot qualification remain required before
promotion.

## 9. Rollback

Producer rollback can return Hosted Agent Cycle writing to 0.1 while retaining
the 0.2 reader. Reader-first compatibility is therefore monotonic.

No schema or registry rollback is required because none was added.

## 10. Future deletion condition

The Hosted-specific correlation shell should be reevaluated when R2 introduces
a stable CycleHandle / operation identity. If common cycle identity can replace
`requestId` and `commandHash`, carrier-specific failure envelopes may be
deletable entirely, leaving:

`common identity + AgentFailureCore`

as the durable failure representation.
