# E4b — Remote kitchen-window inspection

Status: **candidate read-only ergonomic completion for E4**.

## Goal

E4 already returns hash-bound window references, but opening a window still required a caller to download and inspect the workflow artifact manually.

E4b makes window inspection a first-class in-house read operation on the existing Remote Canonical Execution Bus.

## Request

`MOBILIPRESENTER_GOVERNED_MUTATION_INSPECT_V0_1`

The request contains only:

- evidence run ID;
- run attempt;
- exact governed-mutation result hash;
- requested window name.

It carries no Work/cycle/lease/Git authority.

## Read path

The existing `governed-mutation-service.yml` receives the inspection marker in a second, read-only job.

It:

1. validates the bus event and inspection request;
2. downloads the exact `governed-mutation-<run>-<attempt>` artifact;
3. validates `result.json`;
4. requires exact run/attempt/resultHash correspondence;
5. opens the requested artifact member through the existing `inspect_window()` hash check;
6. publishes only the validated window payload plus its original window reference.

No fresh authority observation is substituted for historical evidence.

## Result

`GovernedMutationInspectionResult 0.1` contains:

- request hash;
- run/attempt;
- original result hash;
- window name;
- exact window reference;
- validated historical payload;
- inspection hash.

It is explicitly read-only, non-authoritative and cannot authorize mutation.

## Architecture

E4b adds:

- authority: 0;
- store/index: 0;
- workflow: 0;
- Git writer: 0;
- lifecycle behavior: 0.

It extends the existing E4 workflow with a second read-only job.

## Live qualification

After integration, the intended live canary is the E4 terminal-Work run:

- run: `35791736004`;
- attempt: `1`;
- resultHash: `cf0c256107c6db77460e49d55c6f83b622bfec57651efa890b87ffaee5cf7755`;
- window: `work`.

The inspection must return the exact historical Work evidence whose window hash is:

`fc988298055572d0eff0a5b30e0857b98813b8d62b37d3a607f5ccccdbe57568`.

## Promotion gate

Exact-head Agent Ops, Coordination Guard and Supervisor Snapshot must pass before merge. The live window canary then validates the deployed reader end to end.
