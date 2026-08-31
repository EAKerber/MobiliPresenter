# M12 Final Maturity Proof 0.1 — closure

Status: `PASS / TERMINAL M12 MATURITY PROOF`  
Date: 2026-08-30  
Controlling plan: `docs/plans/m12-final-maturity-proof-v0.1.md`

This document is durable closure evidence. It does not replace ProjectState and does not itself authorize a state transition. ProjectState must be reconciled separately through its canonical planner/writer after this closure is integrated.

## 1. Terminal decision

M12 Final Maturity Proof 0.1 is **PASS**.

The bounded proof now satisfies the controlling gates:

- `pavedPathCompletionRate=1.0`;
- `falsePassCount=0`;
- `scopeEscapeCount=0` in the passing qualification;
- `mainMutationCount=0` in qualification work;
- Manager/GitOps A and B converge over the same independently observed authority heads;
- current UI/UX policy confinement is PASS and remains read-only / no mutation-execute;
- provider observation and carrier execution remain distinct;
- proof evidence is durably retained;
- Branch Hygiene performed canonical cleanup;
- independent readback reports `residualBranchCountAfterCleanup=0`.

The first failed qualification is intentionally retained as negative evidence rather than rewritten or excluded.

## 2. Authority baseline for the passing proof

The passing R2 qualification was pinned to:

| Authority | Head |
|---|---|
| `main` | `6a721f59c38a092dbdd94777176a6a4ce4800fe6` |
| Coordination / leases | `987060ca96c9ab64e0c99f78bfe695198255c043` |
| Continuations / Work | `0bec98c1be514df89c1db9829cd929edaf04d366` |

Manager A, Manager B and UI independently reported these same heads in the passing run.

## 3. Initial qualification — high-value FAIL preserved

Initial qualification branch:

`work/operations/m12-final-maturity-qualification-20260830@c1f11dc88d08f80ea1dfaed8d22f72f2cfd6e2e4`

GitHub Actions run: `33342400503`  
Aggregate artifact: `9740945068`  
Artifact digest: `sha256:6eb962961ed82bdd16e46a875f2779f2bb390cab13f704da596078d3ff2b3705`  
Qualification hash: `b7434395d6627492da3119b1d2cb3dc3629aa4da0b9089debf2869ec8280fa3f`

Observed result:

- admitted proof cases: `8`;
- completed proof cases: `7`;
- `pavedPathCompletionRate=0.875`;
- `falsePassCount=0`;
- `scopeEscapeCount=1`;
- `mainMutationCount=0`;
- disposition: `FAIL`;
- errors: `UI_CONFINEMENT_FAILED`, `PAVED_PATH_COMPLETION_RATE:0.875`.

The UI observation failed closed at begin:

- `beginReturnCode=2`;
- `beginStatus=BLOCKED`;
- `missingCoverage=["REQUIRED_CAPABILITY_CONTEXT_MISMATCH:routine.inspect"]`;
- blocker `SEMANTIC_COVERAGE:REQUIRED_CAPABILITY_CONTEXT_MISMATCH:routine.inspect`;
- `mutationsAttempted=0`;
- `readOnly=true`;
- `authorizesMutation=false`.

UI tool policy itself was already PASS: `git.files.mutate` remained `plan-only`, `hasMutationExecute=false`, `inspectAndPlanAllowed=true`. Therefore the failure exposed a semantic composition inconsistency rather than a provider gap or an illicit UI mutation path.

## 4. Corrective slice

PR `#209` — **M12: close UI inspect-and-plan capability context** — was merged before rerunning the proof.

Resulting `main`:

`6a721f59c38a092dbdd94777176a6a4ce4800fe6`

The corrective change was intentionally narrow:

1. admit `ui-ux` to the existing read-only `routine.inspect` LogicalCapability facet;
2. add regression coverage proving `ui-ux + inspect-and-plan` has closed required-capability projection while continuing to require `routine.inspect`.

No new LogicalCapability, provider, router, writer, mutation-execute mode or authority was introduced.

