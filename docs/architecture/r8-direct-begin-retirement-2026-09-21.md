# R8 direct Agent Cycle begin retirement — 2026-09-21

Status: **candidate subtraction after R7 default-entry promotion and R8 journey-shadow retirement**.

## Purpose

R7 stopped advertising direct `agent.py begin` as the normal entry path, but the stable public CLI still accepted it and bootstrap projections still exposed a `legacyDirectBegin` recovery hint. That leaves two entry surfaces cognitively visible after semantic Work-bound `journey-entry` became the default.

This slice removes that residual public surface without replacing the Agent Cycle engine or its recovery carrier.

## Subtraction

- remove `begin` from the stable `tools/agent_commands` CLI parser and toolbox inventory;
- remove `legacyDirectBegin` from the public bootstrap projection;
- stop accepting runtime ToolSurface binding for direct `agent.py begin`;
- update permanent bootstrap/role/README guidance so recovery is described as an internal Hosted Agent Cycle concern rather than a public façade command.

The canonical Hosted Agent Cycle implementation and workflow remain unchanged. Internal/recovery code may still call the underlying begin primitive where explicitly required.

## Safety

No authority, lifecycle, provider bridge, workflow, state, compatibility layer or replacement command is added. `journey-entry` remains the normal Work-bound entry surface. UNKNOWN/BLOCKED semantics, Work binding, Agent Cycle identity and provider injection are unchanged.

## Promotion evidence

Exact-head Agent Ops, Coordination Guard and Supervisor Snapshot must PASS. Regression coverage must prove:

- `begin` is absent from the public toolbox inventory;
- the public agent CLI rejects `begin`;
- runtime ToolSurface binding rejects direct begin;
- bootstrap projections no longer expose `legacyDirectBegin`;
- manager/bootstrap guidance points only to semantic paved entry for normal operation.

## Accounting

Public normal-path surfaces: -1 direct command and -1 legacy bootstrap projection field.
New public API: 0.
Replacement runtime modules: 0.

## Next R8 inventory

After this subtraction, inspect duplicated hosted-bus I/O and CLI-coupled defaults. Consolidation is justified only when at least two concrete duplicated clients are reduced in the same slice.
