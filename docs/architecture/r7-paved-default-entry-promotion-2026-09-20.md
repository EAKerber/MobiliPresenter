# R7 — promote semantic Work entry as the operational default

Status: **candidate**.

## Purpose

R6 is live-proven through the fresh positive + negative black-box canary and governed Delivery in PR #328. R7 now changes the default operational model instead of adding another execution wrapper.

The already-integrated semantic entry composition becomes the advertised Work-bound entry surface. Direct Agent Cycle `begin` remains implemented for diagnostics, tests and explicit recovery, but is removed from the stable public toolbox surface.

## Default-path change

The public bootstrap projection now behaves as follows:

```text
no Work selected
  -> OBSERVE_WORK
  -> status --work-id <work-id>

Work requires a new cycle
  -> bootstrap.pavedEntry
     surface: journey-entry
     implementation: tools.agent_tools.journey_entry.compose_entry
     executionBoundary: host-provider
     toolSurface: github-connector-tools
```

The projection intentionally does not emit a shell/CLI execution command for hosted entry. R6d already established that direct CLI apply uses `GhApiTransport` and is a bounded CLI/recovery adapter, not the normal provider-backed path.

## Demotion in the same migration window

`agent.py begin` is removed from `TOOLBOX_COMMANDS`, the stable public façade inventory. The underlying command remains reachable for diagnostic/test/recovery cases so R7 does not destroy break-glass capability.

The manager-gitops role contract and permanent agent guidance no longer present direct `begin` as normal Work-bound entry.

This demotes the old normal-path knowledge of manually choosing Agent Cycle begin and treating a local/CLI begin as equivalent to provider-backed hosted entry.

## Safety and authority

No new command, lifecycle, authority, state machine, provider selector, executor bridge or compatibility layer is introduced.

The normal entry implementation remains `JourneyEntryComposition 0.2`, which delegates to canonical Work, Hosted Agent Cycle and handle contracts. The configured host/provider remains `github-connector-tools`; shell `gh`, raw HTTP and local git are not promoted.

`bootstrap.pavedEntry` is a read-only projection. It authorizes no mutation and does not become an authority.

## Promotion evidence

R7 requires:

1. R6 live proof already integrated in PR #328;
2. regression that direct `begin` is no longer advertised in the stable toolbox;
3. regression that Work-bound `BEGIN_NEW_CYCLE` projects the existing semantic host/provider entry;
4. exact-head Agent Ops, Coordination Guard and Supervisor Snapshot PASS;
5. integration through the normal branch/PR path.

## Migration accounting

- new permanent orchestration modules: **0**;
- new mutation surfaces: **0**;
- promoted existing semantic surface: `journey-entry`;
- demoted public normal-path surface: direct `agent.py begin`;
- provider default: unchanged, `github-connector-tools`;
- R8 subtraction target: inventory and remove/privatize obsolete direct-entry callers plus temporary migration shadows such as `journey_shadow`.