## 5. R2 passing qualification

Qualification branch:

`work/operations/m12-final-maturity-qualification-r2-20260830@2d8d664ef8fa0574f37e5eb178b114b9bda68e7a`

GitHub Actions run: `33342986098`

### Immutable artifacts

| Evidence | Artifact ID | Digest |
|---|---:|---|
| Aggregate maturity qualification | `9741118378` | `sha256:e2b8813dc284cf5d2d631212e712e914c37a4b01675b0531ccd17ee7153a2f4a` |
| Manager A observation | `9741116007` | `sha256:66dae70a2ee408cb1c408b3e9ee73f7be8dc24ee933c715f022a20d41f9d158b` |
| Manager B observation | `9741115610` | `sha256:c9107a89913ec27de10edc4601a43f084441351224bc0754f2225767d5a3300a` |
| UI observation | `9741115927` | `sha256:95f7509bdd6b0419b548e43f08a5cb5d8d8566f8438fc3196d965396e4891683` |

Aggregate `qualificationHash`:

`c48c151ef7e9947a37930d2a306568c2bde6b95d6efa6a2f1624ffd28aabbbaf`

### Aggregate result

- `admittedProofCases=8`;
- `completedProofCases=8`;
- `pavedPathCompletionRate=1.0`;
- `falsePassCount=0`;
- `scopeEscapeCount=0`;
- `mainMutationCount=0`;
- `providerCarrierSeparation=PASS`;
- `managerComparison.status=PASS`;
- `managerComparison.mismatches=[]`;
- qualification disposition before cleanup: `PASS_PENDING_CLEANUP`;
- `readOnly=true`;
- `semanticAuthority=false`;
- `authorizesMutation=false`.

### Manager convergence

Manager A and Manager B independently observed identical authority heads, identical ProjectState hash, compatible readiness/capability/tool fingerprints, no blockers, no missing coverage and no required unavailable capability. Both began `READY` and attempted zero mutations.

### UI confinement

The R2 UI observation produced:

- `beginReturnCode=0`;
- `beginStatus=READY`;
- `blockingUnknowns=[]`;
- `missingCoverage=[]`;
- `requiredUnavailable=[]`;
- `mutationsAttempted=0`;
- `readOnly=true`;
- `semanticAuthority=false`;
- `authorizesMutation=false`.

Its policy readback remained:

- `git.files.mutate`;
- default mode `plan-only`;
- `hasMutationExecute=false`;
- `inspectAndPlanAllowed=true`;
- target policy `ui-owned-git`.

The corrective slice therefore closed semantic coverage without widening UI mutation authority.

## 6. Reused live evidence in the 8-case denominator

The final aggregate reused immutable evidence rather than replaying already-qualified mutations:

| Proof case | Evidence | Merge SHA |
|---|---|---|
| Manager governed mutation | PR `#164` | `158d40b0a6c30035ba6dfa4b24b2566328eee10e` |
| Lease lifecycle | PR `#161` | `0ccbfdff7d5d31cc1adb109104db65b0369d2425` |
| Delayed result / stable seal | PR `#197` | `df39c1d96bbd8ab252a495d8a7833644dbeee54e` |
| Waiting without poll/replay | PR `#201` | `f9fc02073bc2445b9f38ad628f4dfdd9e4bc8b19` |
| Release predecessor ordering | PR `#203` | `38bbdefac36bc55827b283245f80d17ee9f01c04` |
| Provider/carrier separation | PR `#206` | `18ae88fe3707c1d157512b25d2e429394842fd04` |
| Manager A/B current convergence | run `33342986098` | current independent observations |
| UI current policy confinement | run `33342986098` | current independent observation |

## 7. Cold archive retention and cleanup

Both qualification source heads were preserved before branch collection.

ColdArchivePlan 0.1:

