# E5d — Hosted Agent Cycle failure recovery certificate

Status: candidate bounded re-entry recovery.

## Problem

A historical Hosted Agent Cycle close may be terminally BLOCKED by a write
lifecycle UNKNOWN even after a later canonical cleanup has removed all residual
write authority.

Because close executes the exact begin semantic host, a newer close rule cannot
retroactively change that historical result. Replaying the old close under new
code would violate semantic-host binding.

## Recovery certificate

E5d adds a current-carrier, read-only recovery surface.

It downloads and binds the exact begin artifact, validates the exact historical
close request and failure, then runs the current write-lifecycle close guard
against the same historical window and current Coordination readback.

A certificate is emitted only when the current guard proves lifecycle state
RELEASED with no blockers and the exact close failure contains both
write-lifecycle UNKNOWN close causes.

The certificate binds cycle instance, handle hash, begin comment, close command
hash, failed close failure hash, lifecycle report hash, and current authority
head.

## Meaning

RECOVERED does not mean the historical close passed. It means the historical
failure has been reconciled sufficiently to prove that the cycle carries no
residual write authority and may leave the active re-entry frontier.

The original failure remains on the bus and remains inspectable.

## Re-entry

hosted_cycle_reentry recognizes a valid later recovery certificate bound to a
single close failure. hosted_cycle_frontier treats PASS and RECOVERED as
terminal states. Without a valid certificate, RECONCILE_FAILURE is unchanged.

Conflicting recovery certificates fail closed as ambiguous.

## Boundary

The recovery workflow has repository contents read only, Actions artifact read,
and issue-comment write only for the certificate. It cannot mutate Work,
Coordination, Git, leases, or Delivery.

New authority: 0. New persistent state: 0. Historical result rewrite: 0.
