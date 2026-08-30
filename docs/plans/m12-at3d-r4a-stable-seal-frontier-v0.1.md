# M12-AT3D-R4A — Stable Seal Frontier & Late-Result Observation 0.1

Status: implementation slice R4A  
Baseline: `main@094aa7b2b2f02b7f6bf87b0e2498cce8d78d7e46`  
ProjectState transition: `implement-m12-at3d-r4a-stable-seal-frontier-v0.1`

## Purpose

Remove the moving close window from Hosted Agent Cycle without creating a new seal
authority or changing the public close status vocabulary.

Before R4A, every close observation used the current close comment as both:

- the final request boundary; and
- the final result observation boundary.

That made bounded stabilization unable to observe a result emitted after the current
close, while a later close retry expanded the request set and could retroactively
admit new work.

R4A separates those two facts by derivation:

```text
begin -------- first bound close ---------------- current close
       requests             late results / receipts
             ^ seal                     ^ observation horizon
```

The first valid close request strongly bound to the cycle is the stable **seal**.
The current close attempt remains the observation horizon.

## No new authority

The seal is derived from immutable Hosted Agent Bus records already used for cycle
identity. R4A adds no:

- mutable seal file;
- session authority;
- writer;
- schema version;
- Work or Coordination mutation;
- provider selection;
- mutation authorization;
- close side effect.

`hosted_cycle_records` remains a read-only record scanner.

## Canonical frontier semantics

`hosted_cycle_records.collect()` keeps its existing public call shape. The supplied
`close_comment_id` is the current observation cutoff. Internally it derives the first
valid cycle-bound Hosted close at or before that cutoff.

A close is eligible as the stable frontier only when it is structurally bound to the
same Hosted cycle:

- legacy `HostedAgentCycleCommand 0.1` close: exact begin, actor, intent and live scope;
- handle-first `HostedAgentCycleCommand 0.2` close: valid hosted handle whose locator,
  cycle instance, context and actor bind to the manifest.

Historical fixtures or pre-R4 carrier records without a parseable close marker retain
the former behavior: the supplied current cutoff is used as the seal.

### Request frontier

Strong Agent Tool and write-lease requests are eligible only before the seal.
A strongly bound request after seal fails closed with:

`HOSTED_CYCLE_RECORD_POST_SEAL_REQUEST`

Ambient direct RemoteCanonical requests after seal are not promoted into the sealed
request set; their results therefore cannot satisfy the cycle by convenience.

### Result horizon

Bot dispatches/results continue to be observed from begin until the current close
attempt. Existing request hashes, command hashes, begin/actor binding and
`cycleInstanceId` rules determine whether they belong to the pre-seal request set.

Thus a terminal result emitted after the first close may satisfy a request that was
accepted before the seal on a later close retry.

## Trace compatibility

`AgentCycleExecutionTrace 0.1` is retained.

Its existing `window.closeCommentId` now records the derived seal rather than the
current retry comment. No new field is required because the trace schema never
required terminal result IDs to be less than `closeCommentId`.

When the first close is also the current observation (`seal == observation`), the
record set and trace semantics are equivalent to the previous single-window behavior.

## Shared consumers

The change is intentionally made in `hosted_cycle_records.collect()` rather than in
Hosted close, trace, lifecycle and resource projection independently.

Consequently the same sealed request set is consumed by:

- execution trace;
- mutation receipt discovery;
- touched-resource projection;
- obligation inventory projection;
- write-lifecycle close inspection.

This prevents trace from accepting a late result while another close-time projection
quietly uses a different request frontier.

## Compatibility and fail-closed behavior

R4A preserves:

- `UNKNOWN != PASS`;
- no operation replay during observation retry;
- existing result duplicate/orphan checks;
- exact cycle identity and handle validation;
- existing lease/CAS/domain-writer authority;
- existing close result vocabulary.

R4A does **not** yet replace the three short stabilization observations with a public
`WAITING` result. A first close may still end non-PASS when a required result has not
arrived. The improvement is that a later `close(handle)` can reuse the same sealed
request set after the correlated result arrives.

## Qualification

Focused tests prove:

1. legacy and handle-first retry derive the first valid close as the same stable seal;
2. a pre-seal request may match a post-seal result on retry;
3. the trace keeps the first close ID while observing the late terminal result;
4. a same-close observation preserves previous behavior;
5. a strongly bound post-seal request fails closed rather than joining the retry;
6. duplicate late results retain the existing duplicate-result guard;
7. malformed/unrelated earlier close comments cannot become the seal;
8. historical unmarked close fixtures keep their current cutoff.

Repository PR/CI is the broad consumer scan. After semantic qualification, R4A should
also receive a Hosted qualification that deliberately lets a terminal result land
after the first close and proves a second handle-close can finish against the same
seal without replaying the operation.

## Out of scope

R4A intentionally does not add:

- public `WAITING`/`PENDING`;
- automatic wake-up/retry;
- new workflow concurrency groups;
- sequence numbers or resource ordering;
- sealed admission at the Tool/Lease carrier boundary;
- Work transitions;
- obligation enforcement in canonical close;
- new bus storage/cursor;
- provider routing;
- compatibility retirement.

Those remain candidates for R4B/R4C/R4D after the stable frontier is proven.

## Exit criterion

R4A is complete when the system can truthfully demonstrate:

> The set of requests belonging to one Hosted Agent Cycle is frozen by the first
> valid bound close, while later correlated results remain observable by a retry of
> that same cycle, without a new begin, operation replay, request-set expansion or
> authority creation.

ProjectState is not advanced as an implementation side effect. The next transition is
reconciled separately after repository and Hosted qualification evidence are complete.
