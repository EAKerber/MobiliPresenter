# ADR-0007 — Work authority evolution

- Status: accepted — M5B promoted ContinuationState 0.2
- Date: 2026-08-16

## Context

ProjectState 2.0 intentionally retained a small execution summary while the repository still had no dedicated work model beyond `ContinuationState 0.1`. The existing `coordination/continuations` Git authority already owns durable work progress, branch/PR linkage, blockers and handoff state, and already has one canonical writer with exact-plan, CAS and readback semantics.

Creating a second WorkState authority would duplicate those facts and create a reconciliation problem.

## Decision

M5 evolves the existing `continuations` managed authority instead of creating a parallel WorkState authority.

During M5A:

- `ContinuationState 0.1` remains the live/current contract;
- `ContinuationState 0.2` exists only as a candidate contract;
- `operational_view()` provides one normalized WorkItem representation across both versions;
- the live executor rejects 0.2 candidates before authority observation or mutation;
- existing 0.1 TransitionPlan identities and hashes remain stable.

The candidate 0.2 contract renames execution identity fields to explicit worker semantics:

- `actor` → `workerId`;
- `blockedBy` → `blockers`;
- `handoffTo` → `handoffToWorkerId`;
- `dependsOn` is added as the only persisted dependency relation.

`workerId` and handoff targets use the shared `WorkerId` identity contract. Role and session identity are not persisted in WorkItems.

## WorkGraph

WorkGraph is a deterministic read-only projection over normalized WorkItems. It is not persisted and is not an authority.

The initial graph has one edge type only: `dependsOn`.

It rejects missing dependencies, self-dependencies, cycles, duplicate active execution branches and duplicate active PR ownership. Terminal WorkItems may share historical branch/PR identity because they no longer represent active execution ownership.

Derived node properties include terminal, runnable, dependency-blocked and handoff-required. Scheduling policy remains outside the graph.

## Transition boundary

Existing 0.1 actions remain create, advance, wait, handoff, resume and done. M5A characterizes their plan hashes so the compatibility refactor cannot silently change the live protocol.

Candidate 0.2 adds `bind-execution` and `restart`. These actions cannot mutate the live authority until M5B promotes 0.2 atomically.

Dependencies are execution guards, not metadata only: progress/completion of a dependent WorkItem requires its dependencies to be DONE. The relevant inventory must be supplied to semantic validation rather than hidden inside a persisted graph.

## Authority and writer

The managed authority remains:

- branch: `coordination/continuations`;
- path: `ops/continuations`;
- semantic owner: `work`;
- canonical writer: `tools.continuation_remote`.

No new authority branch, WorkState file or graph state is introduced.

## Consequences

Positive:

- M5 reuses proven CAS/readback infrastructure;
- work facts continue to have one authority and one writer;
- consumers can migrate before the authority schema changes;
- dependency semantics become deterministic without introducing a project-management subsystem.

Costs:

- M5A temporarily supports current 0.1 plus candidate 0.2 in code;
- M5B must remove that compatibility after a verified authority migration;
- historical terminal probe records remain sanitation debt for M6.

## Non-decisions

This ADR does not define branch retention, WorkItem priority, deadlines, fairness, subtasks, role manifests, persistent sessions, deletion of terminal work records, UI/Engine behavior, or renaming the `coordination/continuations` authority.


## M5B promotion

M5B migrated the existing `coordination/continuations` authority atomically from `ContinuationState 0.1` to `ContinuationState 0.2`. The authority branch/path and canonical writer did not change. The 0.1 compatibility bridge and candidate schema are retired after verified readback. All normal writes validate the complete candidate WorkGraph before CAS and the complete readback WorkGraph afterward. Historical terminal probe records remain sanitation debt for M6.
