# E4 operational qualification checkpoint — 2026-09-22

Status: **integrated; live fail-closed and kitchen-window inspection qualified; first live PASS mutation intentionally deferred to the next genuine governed Work.**

## Scope

This checkpoint records the operational evidence for:

- E4 governed mutation counter;
- E4a terminal-Work fast path;
- E4b remote kitchen-window inspection.

It does not add runtime behavior, authority, state, workflow or persistence.

## Integrated heads

- E4 PR #342 head `1eded619deb713040338145804bffe47f7c08cec`, merged as `b75831fb6a688a3f0f9f50ab5cbbf4421446ede9`.
- E4a PR #343 head `4412e98f822247a05b1ba6ae9f8538c09c5f878a`, merged as `11c94f5a82e18309749c84feabcb0fe9ba06af59`.
- E4b PR #344 head `7f2fda5e444a0b6ad61390c4c35c8d25c5da083f`, merged as `6a7893d31eba09c1b4f4dc4af046471ff54cff78`.

For all three PR heads, exact-head `verify`, `ownership` and `snapshot` checks completed successfully. Branch-hygiene `prune` checks were skipped where non-applicable.

## Live fail-closed evidence

A governed mutation request against terminal Work `r6-black-box-paved-path-canary` targeted branch:

`work/operations/r6-black-box-live-canary`

and attempted to create:

`docs/e4-terminal-canary.txt`

The service returned:

- status: `BLOCKED`;
- blocker: `GOVERNED_MUTATION_WORK_TERMINAL`;
- nextSafeAction: `NONE`;
- branchHead: null;
- parentHead: null;
- Work window available;
- authority/cycle/decision/execution/git windows absent because execution did not proceed.

The sentinel file is absent from both `main` and the target branch after the request.

An earlier negative canary using `docs/e4-negative-canary-sentinel.txt` is also absent from both refs.

## Kitchen-window evidence

The terminal canary result referenced:

- runId: `35791736004`;
- runAttempt: `1`;
- artifact: `governed-mutation-35791736004-1`;
- resultHash: `cf0c256107c6db77460e49d55c6f83b622bfec57651efa890b87ffaee5cf7755`;
- Work window member: `work.json`;
- Work window hash: `fc988298055572d0eff0a5b30e0857b98813b8d62b37d3a607f5ccccdbe57568`.

E4b inspection requested that exact result/run/window tuple and returned PASS with:

- the same resultHash;
- the same window reference and hash;
- the historical Work payload from the artifact.

Independent readback downloaded artifact ID `10722326971` from run `35791736004`. Canonical JSON SHA-256 of `evidence/work.json` recalculated to:

`fc988298055572d0eff0a5b30e0857b98813b8d62b37d3a607f5ccccdbe57568`

which exactly matches both the E4 result window reference and the E4b inspection result.

Therefore the kitchen window is proven to expose the original hash-bound historical evidence, not a fresh reconstruction.

## Authority state

At this checkpoint, Coordination is clean:

- intents: none;
- leases: none;
- revision: `57660890e667a72779cb405eeec8e2ae85aa58b2`.

No suitable active Work/cycle/write binding exists for a legitimate positive E4 mutation canary.

## Positive PASS policy

E4 must not create a Work, Agent Cycle or write lease merely to demonstrate that E4 can create a Work, Agent Cycle or write lease.

The first live PASS mutation through the counter is therefore deferred until the next genuine governed Work whose exact cycle semantic host contains E4 and whose lifecycle/Coordination authority is already valid for that work.

When that opportunity arrives, qualification should record:

1. four semantic caller inputs only: Work ID, branch, changes, message;
2. PASS summary with parentHead, branchHead and changedPaths;
3. non-null decision, authority, execution and git windows;
4. canonical receipt/readback hashes;
5. exact branch readback;
6. remote inspection of at least one non-Work window.

## Current ergonomic conclusion

The normal counter surface has reached the intended separation:

`intent / Work + branch + changes + message -> compact result`

while the detailed chain remains available pull-style through kitchen windows.

The remaining unqualified item is not architectural plumbing. It is the first naturally occurring live PASS execution through this surface.
