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

`Guided Configurator UI 0.3` is the integrated UI baseline in the ProjectState observed when v0.1 was authored. It explicitly supersedes the older three-page `Módulos / Cores / Acessórios` navigation model where those documents conflict.

The next planned development front is `Responsive Fixed-Frame 0.1`, but a UI worker must not claim or start that work merely from a generic `nextTransition`; it still requires explicit role scope/continuation/handoff/routing as defined in the versioned Kickstart.
