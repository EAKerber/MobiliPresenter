# E5 — Governed mutation request client

Status: **candidate caller-side ergonomics layer over E4**.

## Purpose

The E4 counter reduced the semantic request to four caller inputs, but callers still had to know the service schema and bus marker. E5 removes that transport knowledge.

The client accepts only:

- Work ID;
- branch;
- changes;
- commit message.

It canonicalizes change ordering, delegates validation to the existing GovernedMutationServiceRequest 0.1 validator, and renders the exact existing bus comment.

## Boundary

The client does not:

- post the comment;
- observe or mutate Work;
- create/resume an Agent Cycle;
- acquire/renew/release a lease;
- resolve Agent Tools;
- execute Git;
- create a second request schema.

It is a renderer, not a new authority or execution path.

## CLI

`python tools/governed_mutation_client.py --work-id <id> --branch <branch> --changes-file <json> --message <message>`

prints the exact `MOBILIPRESENTER_GOVERNED_MUTATION_REQUEST_V0_1` comment body.

`--json` prints the canonical existing E4 request instead.

## Kitchen-window principle

The caller does not need cycle, lifecycle, lease, proof, receipt or Git object identities to order the mutation. Those remain behind the counter and are available through E4 kitchen windows after execution.

## Operational qualification

Code/CI qualification is independent of carrier availability. A first live positive E4 PASS remains a separate promotion gate because the GitHub connector available to this chat currently refuses creation of the bus command comment before GitHub receives it. No workflow or alternate authority path is added to bypass that external ToolSurface restriction.
