# R6k — Coordination non-interference at Agent Cycle close

Status: implementation candidate discovered by the live R6 black-box canary after R6j.

## Trigger

The post-R6j historical close retry still returned `UNKNOWN / UNATTRIBUTED_DURABLE_DELTA`. The remaining uncovered source-head movement was `coordination/leases`: helper Works advanced Coordination while the long-lived R6 canary cycle remained open.

R6i already proves non-interfering movement in `main` and `coordination/continuations`. R6k extends that same read-only evidence contract to Coordination rather than adding another lifecycle or authority.

## Contract

`AgentCycleNonInterferenceReadback 0.2` may cover a `coordination` source-head change only when:

- the live `coordination/leases` head still equals the close after-head;
- the before→after history is linear/ahead;
- every Coordination state from the before head through every compared commit can be read;
- the projection of `intents` and `leases` mentioning the bound Work branch is empty at every observed state;
- the bound Work remains unchanged and the existing continuation/main non-interference proofs also pass.

If the bound branch appears in any intermediate Coordination state, the proof fails closed and the close remains UNKNOWN.

## Compatibility

The validator continues to admit historical `AgentCycleNonInterferenceReadback 0.1` evidence. New evidence is emitted as 0.2 with an explicit nullable `coordinationReadback`.

No authority, lease type, workflow, mutation permission, replay path, state machine, or second close lifecycle is introduced.

## Retirement criterion

Like R6i/R6j, this remains an R8 retirement candidate if the completed migration shows that long-lived Work-bound cycles are not a recurring operational shape. If independent Works repeatedly experience benign Coordination drift, it is evidence that non-interference attribution belongs to the stable close capability.
