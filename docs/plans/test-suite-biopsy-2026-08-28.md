# MobiliPresenter — Test Suite Biopsy — 2026-08-28

Status: audit / planning only  
Repository: `EAKerber/MobiliPresenter`  
Base: `main@038d1ccc03df17c93600cb06c3c44b874d7e9b70`  
ProjectState mutation: none  
Test deletion in this slice: none

## 1. Question

The suite has grown to roughly seven hundred tests. The useful question is not
whether that number is intrinsically high. The useful question is whether each
remaining proof still protects one of:

1. a distinct invariant;
2. a distinct trust boundary;
3. a real compatibility obligation;
4. a failure/replay/concurrency mode that is not implied by another proof; or
5. an operational governance contract that is intentionally part of the
   repository product.

A passing test is not automatically a valid test.

Conversely, two tests that look similar are not automatically redundant if they
sit on different trust boundaries.

This biopsy therefore uses semantic validity rather than raw test count as the
primary optimization target.

---

## 2. Observed baseline

The exact-head Agent Ops run used to qualify R3B0b executed:

```text
Ran 725 tests in 5.898s
OK
```

This is important: the current test count is **not a material runtime problem**.
The suite is fast enough that deleting tests merely to shorten CI would create
very little value.

The cost that is already visible is different:

- historical tests can silently change meaning as version aliases move;
- characterization tests can turn a temporary absence into a permanent
  regression contract;
- source-text tests can freeze implementation spelling rather than behavior;
- repeated fixtures obscure whether two tests actually prove different things;
- post-cutover absence tests can survive after the useful migration boundary is
  already protected elsewhere.

The target is therefore **proof quality and lifecycle**, not an arbitrary lower
number.

---

## 3. Classification vocabulary

### KEEP

Protects a distinct invariant, trust boundary, compatibility contract, or
failure mode. Refactoring fixtures is allowed, but the proof should survive.

### CONSOLIDATE

The intent is valid, but part of the proof is duplicated at a lower or higher
layer. Prefer one kernel proof plus one boundary/integration proof rather than
repeating the same exact assertion everywhere.

### REWRITE

The intended protection is valid but the current mechanism is weak, synthetic,
or coupled to implementation details.

### DELETE-CANDIDATE

No distinct externally meaningful contract is currently identified. Deletion
still requires a consumer/overlap check in the cleanup PR.

### TRANSITIONAL-MISSING-DEATH-CONDITION

The test deliberately freezes a current limitation or migration state. It is
valid only until a known later slice changes that limitation. It should use the
repository test-lifecycle mechanism or another explicit retirement condition,
not live indefinitely as an ordinary regression test.

---

## 4. Main diagnosis

### 4.1 The suite is not broadly invalid

The audit found substantial legitimate density around boundaries that are easy
to break while refactoring:

- expected-head / CAS / non-force mutation;
- post-write ambiguity and replay fences;
- carrier vs semantic authority;
- Work vs ProjectState execution ownership;
- schema vs semantic validator parity;
- exact writer topology;
- provider observation vs capability satisfaction;
- trace membership vs receipt validity;
- lease identity vs lifecycle disposition;
- artifact availability vs domain state.

These tests often appear repetitive by name because the same domain fact is
revalidated at multiple boundaries. That is allowed and useful when the
**definition remains singular**.

### 4.2 The primary debt is lifecycle governance

The strongest recurring problem is not duplicate assertions. It is tests that
were created as temporary characterization and never received an explicit death
condition.

The repository already has a better pattern in `tools/test_lifecycle.py` and in
`test_project_state_retention_transition.py`: a transitional suite has an owner,
a reason and an executable retirement condition.

That pattern should become the default for tests whose proposition is of the
form:

```text
"the system does not support X yet"
```

or:

```text
"the old surface is still absent after cutover Y"
```

rather than for permanent invariants such as:

```text
"a non-force ref update must remain non-force"
```

---

## 5. High-confidence findings

### 5.1 `test_agent_cycle_r0_characterization.py`

