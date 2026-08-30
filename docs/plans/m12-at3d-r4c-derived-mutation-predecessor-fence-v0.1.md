# M12-AT3D-R4C — Derived Mutation Predecessor Fence 0.1

Status: implementation slice  
Parent refactoring track: R4 — seal and ordered asynchronous execution  
ProjectState selection: `implement-m12-at3d-r4c-derived-mutation-predecessor-fence-v0.1`

## Purpose

Prevent a lifecycle `release` for a branch from overtaking an earlier, same-cycle mutating Agent Tool request for that same branch.

R4A established a stable request seal and safe late-result observation. R4B made incomplete close explicitly `WAITING` without hidden polling or operation replay. R4C closes the first concrete cross-carrier ordering gap: Hosted Agent Tool and Hosted Agent Write Lease use independent workflow runs, so a later release can otherwise reach Coordination before an earlier Git mutation reaches its terminal result.

## Design constraint

Derive order from records that already exist.

Do not add:

- a queue;
- sequence-number authority;
- scheduler state;
- a new lock;
- a mutable session registry;
- a second Coordination authority;
- a new persistent predecessor artifact;
- polling or sleeps;
- automatic operation replay.

The strong bus record already provides the needed ordering identity:

- `cycleInstanceId`;
- request comment identity;
- normalized Agent Tool request;
- branch target;
- request hash;
- correlated terminal result;
- existing at-most-once attempt fences.

## Fence

The fence applies only to lifecycle `release`.

At lifecycle dispatch inspection time:

1. Revalidate the existing lifecycle bundle exactly as today.
2. Read the issue comments once.
3. Use the current lifecycle request comment as the **predecessor request frontier**.
4. From strong cycle records before that frontier, derive Agent Tool requests that:
   - target the same branch;
   - are `shared-durable-mutation`;
   - resolve through the current policy to `mutation-execute` for the cycle intent.
5. Observe correlated Agent Tool terminal results from the full current comment set. This permits a result delivered after the lifecycle release request to clear the fence without changing the predecessor set.
6. Classify:
   - all predecessors `PASS` or `BLOCKED` -> `CLEAR`;
   - at least one predecessor has no terminal -> `PREDECESSOR_WAITING`;
   - any predecessor is `UNKNOWN` -> `PREDECESSOR_UNKNOWN`;
   - duplicate/malformed/binding-inconsistent evidence -> fail closed.

`BLOCKED` is considered terminal for ordering because the Agent Tool mutation host only reports `BLOCKED` when the mutation is not ambiguous. `UNKNOWN` is not safe to cross.

## Carrier behavior

### `PREDECESSOR_WAITING`

- no lifecycle attempt marker;
- no Coordination mutation;
- no lifecycle terminal result;
- dispatch workflow succeeds as a non-terminal observation;
- canonical `close(handle)` continues to expose the incomplete lifecycle as `WAITING`.

There is no wake-up service. The caller can reobserve/reissue the release after the predecessor terminates. Current heads are then bound into the new request, so this is a fresh derived operation rather than replay.

### `PREDECESSOR_UNKNOWN`

- no lifecycle attempt marker;
- no Coordination mutation;
- publish a lifecycle `UNKNOWN` terminal with blocker `AGENT_WRITE_LIFECYCLE_MUTATION_PREDECESSOR_UNKNOWN`;
- preserve ambiguity for explicit recovery.

## Scope boundaries

R4C does not:

- change Agent Tool mutation semantics;
- change Git CAS;
- change lease ownership rules;
- change Coordination writer semantics;
- select providers;
- alter ProjectState;
- alter Work authority;
- solve arbitrary DAG scheduling;
- serialize different branches;
- serialize read-only tools;
- create a generalized cross-carrier queue.

The first productive scope is the currently admitted `git.files.mutate` path, but mutation classification is derived through the existing Agent Tool policy rather than hard-coding the tool id.

## Files

Expected implementation surface:

- `tools/agent_write_lifecycle_host.py`
- `.github/workflows/agent-write-lease-dispatch.yml`
- `tools/tests/test_agent_write_lifecycle_predecessor_fence_r4c.py`
- this plan

No schema or semantic registry change is expected.

## Qualification

### Unit / semantic gates

Required cases:

- same-cycle, same-branch earlier mutation without terminal -> `PREDECESSOR_WAITING`;
- a correlated late `PASS` result clears the fence;
- a correlated `BLOCKED` result clears the fence;
- `UNKNOWN` predecessor prevents release;
- different branch remains independent;
- read-only tool does not fence;
- acquire/renew behavior remains unchanged;
- duplicate correlated results fail closed;
- `PREDECESSOR_WAITING` is returned before attempt creation.

Run the complete existing test and semantic gate suite through PR CI.

### Hosted qualification

Before promotion, prove on the Hosted bus that:

1. acquire is active;
2. a mutating Agent Tool request is recorded;
3. a release request is recorded before the tool terminal;
4. lifecycle dispatch observes `PREDECESSOR_WAITING`;
5. no lifecycle attempt and no Coordination release occur in that state;
6. close is non-terminal/WAITING rather than polling;
7. after the mutation terminal, a fresh release with current heads can complete;
8. close then reaches PASS;
9. disjoint branch traffic is not serialized by the fence.

If orchestration makes step 3 impossible to reproduce reliably without adding test-only timing hooks, qualify the pure ordering derivation plus a hosted no-regression smoke and record that limitation instead of introducing timing behavior into production.

## Death / extension condition

Do not generalize this mechanism into a scheduler merely because more carriers appear.

Extend the predecessor predicate only when a new productive mutation carrier has an observed ordering conflict that cannot be represented by the existing strong request/result records. If a future unified carrier makes this cross-workflow race impossible, remove the fence rather than preserving it as ceremonial infrastructure.
