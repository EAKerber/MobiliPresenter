# M13 residual branch classification — 2026-09-09

Status: **observational consolidation; no branch deletion authorized by this document**.

This note classifies the non-control branches that remained after the M13 operational work. Classification uses current Git ancestry, open-PR/lease state, explicit PR disposition where available, and publication references. Branch names alone are not retention or deletion evidence.

Observation baseline:

- `main`: `0988bf6ac97c89ed8e7e43a923928d088b457cb4`
- no open pull requests at the start of this inspection;
- Coordination had `intents=[]` and `leases=[]` before the consolidation lease was acquired;
- `archive/cold`, `coordination/leases`, `coordination/continuations`, and `main` are control/history authorities and are outside this cleanup set.

## Classification

| Branch | Observed relation to `main` | Disposition | Reason |
| --- | --- | --- | --- |
| `work/operations/m13-bounded-write-canary-v2-20260906` | diverged; 1 branch-only commit | `HISTORICAL_EVIDENCE / ARCHIVE_REVIEW` | No open PR; bounded canary history is not a delivery candidate. Preserve until cold-archive/prune evidence can prove safe ref removal. |
| `work/operations/m13-close-delta-diagnostic` | diverged; 4 branch-only commits | `HISTORICAL_EVIDENCE / ARCHIVE_REVIEW` | Diagnostic history, not current work. Do not merge into `main` merely to eliminate the branch. |
| `work/operations/m13-close-delta-diagnostic-cas-check` | diverged; 3 branch-only commits | `HISTORICAL_EVIDENCE / ARCHIVE_REVIEW` | CAS diagnostic history. Preserve until archived/proven removable. |
| `work/operations/m13-close-delta-diagnostic-pr-sentinel` | diverged; 5 branch-only commits | `HISTORICAL_EVIDENCE / ARCHIVE_REVIEW` | Sentinel history is evidence, not product work. |
| `work/operations/m13-close-delta-diagnostic-pr-sentinel-2` | same head as `m13-close-delta-diagnostic`; 4 branch-only commits relative to `main` | `HISTORICAL_EVIDENCE / ARCHIVE_REVIEW` | Duplicate ref identity does not itself authorize deletion; let canonical prune/cold-archive evidence decide. |
| `work/operations/m13-close-delta-diagnostic-pr-sentinel-3` | same head as `m13-close-delta-diagnostic`; 4 branch-only commits relative to `main` | `HISTORICAL_EVIDENCE / ARCHIVE_REVIEW` | Same rule as sentinel-2. |
| `work/operations/m13-close-delta-reobservation` | diverged; 2 branch-only commits | `HISTORICAL_EVIDENCE / ARCHIVE_REVIEW` | Reobservation experiment is complete historical evidence, not a merge target. |
| `work/operations/m13-finalize-reflection-quiescence` | diverged; 1 branch-only commit | `HISTORICAL_EVIDENCE / ARCHIVE_REVIEW` | Finalization evidence should be archived/proven before ref removal. |
| `work/operations/m13-rq2-bounded-write-canary` | diverged; 1 branch-only commit | `HISTORICAL_EVIDENCE / ARCHIVE_REVIEW` | Canary evidence should not be merged solely for branch hygiene. |
| `work/ui/environment-realism-v0.1-r2` | diverged; 14 branch-only commits | `PRESERVE_DORMANT_EXPERIMENT` | PR #216 was closed unmerged with an explicit reversible disposition requiring this branch to be preserved until the experiment is reconciled onto the current published line. |
| `work/ui/netlify-guided-configurator-current` | ancestor of `main`; 0 branch-only commits | `PRESERVE_PUBLICATION_ANCHOR` | `ops/published/viewer-next-current.json` still names this exact branch and `6eb95a4d71c4ae38d125b488e4cc7fae42727741` as the published source anchor. |

## Consequences

1. **No residual branch should be merged merely to make the branch list clean.** The M13 branches contain historical experimental/diagnostic commits, not pending delivery candidates.
2. **No UI branch in this set should be deleted now.** One is an explicitly preserved dormant experiment; the other is the current publication anchor.
3. **M13 ref cleanup should reuse the canonical cold-archive/prune path.** Once historical heads have objective archive evidence and no protection/authority/work rule applies, the prune planner may classify them independently. This note is not delete authorization.
4. **Branch hygiene and delivery are separate.** Archiving/removing historical experiment refs must not be modeled as accepting their commits into `main`.

This classification can be retired once the M13 historical refs are either canonically archived/pruned or explicitly promoted back to active work, and the publication anchor no longer references `work/ui/netlify-guided-configurator-current`.