Verdict: **SPLIT: KEEP + TRANSITIONAL-MISSING-DEATH-CONDITION + CONSOLIDATE**

This file currently mixes three different species of proof.

#### Keep as permanent invariants

- governed mutation context may be context-ready while execution/tool readiness
  remains conditional;
- context `cycleId` is distinct from concrete Hosted cycle-instance identity;
- interleaved records from another cycle must not contaminate the current cycle;
- Hosted begin failure must preserve the root blocker;
- historical Hosted V0.1 begin has no Work binding.

Some of these can later move beside the canonical kernel that now owns the
invariant, but the semantic proof remains valuable.

#### Transitional, not permanent

- close requirements are static across intents;
- a result after the close comment is outside the active trace window;
- stabilization cannot see a result beyond the current close boundary;
- Hosted carrier concurrency is partitioned by carrier;
- mutation dispatch has no sequence/dependency contract;
- current connector vocabulary cannot express the atomic bundle profile;
- direct-mutation PASS does not imply the future atomic bundle profile.

These statements describe current limitations that R4, R5 or R3C are expected
to change. If left as ordinary tests, future correct implementation will look
like regression.

Action:

1. split permanent characterization from transitional characterization;
2. attach explicit retirement targets/conditions to the latter;
3. as R4/R5 land, delete the old absence assertion in the same slice that adds
   the positive replacement proof.

### 5.2 `test_agent_cycle_readiness.py`

Verdict: **REWRITE historical fixtures; KEEP semantic intent**

R3B0b exposed a concrete flaw: historical Context 0.1/0.2 tests followed a
moving `PREVIOUS_SCHEMA_VERSION` alias. Advancing the current producer changed
what the old test meant.

The immediate repair pins 0.1/0.2/0.3 by literal version string and exact outer
field delta. This is better, but the fixture is still synthesized from the
current producer and current nested artifacts.

Target state:

```text
literal historical artifact emitted by version N
-> validate with current reader
-> no reconstruction from current producer
```

Prefer checked-in minimal historical JSON fixtures or another literal captured
representation. Do not make the current producer manufacture its own history.

### 5.3 `test_agent_cycle_identity_r2a.py`

Verdict: **KEEP**

Distinct proofs include:

- context fingerprint vs concrete instance identity;
- source/actor/context participation in instance identity;
- exact Hosted manifest binding;
- handle integrity without authority promotion;
- forged/rehashed handle still failing authoritative binding;
- historical artifact without handle remaining readable.

These are not replaced by public handle schema tests.

### 5.4 `test_agent_cycle_handle_public_r2b1.py`

Verdict: **KEEP**

Owns public structural/semantic parity and OperationalSemantics registration.
This is a different trust boundary from identity-kernel tests.

### 5.5 `test_hosted_cycle_handle_r2b1.py`

Verdict: **KEEP; fixture consolidation allowed**

Owns Hosted resume-token/provenance binding and exact legacy derivation. It
should not be collapsed into the public handle-schema suite.

### 5.6 `test_hosted_cycle_records_r3b0a.py`

Verdict: **KEEP**

These tests protect the R3B0a single-definition boundary:

- STRONG vs AMBIENT binding;
- explicit instance mismatch never falling back to actor;
- malformed unrelated record ignored;
- malformed record claiming current cycle failing closed;
- V0.1/V0.2 carrier normalization equivalence.

The R3B0a implementation itself showed their value: trace membership and receipt
validity are distinct responsibilities.

---

## 6. Hosted / carrier cluster

### `test_hosted_agent_cycle.py`

Verdict: **KEEP**

Owns closed command parsing, owner-only issue transport, begin/close shape,
canonical begin delegation, manifest binding, failure-core projection and
remote evidence normalization.

### `test_hosted_agent_cycle_close_regression.py`

Verdict: **KEEP for now**

Although small, its tests cover regression boundaries not fully implied by the
main carrier suite:

- unexpected close exception must materialize a structured failure rather than
  promote exception text to semantics;
- close validation is tied to exact begin context and the same evidence;
- valid closure blockers must survive a non-zero wrapper result root-to-wrapper.

