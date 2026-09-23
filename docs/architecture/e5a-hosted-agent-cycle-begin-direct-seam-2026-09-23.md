# E5a — Hosted Agent Cycle begin direct semantic seam

Status: **regression repair required to dogfood the E4 governed mutation counter**.

## Problem

R8 intentionally retired the public tools/agent.py begin facade after Journey Entry became the operational default.

The Hosted Agent Cycle carrier still invoked that retired facade through a subprocess. A fresh Work-bound V0.4 begin therefore failed before an Agent Cycle could be materialized, blocking the first positive E4 dogfood Work.

## Repair

Hosted begin now composes the same canonical begin semantics in-process:

1. validate the Hosted Agent Cycle envelope;
2. resolve the Agent Cycle entry profile;
3. inspect the live ProjectMachine;
4. derive runtime provider observations from the V0.4 ToolSurface inventory;
5. preserve the historical fail-closed provider-source conflict;
6. build the RuntimeCapabilityInspection;
7. call agent_cycle.build_context();
8. continue the existing Work binding, begin manifest, handle and artifact path.

No public agent.py begin command is restored.

## Compatibility

Legacy V0.1/V0.3 begin continues to use local runtime provider observations, matching the previous internal command_begin behavior.

V0.4 preserves the ToolSurface-to-provider translation that existed immediately before R8 retired the public facade.

The existing subprocess helper remains for close. E5a changes begin only.

## Architectural effect

- new authority: 0
- new state/store: 0
- new workflow: 0
- new public command: 0
- begin semantic implementations: 1

## Promotion

Exact-head CI must pass. Then the paused Work e5-governed-mutation-request-client should be resumed through Journey Entry with the caller-observed github-connector-tools surface. A READY hosted begin is the live regression proof.

After that, E5 should acquire the normal write lifecycle and use E4 itself to author the request-client code, producing the first positive governed-mutation counter PASS.
