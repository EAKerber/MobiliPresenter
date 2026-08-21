# MobiliPresenter — UI / UX current

Current role document: [`ui-ux-v0.1.md`](./ui-ux-v0.1.md).

This pointer does not replace the versioned Kickstart. It identifies the current runtime contract for the `ui-ux` role.

## Current bootstrap

Every UI/UX worker must:

1. read `AGENTS.md`;
2. observe `ops/state/project.json`;
3. read this pointer and the versioned role document above;
4. resolve current UI decisions/contracts using the precedence rules in the versioned Kickstart;
5. observe Coordination Leases and Continuation State before write/continuation decisions;
6. inspect the executable `viewer-next/src/api/ui-contract.ts` before assuming a UI capability exists.

There is currently no UI-specific Scheduler, continuation store, lease store, health protocol or runtime state layer. Reuse the canonical project surfaces instead of creating parallel mechanisms.

## Current product baseline note

`Responsive Fixed-Frame 0.1` is integrated and is the current UI baseline declared by ProjectState. It preserves the fixed-camera presentation frame across desktop, compact landscape, tablet and mobile layouts.

The coordinated module-presentation metadata plan is accepted at checkpoint
`MODULE-PRESENTATION-METADATA-PLAN-0.1-ACCEPTED`. Its implementation is not
admitted. The current plan is
[`docs/plans/coordinated-module-presentation-metadata-v0.1.md`](../../plans/coordinated-module-presentation-metadata-v0.1.md).

The next declared transition is
`plan-m9-m13-closure-before-module-metadata-implementation-v0.1`. It is not an
assignment to UI. A UI worker must not claim the infrastructure transition or
start metadata implementation merely from `nextTransition`; explicit role
scope, Work, continuation, handoff or routing remains required by the versioned
Kickstart.
