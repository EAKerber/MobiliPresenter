# E2b — Portable canonical execution provenance

Status: **candidate final boundary extraction before a shared/direct governed mutation host**.

## Purpose

E2 made the write-lifecycle admission proof transport-neutral. The remaining hosted assumption was inside `RemoteCanonicalExecutionReceipt`: receipt 0.1 required `workflow`, `runId`, `issueNumber` and `commentId` in every execution source.

Those fields describe the carrier that materialized a receipt. They are provenance, not authority, CAS, ownership or lifecycle.

E2b makes canonical execution provenance portable without adding a second receipt type or execution engine.

## Current producer

New receipts use:

`RemoteCanonicalExecutionReceipt 0.2`

with source:

```json
{
  "kind": "hosted-comment | agent-tool-host",
  "host": "<execution-host>",
  "sourceSha": "<git-sha>",
  "invocationId": "<host invocation>",
  "ref": {
    "kind": "issue-comment | agent-tool-request",
    "value": "<carrier-specific stable reference>"
  }
}
```

The source remains non-authoritative and is hash-bound as part of the receipt.

## Hosted adapter

Hosted comment execution uses one shared builder and encodes its carrier reference as:

`issue-comment -> "<issue-number>:<comment-id>"`

Both the Remote Canonical issue adapter and Hosted Agent Tool dispatch use the same builder.

## Direct-host readiness

The core also validates the already-known next carrier:

`agent-tool-host -> agent-tool-request:<request-hash>`

No direct mutation host is added in E2b. This proves only that a canonical receipt can be built and validated without an issue/comment identity.

## Historical compatibility

`RemoteCanonicalExecutionReceipt 0.1` remains validation-only compatibility.

- current `build_receipt()` emits only 0.2;
- current hosted producers emit source 0.2;
- `validate_receipt()` can reconstruct/validate 0.1 historical receipts;
- there is no new 0.1 producer.

Death condition: remove 0.1 validation only when retained evidence and current tests no longer require historical receipt verification.

## Migration-release boundary

Historical migration-release inspection is intentionally narrower than general receipt validation.

It accepts only provenance that normalizes to a hosted comment and whose host is `remote-canonical-execution` on the expected issue.

Therefore:

- legacy 0.1 hosted receipt: accepted when otherwise exact;
- current 0.2 hosted receipt: accepted when otherwise exact;
- future `agent-tool-host` receipt: rejected as migration-release evidence.

This preserves the historical hosted binding instead of generalizing an old exception into future runtime semantics.

## Preserved invariants

E2b does not change:

- RemoteCanonicalCommand;
- GitMutationPlan;
- GitMutationBundle;
- exact expected head/CAS;
- Coordination ownership enforcement;
- lifecycle admission;
- provider readback;
- aggregate readback;
- receipt hashing;
- BLOCKED/UNKNOWN behavior.

## Non-goals

No direct mutation host, ToolSurface, workflow, provider manager, retry service, authority, state or lifecycle is added.

## Promotion gate

The PR must pass exact-head Agent Ops, Coordination Guard and Supervisor Snapshot.

Regression must prove:

1. current hosted producers emit receipt/source 0.2;
2. a direct Agent Tool host source builds and validates a canonical receipt without issue/comment fields;
3. historical receipt 0.1 remains readable;
4. malformed/unknown source kinds and refs fail closed;
5. migration-release accepts legacy/current hosted provenance;
6. migration-release rejects direct-host provenance.

## Next

After E2b, E3 should extract the existing reproof/admission/execution/classification core from Hosted Agent Tool dispatch, make the hosted path consume that core immediately, and expose the same core to a direct governed-mutation host. E3 should be implementation, not another preparatory compatibility layer.
