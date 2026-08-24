# M12 — constraints for the next scheduled maturity protocol

Status: historical S2 protocol baseline; S2 was later admitted and executed.

This document originally constrained admission of S2. It is preserved as the
design baseline for that experiment; statements below that say “no S2 admission”
or describe preconditions are historical constraints, not current operational
state.

## Outcome after execution

S2 was subsequently admitted after Remote Canonical/Hosted Agent Cycle changes
and executed on the role branches defined below.

Observed disposition:

- `NOT PASSED / HIGH-VALUE FAILURE`;
- Manager/GitOps A materialized only `ACTIVATION`, after earlier blocked attempts;
- Manager/GitOps B failed closed on repeated `REMOTE_AUTHORITY_DRIFT`;
- UI runs were blocked before the role-scoped Git mutation, so the UI bridge
  remained `UNTESTED`;
- no unexpected branch delta or residual lease remained;
- the experiment exposed two architectural gaps now being addressed by AT2:
  manual tool/envelope orchestration and non-exhaustive close evidence.

The current direction authority is ProjectState; this file no longer controls
experiment admission.

## Branch allocation

Branches belong to roles, not workers:

| Role | Branch | Participants |
|---|---|---|
| `manager-gitops` | `experiment/operations/m12-s2-manager-gitops` | `manager-gitops-a`, `manager-gitops-b` |
| `ui-ux` | `experiment/ui/m12-s2-ui-ux` | `ui-ux-a` |

The role manifest lists participants and allowed writer phases. A and B may
write only their phase-specific receipts on the shared role branch. Every
mutation binds an expected branch head and uses non-force CAS/readback.

Recommended phase order:

```text
manager-gitops-a run 1 -> ACTIVATION
manager-gitops-b run 1 -> EVALUATION
manager-gitops-a run 2 -> TERMINATION_PROPOSAL
manager-gitops-b run 2 -> TERMINAL_EVALUATION
```

Offsets remain `A :00`, `B :30`, `UI :45`, but creation must select a cycle in
which A runs first. A missing predecessor receipt or head drift produces zero
writes.

## Task creation control-plane requirement

The following text belonged to the S2 task creation request, outside the per-run
executable prompts:

```text
Create each automation as a standalone Scheduled Task on the web, from normal
ChatGPT Chat, outside ChatGPT Work/Codex. Do not associate it with a local
project, folder, worktree or Work execution environment.

This is an experimental requirement, not an informal preference. If the
creation surface cannot select and confirm this context, create no task and
return MODE_SELECTION_UNAVAILABLE.

After creation, report the execution context selected for every task. UNKNOWN
does not equal NORMAL.
```

Every S2 per-run prompt also declared:

```text
expectedExecutionContext=CHATGPT_WEB_STANDALONE_NON_WORK
```

If the runtime could observe a mismatch, it returned `ENVIRONMENT_MISMATCH` with
`mutation.attempted=false`. If the runtime could not observe its context, it
returned `UNKNOWN_EXECUTION_CONTEXT`; it did not claim a match.

## Preconditions before S2 — historical

No task or experiment branch was to be created until:

1. S1 closure and cleanup readback pass;
2. a remote provider executes and validates the canonical planner;
3. one manual branch-confined plan/apply/readback qualification passes;
4. the S2 charter fixes role manifests, writer phases, receipt paths, budget,
   death conditions and cleanup;
5. task creation can confirm normal standalone context or fail closed.

These items are retained to reconstruct the experiment’s admission criteria.
They are not current instructions to create or repeat S2.
