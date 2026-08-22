from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone

from tools import coordination, coordination_apply, coordination_transition as transition
from tools import transition_protocol as protocol
from tools.coordination_remote import (
    AppliedTransition,
    AuthorityObservation,
    CoordinationRemoteError,
)

HEAD0 = "1" * 40
HEAD1 = "2" * 40
TREE0 = "3" * 40
NOW = datetime(2026, 8, 22, 22, 0, 0, tzinfo=timezone.utc)
OWNER = {
    "role": "manager-gitops",
    "session": "cv1b-apply",
    "branch": "work/operations/cv1b-test",
    "pr": None,
}
RESOURCE = "file:ops/coordination/cv1b-apply.shared"


class FakeAuthority:
    repository = transition.DEFAULT_REPOSITORY
    authority_branch = transition.DEFAULT_BRANCH
    state_path = transition.DEFAULT_PATH

    def __init__(self, state, *, head=HEAD0, now=NOW):
        self.state = copy.deepcopy(state)
        self.head = head
        self.now = now
        self.mutate_calls = 0
        self.last_expected_revision = None

    def observe(self):
        return AuthorityObservation(
            head_sha=self.head,
            tree_sha=TREE0,
            state=copy.deepcopy(self.state),
            authority_now=self.now,
        )

    def mutate(self, planner, *, message, expected_revision=None):
        self.mutate_calls += 1
        self.last_expected_revision = expected_revision
        if expected_revision != self.head:
            raise CoordinationRemoteError("COORDINATION_EXPECTED_REVISION_MISMATCH")
        candidate, event = planner(copy.deepcopy(self.state), self.now)
        self.state = copy.deepcopy(candidate)
        self.head = HEAD1
        return AppliedTransition(
            before_sha=HEAD0,
            after_sha=HEAD1,
            authority_now=self.now,
            state=copy.deepcopy(candidate),
            event=copy.deepcopy(event),
        )


class CoordinationApplyTests(unittest.TestCase):
    def _plan(self, before):
        return transition.plan_acquire(
            before,
            authority_head=HEAD0,
            authority_now=NOW,
            owner=OWNER,
            resources=[RESOURCE],
            reason="canonical apply",
            transition_id="cv1b-apply",
        )

    def test_expected_plan_is_required_before_mutation(self):
        before = coordination.empty_state(revision=HEAD0)
        plan = self._plan(before)
        authority = FakeAuthority(before)
        with self.assertRaisesRegex(CoordinationRemoteError, "TRANSITION_EXPECTED_PLAN_REQUIRED"):
            coordination_apply.apply(authority, plan, None)
        self.assertEqual(0, authority.mutate_calls)

    def test_expected_plan_mismatch_is_rejected_before_mutation(self):
        before = coordination.empty_state(revision=HEAD0)
        plan = self._plan(before)
        authority = FakeAuthority(before)
        with self.assertRaisesRegex(CoordinationRemoteError, "TRANSITION_EXPECTED_PLAN_MISMATCH"):
            coordination_apply.apply(authority, plan, "0" * 64)
        self.assertEqual(0, authority.mutate_calls)

    def test_stale_head_is_rejected_before_mutation(self):
        before = coordination.empty_state(revision=HEAD0)
        plan = self._plan(before)
        authority = FakeAuthority(before, head="9" * 40)
        with self.assertRaisesRegex(CoordinationRemoteError, "COORDINATION_PLAN_STALE"):
            coordination_apply.apply(authority, plan, plan["planHash"])
        self.assertEqual(0, authority.mutate_calls)

    def test_success_returns_verified_transition_receipt(self):
        before = coordination.empty_state(revision=HEAD0)
        plan = self._plan(before)
        authority = FakeAuthority(before)
        receipt = coordination_apply.apply(authority, plan, plan["planHash"])
        protocol.validate_receipt(receipt, plan)
        self.assertTrue(receipt["verified"])
        self.assertEqual(HEAD1, receipt["authorityRevision"])
        self.assertEqual(HEAD0, authority.last_expected_revision)
        self.assertEqual(1, authority.mutate_calls)

    def test_domain_tamper_is_rejected_before_mutation(self):
        before = coordination.empty_state(revision=HEAD0)
        plan = self._plan(before)
        broken = copy.deepcopy(plan)
        broken["intent"]["reason"] = "different"
        core = {k: copy.deepcopy(v) for k, v in broken.items() if k != "planHash"}
        from tools.canonical import stable_hash
        broken["planHash"] = stable_hash(core)
        authority = FakeAuthority(before)
        with self.assertRaises(CoordinationRemoteError):
            coordination_apply.apply(authority, broken, broken["planHash"])
        self.assertEqual(0, authority.mutate_calls)


if __name__ == "__main__":
    unittest.main()