Reconsider only if those exact scenarios are promoted into the main carrier
suite with one-to-one proof evidence.

### `test_hosted_cycle_artifact_r2c1.py`

Verdict: **KEEP**

Artifact-provider observation is a separate trust boundary from cycle semantics.
The suite distinguishes AVAILABLE, EXPIRED, UNKNOWN, ambiguous/missing and
head-mismatch states without making local time or carrier state into authority.

---

## 7. Agent Tool cluster

Inspected surfaces include:

- `test_agent_tool_admission.py`
- `test_agent_tool_dispatch_intent.py`
- `test_agent_tool_guard_proofs.py`
- `test_agent_tool_semantic_contracts.py`
- `test_agent_tools.py`
- `test_agent_tool_effective_mode_callers.py`

Overall verdict: **KEEP suites; CONSOLIDATE repeated kernel assertions; REWRITE
one source-text test**.

### Valid layering

A useful pattern is:

```text
kernel proof
+ one resolver/admission integration proof
+ one dispatch/host enforcement proof
```

The integration proof should not need to repeat every exact member of the guard
proof set already exhaustively tested by the kernel.

### `test_agent_tool_effective_mode_callers.py`

Verdict: **REWRITE**

The intent is excellent: production callers must use the canonical
`resolve_effective_mode` definition and must not independently reconstruct
policy.

The current mechanism scans Python source text for function names. That can fail
on harmless renames or pass despite an equivalent duplicated implementation.

Replace with an architectural/behavioral proof, for example by instrumenting or
patching the canonical resolver at the boundary and proving the production
caller delegates to it with declared intent.

---

## 8. Write lifecycle cluster

Inspected:

- `test_agent_write_lifecycle.py`
- `test_agent_write_lifecycle_close_evidence.py`
- `test_agent_write_lifecycle_host.py`
- `test_agent_write_lifecycle_workflow_entrypoint.py`

Verdict: **KEEP; consolidate fixtures only**

These files cover different trust boundaries:

1. lifecycle identity/binding and ACTIVE/RELEASED/EXPIRED/UNKNOWN semantics;
2. evidence discovery and close stabilization;
3. dispatch-host replay ambiguity and precondition revalidation;
4. actual package/module workflow entrypoint.

In particular, tests around "prior attempt may have written" and post-mutable
failure must remain. They are safety properties, not test noise.

A shared fixture/builder module may reduce cognitive duplication, but should not
become a new semantic layer.

---

## 9. Coordination remote cluster

Inspected:

- `test_coordination_remote.py`
- `test_coordination_remote_timeout.py`
- `test_coordination_remote_transient.py`

Verdict: **KEEP; fixture consolidation only**

They cover different operational failures:

- ordinary canonical writer / CAS / ancestry / readback;
- process timeout / stalled `gh api`;
- ambiguous 503/504 and deterministic retry after a possibly-applied write.

Do not merge these simply because all use a scripted transport.

A shared `ScriptedTransport` test helper is reasonable if it reduces boilerplate
without hiding scenario state.

---

## 10. Semantic layer

Inspected:

- `test_semantic_core.py`
- `test_semantic_actions.py`
- `test_semantic_work.py`
- `test_semantic_contracts.py`
- `test_semantic_coverage.py`
- `test_semantic_foundations.py`
- `test_semantic_registry.py`
- `test_semantic_topology.py`

Overall verdict: **mostly KEEP**.

The apparent repetition comes from different semantic layers:

- core typed identity / closed vocabularies;
- contract/schema conformance;
- live inventory coverage;
- declarative foundation invariants;
- concept/owner/alias registry integrity;
- authority/writer/delegation topology.

`test_semantic_topology.py` is especially high-value because it guards the
repository's Single Writer / Single Definition architecture. Source inspection
is appropriate there only when the property being tested is genuinely static
architecture rather than incidental spelling.

### Small vocabulary tests

`test_semantic_actions.py` and `test_semantic_work.py` each contain very small
closed-enum tests. They are semantically valid. They may be consolidated into a
single vocabulary suite for file-count/readability reasons, but doing so would
not materially change the test count or risk profile.

