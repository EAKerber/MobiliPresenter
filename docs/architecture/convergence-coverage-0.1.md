# M11-CV1A — Convergence Coverage & Residue Inventory 0.1

Status: **historical evidence. CV1A/CV1C fulfilled the closed `lock`/`ops` convergence objective in M11; the runtime ConvergenceInspection surface was retired after the final proof.**

## Purpose

CV1A established the evidence boundary required before compatibility surfaces could be migrated or retired. It deliberately separated:

- `coverageStatus`: whether required consumer classes were observed;
- `retirementReadiness`: whether a fully observed alias had no supported consumers requiring migration.

A healthy pre-retirement result could therefore be:

```text
coverageStatus = PASS
retirementReadiness = MIGRATION_REQUIRED
```

## Closed subjects

The inspection tracked exactly two M11 aliases:

1. `coordination.lease` alias `lock`, scope `cli-name`;
2. `branch.domain.operations` alias `ops`, scope `legacy-branch-namespace`.

The set was intentionally closed. It was never a general-purpose semantic lint framework.

## Coverage boundary

Coverage combined tracked repository consumers with validated live branch/PR/Work evidence reused from `GitPrunePlan 0.4`. It distinguished workflow branch listeners from repository path filters, so retiring the branch listener `ops/**` never implied deleting repository path filters for `ops/**`.

It also distinguished historical grammar recognition from semantic projection: `ops` may remain in `branchGrammar.legacyNamespaces` while no longer resolving to semantic domain `operations`.

## Final M11 result

The final CV1C proof observed complete coverage and reported:

```text
lock = ABSENT / PASS / RETIRED
ops  = ABSENT / PASS / RETIRED
triggerRetirement = []
residues = []
```

The legacy `lock` compatibility surface, the semantic alias `ops`, and the retired `ops/**`, `renderer/**`, and `architecture/**` branch listeners were removed only after their live relations were proven absent. Repository path filters remained intact.

## Runtime retirement

Because the inspection subject set was exhausted by M11, keeping `tools/semantics/convergence.py`, its dedicated tests, and Agent Ops prune/convergence artifact generation would turn temporary migration scaffolding into permanent runtime surface.

After the final proof was captured, M11 closure therefore retired that runtime scaffolding. Branch lifecycle planning remains owned by Branch Hygiene and its canonical `GitPrunePlan` path; normal Agent Ops continues to run OperationalSemantics coverage, ProjectMachine, Routine, Maintenance, Scheduler, and integration evidence.

## Authority boundaries

The historical inspection was always:

```text
readOnly = true
semanticAuthority = false
authorizesMutation = false
```

It never mutated Coordination, Work, ProjectState, aliases, branch refs, or writer topology. This document remains as the design/evidence record; it is not a current invocable contract.