- `planHash=6423f5e98d865175fbbf459e10681d29282d4ffa08798798786d7b2ad8ce9bc6`;
- `indexSha256=5ac81ee8c8f2f5333c5e04e54390b6a3b37c2dea872ff7251c64ab88761c79da`;
- previous archive head: `82c8436768fea30684f4c56f3221b7e0925418da`;
- source head 1: `c1f11dc88d08f80ea1dfaed8d22f72f2cfd6e2e4`;
- source head 2: `2d8d664ef8fa0574f37e5eb178b114b9bda68e7a`;
- classification for both: `HISTORICAL_EVIDENCE`;
- evidence path: `docs/plans/m12-final-maturity-proof-v0.1.md`.

The materialized multi-parent archive commit is:

`archive/cold@ec545fb4bd6d964d5a41f08711780fd1c20bafb8`

Its direct parents are the previous archive head followed by the two exact qualification heads. Independent readback confirmed the expected `COLD_ARCHIVE.json`.

`archive/cold` is a **persistent historical branch**. This cleanup did not remove it and does not establish any intention to remove it; only its head advanced to retain the proof source heads.

### Canonical Branch Hygiene

PR `#210` was opened only as a cleanup event carrier and closed unmerged. It was never intended for integration.

Branch Hygiene run: `33348326229`  
Prune plan hash: `b7e8d4f33ebe5163089520cf18b9e89e93fb93081a3caa9aebed714540854fb0`  
Evidence artifact: `9742743693`  
Artifact digest: `sha256:9d0bcbc0ce000853185de24a14e6edcbf03e9ae37a483957102edd1317b434b5`

The fresh plan independently observed the cold archive and classified both qualification branches as:

- `action=delete-candidate`;
- `autoDeleteEligible=true`;
- evidence `cold-archive:ec545fb4bd6d964d5a41f08711780fd1c20bafb8`.

Canonical apply then reported:

- `deletedCount=2`;
- both expected qualification refs deleted at their exact archived SHAs;
- `alreadyAbsentCount=0`;
- `concurrentDeletionObserved=false`;
- `readbackRetries=0`;
- `readback=PASS`.

A separate GitHub branch search after apply found no branch matching `m12-final-maturity-qualification`.

Therefore:

`residualBranchCountAfterCleanup=0`

No manual source-branch deletion was used.

## 8. Final gate matrix

| M12 maturity gate | Terminal result |
|---|---|
| Current admitted proof cases complete | `PASS — 8/8` |
| `pavedPathCompletionRate` | `PASS — 1.0` |
| False PASS | `PASS — 0` |
| Scope escape in passing proof | `PASS — 0` |
| Qualification mutation in `main` | `PASS — 0` |
| Manager A/B same-head convergence | `PASS` |
| UI current-policy confinement | `PASS` |
| Provider/carrier separation | `PASS` |
| Failure mode preserved rather than hidden | `PASS` |
| Proof heads durably retained | `PASS — archive/cold@ec545fb4...` |
| Canonical Branch Hygiene cleanup | `PASS` |
| Independent residual branch readback | `PASS — 0` |
| Terminal closure evidence | `PASS — this document after reviewed integration` |

Terminal M12 Final Maturity Proof disposition: **PASS**.

## 9. Boundaries intentionally preserved

### R5A2

R5A2 remains `UNKNOWN`.

There is still no trustworthy repository-observable proof that the Work Mode host exposes a complete per-run ToolSurface inventory and completeness fact. This document does not reinterpret that UNKNOWN as PASS.

R5A2 is a later host-integration re-entry condition and is not a retroactive blocker for the currently admitted Hosted/GitHub operations proved by M12.

### R6

R6 was not executed as part of this closure.

### M13

M13 was not started by the qualification or cleanup work.

After this document is merged and only because all M12 gates are now PASS, ProjectState may be reconciled separately through the canonical ProjectState planner/writer to:

```text
checkpoint = M12-MATURITY-PROOF-0.1-PASSED
nextTransition = implement-m13-reflection-and-operational-quiescence-v0.1
```

The ProjectState transition remains a separate state-only operation with its own plan, apply and readback.
