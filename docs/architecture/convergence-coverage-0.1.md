# M11-CV1A — Convergence Coverage & Residue Inventory 0.1

Status: implementation slice for M11 convergence. Read-only inspection; no alias retirement.

## Purpose

CV1A establishes the evidence boundary required before compatibility surfaces can be migrated or retired. It does not make a legacy alias disappear merely because the M11 milestone has been reached.

The inspection separates:

- `coverageStatus`: whether the required consumer classes were observed;
- `retirementReadiness`: whether a fully observed alias has no supported consumers that still require migration.

A valid result may therefore be:

```text
coverageStatus = PASS
retirementReadiness = MIGRATION_REQUIRED
```

That is a healthy result, not a failed inspection.

## Subjects

The 0.1 inspection tracks the two explicit M11 aliases already declared by OperationalSemantics:

1. `coordination.lease` alias `lock`, scope `cli-name`;
2. `branch.domain.operations` alias `ops`, scope `legacy-branch-namespace`.

The subject set is closed in 0.1. New aliases require an explicit contract revision rather than silently entering the scan.

## Consumer classes

Coverage is complete only when all of these classes are observed:

- repository tracked files;
- workflow branch triggers;
- current role pointers;
- OperationalSemantics alias declarations;
- live branch inventory;
- open PR branch relations;
- Work authority branch relations.

Repository coverage is derived from the checked-out tracked tree. Runtime Git/PR/Work coverage is reused from a validated `GitPrunePlan 0.4`; CV1A does not create another branch/PR/Work observer.

## `lock`

`tools/lock.py` is treated as an active legacy implementation, not as a cosmetic alias. Registered components, imports, executable invocations and transitional tests remain visible as consumers.

`LOCK_OWNERSHIP_VIOLATION` is not considered use of the `lock` CLI merely because the token contains the word "LOCK". Error-code retirement is a separate compatibility decision.

## `ops`

The legacy branch namespace is distinct from the repository directory `ops/`.

In workflow YAML:

```yaml
push:
  branches: ['ops/**']  # legacy branch consumer

  paths: ['ops/**']     # repository path filter, not the legacy branch alias
```

CV1A parses branch filters specifically so path filters are never retired by textual substitution.

Keeping `ops` in `branchGrammar.legacyNamespaces` is also distinct from keeping the semantic alias `ops -> operations`: grammar recognition may remain after semantic projection is retired.

## Current role pointers

`docs/kickstarts/roles/*-current.md` files locate the current versioned role contract. They must not copy mutable infrastructure direction from ProjectState.

This closes the known failure mode where an already-stale pointer stops matching the current ProjectState value and therefore disappears from value-based freshness discovery.

## Trigger inventory

The inspection records branch trigger patterns and classifies legacy namespace triggers without automatically retiring them. `renderer/**` and `architecture/**` are therefore visible adjacent residues, but CV1A does not assume that they share the same death condition as `ops/**`.

## Runtime limitations

The inspection proves coverage over:

```text
tracked repository consumers
+ live branch/PR/Work evidence represented by GitPrunePlan
+ declared current operational contracts
```

It cannot prove the absence of an undocumented external script on an arbitrary operator machine. Later retirement still requires a compatibility migration path, not an assertion of global omniscience.

## Authority boundaries

`ConvergenceInspection 0.1` is:

```text
readOnly = true
semanticAuthority = false
authorizesMutation = false
```

It does not mutate Coordination, change Work, retire aliases, change writer topology, change ProjectState, or authorize M12.

CV1B owns migration to a canonical Coordination surface. CV1C owns retirement only after coverage is rebuilt over the migrated state.
