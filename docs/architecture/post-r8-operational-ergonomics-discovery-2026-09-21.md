# Post-R8 operational ergonomics discovery — 2026-09-21

Status: **evidence supports an execution-surface gap, not a new repository architecture gap**.

## Question

After closing R8, is the remaining agent friction task-specific, or does the same execution-edge choreography recur strongly enough to justify a narrower ToolSurface?

The discovery compares four representative cases and inspects the mutation primitives already present in the repository and GitHub connector.

## Representative samples

| Sample | Shape | Durable change | Observed execution characteristic |
| --- | --- | --- | --- |
| PR #314 | single-file documentation edit | 1 file / 1 commit | little benefit from multi-path batching; PR/CI/merge ceremony dominates |
| PR #334 | multi-file retirement refactor | 6 files / 6 branch commits | one semantic recut became sequential per-file mutations plus readbacks |
| PR #333 | workflow/runtime retirement | 8 files / 9 branch commits | same Git/CI identifiers and readback choreography repeated across files |
| PR #328 | authority-bound live canary | governed `git.files.mutate` | positive branch mutation PASS with exact readback; attempt against `main` BLOCKED with no unintended write |

PR #332 is intentionally not used as the primary quantitative sample because its 51 commits include genuine design iteration and reverted scope, not only mechanical mutation overhead.

## What repeats

Across the representative normal changes, the semantic decision is usually small relative to the execution ceremony:

1. observe exact branch/main head;
2. create or select a work branch;
3. read each file/blob needed for CAS;
4. construct a mutation plan;
5. mutate files sequentially when using Contents API actions;
6. propagate the new branch head after every write;
7. read back content/absence;
8. create PR;
9. discover exact PR head SHA;
10. observe applicable CI runs and their real jobs;
11. merge with expected-head protection;
12. re-observe main.

The safety-relevant parts are valuable: exact-head preconditions, non-force publication, ownership where required, and readback must remain.

The avoidable part is that the agent coordinates those mechanics individually.

## Existing repository capability

The repository already contains the semantic and verification machinery needed for atomic multi-path Git mutation:

- `GitMutationPlan 0.1` includes `mutate-files`;
- `GitMutationBundle 0.1` binds ordered path operations, exact content hashes, base head/tree and changed paths;
- `remote_canonical_execution._execute_multi_path()`:
  - builds and validates the bundle;
  - materializes blobs;
  - creates a candidate tree;
  - verifies tree proof;
  - creates one commit with the exact observed parent;
  - publishes the ref non-force;
  - reads back content/deletion;
  - validates bundle readback;
  - returns aggregate PASS evidence;
- the Agent-owned Git route can wrap mutable provider calls with Coordination ownership proof.

Therefore a new repository-side mutation engine is not justified.

## Existing connector capability

The connected GitHub ToolSurface already exposes the lower-level provider primitives required by the bundle path:

- create branch;
- create blob;
- create tree;
- create commit with parent;
- update ref non-force;
- fetch commit/Git-data resources;
- fetch file/content;
- compare commits;
- create/inspect/merge PR;
- observe workflow runs/jobs.

This means the missing capability is not raw provider power. It is **composition at the ToolSurface boundary**.

## Live atomic-mutation experiment

This discovery checkpoint itself is materialized as a single two-path Git tree mutation rather than two sequential Contents API commits:

`create branch -> observe base tree -> create tree with two paths -> create commit(parent=exact head) -> update ref(non-force) -> readback`

The experiment intentionally uses existing connector primitives only. It tests whether one logical multi-file change can remain one commit without adding repository runtime.

Success criteria:

- exactly one branch commit for both discovery documents;
- parent equals the exact observed main head;
- compare reports exactly the two intended changed paths;
- both contents read back exactly;
- no force update;
- no runtime/authority/lifecycle changes.

## Friction comparison

For a coherent N-file mutation whose contents are already known:

### Contents API shape used heavily during R8

Agent-facing orchestration grows approximately with N:

- N file/blob observations when needed;
- N sequential write/delete calls;
- N branch-head transitions;
- N readbacks;
- per-write blob/head identifiers.

The repository history also tends toward one commit per write action.

### Existing atomic Git-data shape

Provider calls still exist internally, but the logical mutation has constant publication shape:

- observe base head/tree;
- build one candidate tree containing N changes;
- create one commit;
- publish one non-force ref update;
- aggregate readback.

The number of content payloads remains N, necessarily, but branch-head/CAS/publication choreography no longer scales with N.

### Desired agent-facing shape

A host/tool should expose the already-existing semantic operation as one governed action:

`mutate_files(branch, expected_head, changes, message, governance_context?) -> verified aggregate receipt`

The tool performs internal provider calls and returns the canonical plan/bundle/readback proof.

## Finding

The decision-rule conditions from the R8 closeout are now substantially met:

1. **Recurring choreography:** yes, visible in single- and multi-file changes, especially #333/#334.
2. **Execution-edge problem:** yes; repository semantic owners are no longer the source of confusion.
3. **No new authority/lifecycle needed:** yes; existing Work/Coordination/Agent Cycle/Delivery remain sufficient.
4. **CAS/readback can remain:** yes; the existing bundle path already proves them.
5. **Administrative reduction is material:** yes for multi-file changes; weak for one-file changes.
6. **No generic forge abstraction required:** yes; target the current GitHub ToolSurface first.

## Recommendation

Do **not** build another repository mutation module.

The next useful capability should be a thin ToolSurface/host binding over the existing governed multi-path mutation semantics. Prefer extending the connected GitHub/Agent Tool surface with an atomic governed `mutate-files` action over adding a compatibility layer inside MobiliPresenter.

The capability should initially target GitHub only and the already-supported mutation set. Generalize only after another provider/forge produces a real second case.

## Scope boundary

This discovery does not propose combining PR creation, CI waiting and merge into the same mutation transaction. Those are separate lifecycle stages with meaningful stop/fail points.

The first ergonomic improvement should solve only branch content mutation:

`observe -> plan/bundle -> mutate -> readback`

PR/CI/merge orchestration can be measured separately after this improvement exists.
