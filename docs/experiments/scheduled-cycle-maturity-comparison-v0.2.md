# M12 maturity comparison envelope 0.2

Status: future comparison format; derived evidence, not Experiment authority.

## Purpose

Version 0.1 remains the historical per-run envelope used by M12-S1. Version 0.2
adds protocol variables that changed after S1. A future result must not attribute
all improvement to canonical tooling when branch topology or execution context
also changed.

## Additional fields

```json
{
  "comparisonContract": "M12MaturityComparison 0.2",
  "implementationMode": "PROMPT_BOUND_PROTOTYPE|CANONICAL_EXPERIMENT_TOOLING",
  "branchAllocation": "PER_WORKER|PER_ROLE",
  "roleBranch": "ref-or-unknown",
  "workerId": "worker-id",
  "role": "role-id",
  "writerPhase": "ACTIVATION|EVALUATION|TERMINATION_PROPOSAL|TERMINAL_EVALUATION|ROLE_NOOP",
  "requestedExecutionContext": "CHATGPT_WEB_STANDALONE_NON_WORK|WORK|unknown",
  "observedExecutionContext": "NORMAL|WORK|unknown",
  "executionContextEvidence": "PROVIDER_VERIFIED|USER_REPORTED|UNKNOWN",
  "executionContextMatch": false,
  "expectedRoleBranchHead": "sha-or-unknown",
  "observedRoleBranchHeadBefore": "sha-or-unknown",
  "observedRoleBranchHeadAfter": "sha-or-unknown",
  "protocolDeltas": []
}
```

The complete record also carries every field from `M12S1ComparisonRecord 0.1`.
Unknown never equals PASS.

## S1 protocol baseline

```json
{
  "implementationMode": "PROMPT_BOUND_PROTOTYPE",
  "branchAllocation": "PER_WORKER",
  "requestedExecutionContext": "unknown",
  "observedExecutionContext": "WORK",
  "executionContextEvidence": "USER_REPORTED"
}
```

## Future protocol target

```json
{
  "implementationMode": "CANONICAL_EXPERIMENT_TOOLING",
  "branchAllocation": "PER_ROLE",
  "requestedExecutionContext": "CHATGPT_WEB_STANDALONE_NON_WORK",
  "observedExecutionContext": "NORMAL",
  "executionContextEvidence": "PROVIDER_VERIFIED"
}
```

The Manager/GitOps role branch is shared by A and B. Worker identity remains
evidence attribution, not branch ownership. Concurrent or stale writes are
blocked by phase ordering and expected-head/CAS.

## Comparable invariants

The following remain directly comparable across protocol versions:

- run budget;
- zero mutations in `main` by tasks;
- no write-as-probe;
- canonical plan before apply;
- allowlisted changed paths;
- aggregate readback;
- false-pass count;
- scope-escape count;
- provider-gap classification;
- terminal disposition durability;
- residual count after cleanup.

Changes to implementation mode, branch allocation, execution context, schedule
ordering or provider are explicit protocol deltas.
