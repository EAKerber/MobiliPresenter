# Capability Gates 0.1

## Purpose

Experimental operational capabilities must not remain experimental only because no agent returns to validate them.
This increment keeps the model deliberately small: unresolved **Gates**, Gates selected for the **next formal review**, and a counter for consecutive formal reviews with no active Gates.

This mechanism is GitOps governance. It does not schedule workers and it does not automatically promote policy.

## Minimal state

Each file under `ops/capabilities/<id>.json` contains:

- `policy`: current usage policy;
- `gates.backlog`: unresolved Gates only;
- `gates.next`: backlog Gate ids that the responsible agent should exercise on its next formal review;
- `roundsWithoutActiveGates`: consecutive formal reviews that ended with `gates.next` empty;
- `maxRoundsWithoutActiveGates`: point at which continued emptiness requires a stronger review;
- `deferReason`: the currently observed reason for leaving `gates.next` empty, or `null`.

A Gate contains only an id and the claim/test that still needs to be resolved. Passed Gates leave the backlog; Git, PRs and CI remain the evidence/history authorities instead of turning the capability file into an evidence ledger.

`gates.next: []` is valid and intentional.

## Formal review round

A round is counted only when the responsible GitOps agent formally reviews that capability. Unrelated development work, chats or scheduler wake-ups do not increment it by themselves.

At each formal review:

1. if `gates.next` is non-empty, exercise/evaluate those Gates;
2. if `gates.next` is empty, investigate whether the current reason for deferral is still valid;
3. if the reason is no longer valid, select or add one or more backlog Gates for the next round and reset the empty-round counter;
4. if the reason remains valid, `gates.next` may remain empty and the empty-round counter advances;
5. when the configured maximum is reached, the maximum and the deferral reason must be deliberately reviewed rather than extended mechanically.

Competing work, a busy backlog or "doing something else first" is not sufficient on its own to extend the maximum. A valid continued deferral should identify a concrete external, safety, dependency or representativeness reason.

If there is no meaningful unresolved Gate and no valid reason to defer, the responsible authority should review whether the capability should leave experimental policy. Promotion remains explicit and is never performed by this tool.

## Read-only tool

The first increment is intentionally read-only:

```bash
python3 tools/capability_gates.py list --json
python3 tools/capability_gates.py review-plan coordination-leases --json
```

`review-plan` produces one of four simple actions:

- `TEST_NEXT_GATES`
- `REVIEW_EMPTY_ROUND`
- `REVIEW_EMPTY_LIMIT`
- `NO_EXPERIMENTAL_REVIEW`

It also emits a stable `planHash`.

No `--apply` exists in Capability Gates 0.1. Write support should be added only after this model has survived real review rounds.

## Pilot: Coordination Leases

Coordination Leases is the first pilot because current CI evidence has already satisfied several gates that its PR description previously treated as pending. The unresolved backlog is deliberately reduced to the two concrete items still observed at the start of this increment:

- formal rollback exercise;
- official CLI surface decision/validation.

Those two Gates are active for the next responsible review. The file does not copy the already-passed CI evidence because that evidence remains authoritative in GitHub/CI.

## Future integration

After real pilot rounds, the standalone read-only surface can be routed through `tools/agent.py` (for example `agent.py capabilities` / `capability review-plan`) and later surfaced by `maintenance inspect`.

The scheduler/Agent Bus may wake GitOps for a review, but it must not own promotion decisions.
