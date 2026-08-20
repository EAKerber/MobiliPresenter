# GitMutationBundle 0.1 — atomic multi-path Git mutation

## Status

Canonical read-only mutation materialization contract for Manager/GitOps. It does **not** authorize a write and does not replace `GitMutationPlan 0.1`.

## Problem

A multi-file change can be semantically correct while transport materialization maps a path to the wrong blob or publishes a branch before the candidate is complete. File-at-a-time Contents API writes also create avoidable intermediate commits and repeated readbacks.

`GitMutationBundle 0.1` binds the intended multi-path change before publication:

```text
observed head/tree
  -> bundle(path + contentSha256 + gitBlobSha + size)
  -> validate concrete content
  -> create candidate tree
  -> compare base/candidate trees
  -> GitMutationTreeProof 0.1
  -> create commit(parent = observed head)
  -> create/update ref without force
  -> aggregate readback
```

The bundle is evidence/intent, never authority: `authorizesMutation=false` and `force=false` are invariant.

## Capability boundary

The logical capability remains `git.direct-mutation`. Atomic tree materialization is a stronger execution profile, not a new capability identifier.

A provider used for this profile must prove the required features declared by `ATOMIC_PROFILE_REQUIRED_FEATURES` in `tools/git_mutation_bundle.py`. Provider identity is irrelevant; only observed PASS + feature coverage matter.

The profile is additive to the ordinary direct-mutation gate. It does not weaken CAS, expected-head, non-force or readback requirements.

## Bundle invariants

Each entry is canonical and path-unique. Writes bind:

- repository path;
- UTF-8 content SHA-256;
- Git blob SHA;
- UTF-8 byte size.

Deletes are explicit and carry no content/blob metadata. `expectedChangedPaths` must equal the sorted entry paths exactly.

The bundle also binds:

- repository;
- target branch;
- observed base commit;
- observed base tree;
- target-ref precondition (`absent` or `head == baseHead`);
- non-force policy;
- stable `bundleHash`.

A rehashed semantic drift remains invalid because validation reconstructs the canonical relationships instead of trusting the hash alone.

## Pre-commit tree proof

A provider may create a candidate tree using inline content or another equivalent mechanism. Before commit creation, the base and candidate trees are read back recursively and projected to blob paths.

`verify_tree` requires:

1. the exact changed path set to equal `expectedChangedPaths`;
2. every write path to resolve to its declared Git blob SHA;
3. every delete path to be absent;
4. no extra changed blob path.

Only a passing `GitMutationTreeProof 0.1` may proceed to commit creation.

## Publication and readback

Commit creation binds `parent = baseHead` and `tree = candidateTreeSha` from the tree proof. Publication uses either:

- create ref at the complete candidate commit when the target ref was absent; or
- non-force ref advancement when the target ref was observed at `baseHead`.

Aggregate readback then proves:

- branch head == candidate commit;
- commit parent == bundle base head;
- commit tree == the pre-commit tree proof candidate tree;
- changed paths == bundle allowlist;
- every written path has the expected content SHA-256.

The resulting `GitMutationBundleReadback 0.1` is a derived proof, not an authority.

## Relationship to GitMutationPlan

`GitMutationPlan 0.1` remains the operation-level read-only planner for branch, file, PR, merge and ref actions. `GitMutationBundle 0.1` specializes multi-path content materialization. Neither contract grants authorization by itself.

## Fail-closed rules

Do not continue when any of these is unknown or mismatched:

- base head/tree;
- target-ref precondition;
- provider profile;
- materialized content hash/blob mapping;
- tree readback;
- commit parent/tree;
- non-force ref publication;
- aggregate content/ref readback.

Do not fall back silently to sequential Contents API writes after an atomic bundle has been selected.
