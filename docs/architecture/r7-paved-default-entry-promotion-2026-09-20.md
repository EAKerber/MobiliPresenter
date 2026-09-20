# R7 — promote semantic Work entry as the operational default

Status: **candidate**.

## Purpose

R6 proved the provider-backed paved path with a fresh positive + negative live canary and governed Delivery. R7 therefore stops treating the semantic entry composition as optional migration scaffolding and makes it the normal Work-bound entry surface.

This recut does not add a new lifecycle, authority, state machine, provider bridge or protocol. It exposes the already-integrated `tools.agent_tools.journey_entry.compose_entry` through the stable `tools/agent.py` facade as `enter`.

## Default-path change

For normal Work-bound execution the sequence becomes:

```text
agent.py status --work-id <work-id>
        |
        v
BEGIN_NEW_CYCLE
        |
        v
agent.py enter --work-id <work-id> --role <role> --intent <intent> ...
        |
        v
existing JourneyEntryComposition -> canonical Hosted Agent Cycle
```

`status --work-id` now projects `enter` for `BEGIN_NEW_CYCLE`. The manager-gitops role contract and permanent agent rules identify this as the normal path.

## Demotion in the same migration window

Direct `agent.py begin` remains available only for diagnostic, tests and explicit recovery use. It is no longer the documented/default entry for Work-bound normal operation.

That demotes the old normal-path knowledge of:

- manually choosing direct Agent Cycle begin;
- treating the local context builder as equivalent to hosted Work-bound entry;
- reconstructing hosted entry mechanics outside `JourneyEntryComposition`.

R8 may further privatize or delete direct-entry surfaces once recovery consumers are inventoried.

## Safety and authority

`enter` delegates to `JourneyEntryComposition 0.2`. It does not implement begin itself.

The existing composer remains responsible for Work observation, canonical begin request construction, idempotent reuse, provider-backed submission, handle validation and fail-closed outcomes. Runtime ToolSurface inventory is still required; absence remains blocked/unknown rather than falling back to shell/CLI transport.

## Promotion evidence

R7 requires:

1. regressions proving the bootstrap projection selects `enter`, not direct `begin`, for Work-bound `BEGIN_NEW_CYCLE`;
2. a regression proving the facade delegates to the existing Journey entry composer;
3. exact-head Agent Ops, Coordination Guard and Supervisor Snapshot PASS;
4. branch/PR integration with no new authority or lifecycle.

## Migration accounting

- added public normal-path surface: `agent.py enter`;
- promoted existing implementation: `journey_entry.compose_entry`;
- demoted old normal-path surface: direct `agent.py begin`;
- net semantic model: one Work-bound entry model over the existing Agent Cycle primitive;
- R8 subtraction target: delete/privatize obsolete direct-entry and migration-shadow surfaces after recovery-use inventory.
