# M12 — constraints for the next scheduled maturity protocol

Status: design constraint; no S2 admission and no task creation.

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

The following text belongs to the task creation request, outside the per-run
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

Every future per-run prompt also declares:

```text
expectedExecutionContext=CHATGPT_WEB_STANDALONE_NON_WORK
```

If the runtime can observe a mismatch, it returns `ENVIRONMENT_MISMATCH` with
`mutation.attempted=false`. If the runtime cannot observe its context, it
returns `UNKNOWN_EXECUTION_CONTEXT`; it does not claim a match.

## Preconditions before S2

No task or experiment branch is created until:

1. S1 closure and cleanup readback pass;
2. a remote provider executes and validates the canonical planner;
3. one manual branch-confined plan/apply/readback qualification passes;
4. the S2 charter fixes role manifests, writer phases, receipt paths, budget,
   death conditions and cleanup;
5. task creation can confirm normal standalone context or fail closed.