Do not delete them just because they are small.

---

## 11. ProjectState cluster

Inspected:

- `test_project_state.py`
- `test_project_state_transition.py`
- `test_project_state_retention_transition.py`
- `test_project_state_consumer_boundaries.py`

### Kernel / transition tests

Verdict: **KEEP**

Schema/current-contract, deterministic plan, apply/rebuild, rollback and
retention-only shrink are distinct responsibilities.

### Retention transitional suite

Verdict: **KEEP as reference pattern**

This is the model for temporary tests: explicit owner, reason and executable
retirement condition via `transitional_suite`.

### Consumer boundaries

Verdict: **KEEP architectural AST barrier; CONSOLIDATE post-cutover absence
assertions**

High-value permanent proof:

- operational Python/workflows must not reintroduce ProjectState execution
  ownership;
- Work execution fields must remain distinguishable from retired ProjectState
  fields.

Lower-value long-lived proofs after cutover:

- exact old migration files do not exist;
- exact old schema filenames do not exist;
- exact removed compatibility symbol list remains absent forever.

These are useful during and immediately after migration, but should eventually
collapse into a smaller "no retired ProjectState execution surface" boundary or
be lifecycle-managed.

---

## 12. Meta/governance tests are real tests, but a different category

Examples:

- `test_roadmap_freshness.py`
- `test_routine_coverage.py`
- `test_test_lifecycle.py`
- `test_workflow_boundaries.py`
- `test_integration_reconcile_ops_ci.py`

These inflate the raw count relative to a conventional application unit-test
suite, but they intentionally make repository operations part of the product.

Verdict: **KEEP category, audit individual source-scan assertions**.

`test_test_lifecycle.py` is particularly important because it makes transitional
test retirement executable rather than documentary.

`test_roadmap_freshness.py` protects consumer-update accountability during real
ProjectState transitions.

`test_routine_coverage.py` mixes runtime-catalog assertions with workflow/source
boundaries. The latter are valid architectural checks, but should be reviewed
when the routine pipeline changes rather than treated as domain-unit tests.

---

## 13. Concrete DELETE / CONSOLIDATE candidates

These are candidates, not deletions authorized by this biopsy.

### High-confidence delete or replacement candidate

`test_agent_prune_facade.py::test_removed_generic_prune_command_is_not_required`

It freezes the absence of a removed private symbol rather than proving the
positive external contract. The adjacent positive facade test already proves
that `agent git prune-plan` delegates to the canonical generator.

Before deletion, verify no separate consumer relies on the negative symbol
boundary.

### Consolidate / lifecycle-manage candidates

- `test_agent_ops.py::test_legacy_prune_classifier_is_removed`
- `test_project_sensors.py::test_removed_derived_helpers_are_not_present`
- `test_coordination_surface_semantics.py::test_legacy_lock_surface_is_absent`
- `test_supervisor_pipeline.py::test_retired_maintenance_live_has_no_runtime_surface`
- `test_maintenance_inspect.py::test_maintenance_no_longer_has_direct_capability_deathcircle_path`
- `test_workflow_boundaries.py::test_agent_ops_does_not_reintroduce_m11_convergence_pipeline`
- migration-file/schema-absence assertions inside
  `test_project_state_consumer_boundaries.py`.

These may still be valuable as post-cutover guards, but they should not remain
indefinitely as unrelated negative facts. Prefer one positive architecture
boundary plus an explicit transitional retirement condition when the absence is
migration-specific.

---

## 14. False-positive cleanup targets to avoid

The following clusters should **not** be selected for deletion merely because
they look repetitive:

- Coordination CAS / timeout / transient suites;
- Agent Write Lifecycle kernel / close evidence / host suites;
- AgentCycle identity vs public handle vs Hosted handle suites;
- Hosted artifact observation;
- semantic topology writer/authority tests;
- remote canonical post-write/replay tests;
- Work graph execution-identity and dependency tests;
- Git mutation plan vs Git mutation bundle vs execution readback.

They protect different trust boundaries.

---

## 15. Recommended cleanup sequence

