# R8 hosted issue-bus I/O retirement — 2026-09-21

Status: **candidate measurable subtraction after R7 paved-entry promotion and the first two R8 retirements**.

## Purpose

R7 made semantic Work-bound `journey-entry` the normal operational entry. After R8 removed `journey_shadow` and direct public `agent.py begin`, the remaining hosted carriers still repeated GitHub issue discovery, comment reads/pagination, and comment publication across multiple clients.

This slice removes that repeated carrier I/O without creating a bus authority, provider manager, dispatcher, workflow, lifecycle, state, or compatibility framework.

## Boundary

`tools/hosted_issue_bus.py` owns only provider-backed issue transport primitives:

- get one comment;
- list comments with bounded pagination;
- find the unique open bus issue by supplied title;
- post a comment.

It receives the provider explicitly. It does not construct `GhApiTransport`, invoke shell `gh`, parse protocol markers/schemas, inspect Work/Agent Cycle/Delivery semantics, authorize mutation, or persist state.

Event framing remains with each existing protocol owner. The attempted broader framing consolidation was deliberately rejected because its production accounting did not justify the abstraction.

## Concrete retirement

This candidate removes or demotes:

- direct comment GET/pagination implementations in migrated clients in favor of one `get_comment` and one `list_comments` carrier primitive;
- the Journey Entry open-bus issue discovery loop in favor of one `find_open_issue` carrier primitive;
- direct comment POST implementations in Journey Entry, Agent Cycle close composition, ownership and Delivery in favor of one `post_comment` primitive;
- the shell-`gh` issue-comment reader in `trace_collect`;
- hidden comment-reader selection in Agent Cycle trace/WAITING observation, which now receives the provider explicitly at the hosted workflow edge.

Protocol owners retain repository/event validation, markers, schemas, hashes, guards, bindings, and error semantics.

## Accounting

Compared with `main=287970e1469d9d38ade24ec2d4f34bc6c59ec3a1` before documentation:

- production runtime additions: 356 lines;
- production runtime deletions: 357 lines;
- production runtime net: **-1 line**;
- new public commands: 0;
- new public APIs: 0;
- new authorities/state/lifecycles/workflows: 0;
- new provider selectors below host edges: 0;
- direct shell-`gh` issue-comment readers in the migrated path: 0.

The LOC balance is intentionally only slightly negative. The stronger subtraction is structural: multiple implementations of issue discovery, comment pagination/read, and comment publication are replaced by one narrow carrier owner, while protocol semantics stay decentralized in their existing owners.

## Qualification

Exact-head Agent Ops, Coordination Guard, and Supervisor Snapshot must PASS with real jobs.

Regression coverage must prove:

- missing provider blocks rather than falling back;
- issue discovery, pagination, read and publication are provider-backed;
- migrated clients do not reintroduce direct comment GET/pagination or shell-`gh` readers;
- Agent Cycle WAITING observation receives its provider at the workflow host edge;
- protocol-specific event framing and marker/schema validation remain in protocol owners.

## Stop condition

Do not extend this helper into event/protocol parsing, generic dispatch, or provider selection. If future consolidation requires importing Agent Cycle, Work, Coordination, Delivery, protocol markers, or semantic policy into `hosted_issue_bus`, stop rather than expand the layer.

After integration, re-inventory CLI-coupled defaults and R6g-R6l recovery-only scaffolding. Open another R8 slice only where deletion/demotion is independently measurable.
