# E5c — Reconcile UNKNOWN write-lifecycle cleanup at close

Status: candidate bounded recovery rule.

## Problem

A lifecycle acquire may mutate Coordination and then fail while materializing
its terminal evidence. The lifecycle result is correctly UNKNOWN and must not
be rewritten to PASS.

If a later canonical Coordination release removes exactly the same
branch/owner/session and current Coordination readback is clean, however,
retaining UNKNOWN forever prevents the Agent Cycle from closing even though no
write authority remains.

## Rule

Close-only reconciliation may classify that lifecycle as RELEASED when all are
true:

1. the terminal UNKNOWN belongs to an exact bound write-lifecycle request;
2. that request action is acquire;
3. a later RemoteCanonicalExecutionReceipt PASS releases exactly the request
   branch/resource and expected owner/session;
4. the receipt is hosted on the same canonical bus issue;
5. its transition plan candidate contains no matching owner/resource lease;
6. its transition receipt is verified and matches aggregate readback;
7. current Coordination contains no matching owner/resource lease.

If any condition is absent, close remains UNKNOWN.

## Non-goals

This does not:

- convert the historical acquire result to PASS;
- synthesize a lifecycle binding or receipt;
- permit mutation admission from the UNKNOWN request;
- retry the original acquire;
- hide or delete the UNKNOWN evidence.

The rule exists only to prove that residual write authority has been
canonically neutralized, allowing cycle close/turnover to proceed.

## Architecture effect

New authority: 0.
New mutation path: 0.
New persistent state: 0.
Runtime acquire/release behavior change: 0.
Close classification rule: +1 bounded recovery case.
