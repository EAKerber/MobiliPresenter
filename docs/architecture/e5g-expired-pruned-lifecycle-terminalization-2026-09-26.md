# E5g — expired/pruned write-lifecycle terminality

A write binding can outlive its canonical lease row: after `expiresAt`, Coordination may compact the expired lease while the Hosted Agent Cycle still retains the last `ACTIVE` lifecycle binding in durable issue-bus history.

This state is not active authority and must not be reacquired inside the same cycle. It is also not equivalent to an expired lease that is still materialized and needs cleanup.

The derived terminality rule is deliberately narrow:

- exact expired lease still materialized on the Work branch → `EXPIRED`, cleanup remains required;
- no lease at all remains for the Work branch → `RELEASED`, read-only derived terminality;
- any residual or replacement lease remains on the Work branch → `UNKNOWN`, fail closed.

The derivation creates no Coordination mutation, no lifecycle result, no semantic authority, and no mutation authority. It only lets turnover and close agree that a chronologically expired binding whose authority has already disappeared canonically is terminal.

This preserves the stronger negative gates: unexpired missing bindings remain unknown, materialized expired records still require canonical release, and conflicting branch authority never becomes implicit success.