### T1 — lifecycle correction, no semantic test loss

1. split `test_agent_cycle_r0_characterization.py` into permanent and
   transitional propositions;
2. attach retirement owner/reason/condition to R4/R5/R3C limitation tests;
3. do the same for clearly migration-specific absence tests that currently have
   no lifecycle;
4. keep the suite count approximately stable during this step.

Success criterion: every test that freezes a temporary limitation has a visible
death condition.

### T2 — historical compatibility made literal

1. capture minimal literal Context 0.1, 0.2 and 0.3 artifacts;
2. make current readers validate those fixtures directly;
3. delete the producer-minus-fields historical synthesis helper;
4. apply the same rule to any other historical compatibility test found during
   the exhaustive pass.

Success criterion: current producer changes cannot silently rewrite history.

### T3 — replace brittle source-text checks

Start with `test_agent_tool_effective_mode_callers.py`.

Classify source inspections into:

```text
architecture scan -> keep if it proves topology/ownership
spelling scan      -> replace with behavioral/delegation proof
migration absence  -> lifecycle-manage or retire
```

Success criterion: harmless refactors do not fail tests unless an architecture
boundary actually changed.

### T4 — consolidate repeated exact assertions and fixtures

1. keep one exhaustive kernel proof;
2. keep one proof per meaningful boundary;
3. remove repeated enumeration of the same lower-level proof from integration
   tests;
4. extract test-only builders where they reduce noise, not semantics.

Success criterion: a failure points clearly to one owner/layer rather than the
same fact failing in many near-identical tests.

### T5 — delete only after consumer-zero evidence

For each DELETE-CANDIDATE:

1. name the positive invariant that survives;
2. identify the remaining test(s) that prove it;
3. verify the deleted test does not own a distinct failure mode;
4. delete in a small PR;
5. observe full-suite result and semantic/OperationalSemantics gates.

No bulk deletion by file count.

---

## 16. Suggested test design rule going forward

Every new test should answer at least one of these questions in its name or
nearby documentation:

```text
Which invariant does this protect?
Which trust boundary does this cross?
Which historical artifact must remain readable?
Which failure/replay state is distinct from the neighboring test?
If this is transitional, what makes it obsolete?
```

A useful compact rule:

```text
useful test
= distinct invariant
  OR distinct trust boundary
  OR real historical compatibility
  OR distinct failure/replay state
```

For transitional tests:

```text
transitional test
= current limitation
+ owner
+ reason
+ executable death condition
```

---

## 17. What the number 725 means

It should not be interpreted as "725 independent product features".

The current suite combines:

- domain/unit semantics;
- transition and canonical writer proofs;
- transport failure simulations;
- historical compatibility;
- schema/registry parity;
- architecture/topology checks;
- workflow entrypoint and permission boundaries;
- repository governance and roadmap freshness.

That makes the raw count naturally larger than a conventional UI/application
unit-test suite.

Because 725 tests currently execute in about six seconds, the value of cleanup
will come from:

- fewer stale contracts;
- clearer ownership;
- less false coupling to implementation;
- less historical self-deception;
- easier interpretation of failures;
- explicit removal when migrations/limitations end.

Not from making the CI counter smaller.

---

## 18. Current conclusion

The current suite is **mostly justified but insufficiently lifecycle-managed**.

The evidence does **not** support a claim that hundreds of tests are obsolete.
It does support a focused refactor of test governance.

Highest-priority problems:

1. R0 temporary characterization without death conditions;
2. synthesized historical AgentCycleContext compatibility;
3. brittle source/spelling checks where behavioral delegation is the real
   invariant;
4. migration/post-cutover absence checks that should be consolidated or
   retired;
5. repeated exact kernel assertions inside otherwise valuable integration
   tests.

The safest next implementation slice is therefore **Test Hygiene T1**:
lifecycle-correct the known temporary tests without deleting semantic coverage.
Only after that should T2/T3/T4 reduce or rewrite tests.

No target test count is proposed. The correct terminal count should be an
outcome of removing redundant proofs and retired obligations, not a quota.
