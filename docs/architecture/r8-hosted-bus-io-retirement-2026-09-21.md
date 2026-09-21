# R8 hosted issue-bus I/O retirement — 2026-09-21

Status: **candidate measurable subtraction after R7 paved-entry promotion and the first two R8 retirements**.

## Purpose

R7 made semantic Work-bound `journey-entry` the normal operational entry. After R8 removed `journey_shadow` and direct public `agent.py begin`, the remaining hosted carriers still repeated GitHub issue-bus framing and comment transport in multiple protocol owners.

This slice removes that repeated carrier plumbing without creating a bus authority, provider manager, dispatcher, workflow, lifecycle, state, or compatibility framework.

## Boundary

`tools/hosted_issue_bus.py` owns only provider-backed issue transport primitives:

- validate the shared GitHub issue-event envelope;
- derive issue/comment identity;
- get one comment;
- list comments with bounded pagination;
- find the unique open bus issue by supplied title;
- post a comment.

It receives the provider explicitly. It does not construct `GhApiTransport`, invoke shell `gh`, know protocol markers/schemas, inspect Work/Agent Cycle/Delivery semantics, authorize mutation, or persist state.

Protocol owners continue to own their markers, schemas, hashes, guards, bindings, and error semantics.

## Concrete retirement

The same carrier behavior was previously implemented independently across Hosted Agent Cycle, Agent Tool, Write Lease, Remote Canonical, Delivery, Journey Entry, ownership, Agent Tool dispatch, and write-lifecycle surfaces.

This candidate removes or demotes:

- direct comment GET/pagination implementations in the migrated clients in favor of one `get_comment` and one `list_comments` carrier primitive;
- the Journey Entry open-bus issue discovery loop in favor of one `find_open_issue` carrier primitive;
- direct comment POST implementations in Journey Entry, Agent Cycle close composition, ownership and Delivery in favor of one `post_comment` primitive;
- the shell-`gh` comment readers in `trace_collect` and Hosted Agent Cycle evidence observation;
- duplicated event framing checks for repository / issue-vs-PR / bus title / OWNER / body across five hosted protocol parsers.

Agent Cycle trace stabilization now requires an injected comment reader rather than selecting a transport path itself.

## Accounting

Compared with `main=287970e1469d9d38ade24ec2d4f34bc6c59ec3a1` before documentation:

- production runtime additions: 479 lines;
- production runtime deletions: 491 lines;
- production runtime net: **-12 lines**;
- new public commands: 0;
- new public APIs: 0;
- new authorities/state/lifecycles/workflows: 0;
- new provider selectors: 0;
- direct shell-`gh` issue-comment readers in the migrated path: 0.

The small negative LOC balance is secondary to the larger structural subtraction: comment transport and common event framing now have one carrier owner instead of being reimplemented by each protocol.

## Qualification

Exact-head Agent Ops, Coordination Guard, and Supervisor Snapshot must PASS with real jobs.

Regression coverage must prove:

- missing provider blocks rather than falling back;
- carrier framing remains protocol-neutral;
- issue discovery, pagination, read and publication are provider-backed;
- migrated clients do not reintroduce direct comment GET/pagination or shell-`gh` readers;
- protocol-specific marker/schema validation remains in the protocol owners.

## Stop condition

Do not extend this helper into generic protocol dispatch or provider selection. If a future consolidation requires importing Agent Cycle, Work, Coordination, Delivery, protocol markers, or semantic policy into `hosted_issue_bus`, stop rather than expand the layer.

After integration, re-inventory CLI-coupled defaults and R6g-R6l recovery-only scaffolding. Open another R8 slice only where deletion/demotion is independently measurable.
