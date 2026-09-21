# Candidate ToolSurface contract — governed multi-path Git mutation

Status: **discovery candidate, not yet a public capability**.

## Purpose

Expose the repository's already-proven `mutate-files` semantics at the execution boundary so an agent can perform one coherent branch mutation without manually orchestrating Git-data plumbing.

The tool is an automatic transmission over the existing engine. It does not create a new mutation model.

## Candidate request

Conceptually:

```json
{
  "repository": "owner/repository",
  "branch": "work/example",
  "expectedHead": "<git-sha>",
  "message": "Concise commit message",
  "changes": [
    {"path": "a.txt", "content": "..."},
    {"path": "b.txt", "delete": true}
  ],
  "governanceContext": {
    "workId": "<optional when the host already binds it>",
    "cycleId": "<optional when the host already binds it>"
  }
}
```

The concrete schema should reuse existing Agent Tool / Remote Canonical contracts rather than inventing parallel identifiers where the host already has them.

## Candidate response

The successful result should expose proof, not merely `ok: true`:

```json
{
  "status": "PASS",
  "branch": "work/example",
  "parentHead": "<expected-head>",
  "branchHead": "<new-commit>",
  "changedPaths": ["a.txt", "b.txt"],
  "planHash": "...",
  "bundleHash": "...",
  "readbackHash": "..."
}
```

Full evidence may remain inspectable behind the result, but these fields are sufficient for ordinary caller continuation.

## Required semantics

The host/tool must:

1. reject `main` or other forbidden control targets under the current policy;
2. require exact expected branch head;
3. canonicalize and reject duplicate/non-canonical path operations;
4. bind UTF-8 contents to hashes before mutation;
5. prove ownership at the existing governed boundary when the mutation is agent-owned;
6. build one candidate tree over the exact base tree;
7. create one commit whose parent is exactly `expectedHead`;
8. update the ref non-force;
9. read back the resulting ref/tree/content;
10. return the existing GitMutationPlan/GitMutationBundle proof or a lossless projection of it;
11. remain reentrant/fail-closed on stale head, ownership loss, content mismatch or provider ambiguity.

## Explicit non-goals

The first version must not:

- create Work, lease, Agent Cycle or Delivery authority;
- acquire ownership implicitly unless an existing semantic composer already owns that responsibility;
- create PRs;
- wait for CI;
- merge PRs;
- choose a provider dynamically;
- support multiple forges;
- add persistent session/transaction state;
- retry a stale plan by silently rebasing;
- force-update refs.

Those are different responsibilities.

## Why a ToolSurface rather than another repository wrapper

The repository already has:

- `git_mutation_plan.mutate_files`;
- `git_mutation_bundle`;
- `remote_canonical_execution._execute_multi_path`;
- Agent-owned mutation guarding.

Adding another Python composer would mostly compensate for the fact that the chat/tool host currently exposes low-level GitHub operations separately.

The ergonomics gap is therefore above the repository engine and below semantic project intent.

## Adoption gate

Promote this candidate only if the live atomic discovery experiment passes and a second representative multi-file task demonstrates the same reduction.

For a multi-file task, target:

- one agent-facing mutation request;
- one branch commit for one coherent logical patch;
- no caller-managed per-file branch-head propagation;
- canonical proof/readback still available.

For a single-file task, the tool may be neutral rather than superior; that is acceptable. The justification is repeated multi-path work, not universal replacement of every Git action.

## Fallback

Until such a ToolSurface exists, prefer the existing atomic Git-data primitives for coherent multi-file mutations when practical, but do not encode that raw choreography as a new permanent repository abstraction.
