from __future__ import annotations

import copy
import unittest
from datetime import datetime, timedelta, timezone

from tools import coordination, coordination_transition as transition
from tools import transition_protocol as protocol
from tools.canonical import stable_hash

HEAD0 = "1" * 40
NOW = datetime(2026, 8, 22, 22, 0, 0, tzinfo=timezone.utc)
OWNER = {
    "role": "manager-gitops",
    "session": "cv1b-test",
    "branch": "work/operations/cv1b-test",
    "pr": None,
}
RESOURCE = "file:ops/coordination/cv1b-probe.shared"


class CoordinationTransitionTests(unittest.TestCase):
    def test_same_inputs_produce_same_plan(self):
        before = coordination.empty_state(revision=HEAD0)
        left = transition.plan_acquire(
            before,
            authority_head=HEAD0,
            authority_now=NOW,
            owner=OWNER,
            resources=[RESOURCE],
            reason="cv1b deterministic plan",
            transition_id="cv1b-acquire",
        )
        right = transition.plan_acquire(
            before,
            authority_head=HEAD0,
            authority_now=NOW,
            owner=OWNER,
            resources=[RESOURCE],
            reason="cv1b deterministic plan",
            transition_id="cv1b-acquire",
        )
        self.assertEqual(left, right)
        self.assertEqual("TransitionPlan 0.1", left["schemaVersion"])
        self.assertEqual("coordination", left["domain"])
        self.assertEqual("compensatable", left["reversibility"])
        self.assertEqual(HEAD0, left["candidate"]["revision"])
        transition.validate_plan(left, before, bind_before=True, authority_now=NOW)

    def test_generic_rehash_cannot_bypass_domain_rebuild(self):
        before = coordination.empty_state(revision=HEAD0)
        original = transition.plan_intent(
            before,
            authority_head=HEAD0,
            authority_now=NOW,
            owner=OWNER,
            resources=[RESOURCE],
            reason="cv1b intent",
            transition_id="cv1b-intent",
        )
        tampered_candidate = copy.deepcopy(original["candidate"])
        tampered_candidate["intents"][0]["reason"] = "tampered but rehashed"
        tampered = protocol.build_plan(
            domain=original["domain"],
            action=original["action"],
            subject=original["subject"],
            authority=original["authority"],
            before=before,
            candidate=tampered_candidate,
            intent=original["intent"],
            reversibility=original["reversibility"],
        )
        protocol.validate_plan(tampered)
        with self.assertRaisesRegex(RuntimeError, "COORDINATION_PLAN_SEMANTIC_MISMATCH"):
            transition.validate_plan(tampered, before, bind_before=True, authority_now=NOW)

    def test_expired_acquire_is_rejected_at_apply_time(self):
        before = coordination.empty_state(revision=HEAD0)
        plan = transition.plan_acquire(
            before,
            authority_head=HEAD0,
            authority_now=NOW,
            owner=OWNER,
            resources=[RESOURCE],
            reason="short lease",
            transition_id="cv1b-short",
            ttl_seconds=1,
        )
        with self.assertRaisesRegex(RuntimeError, "COORDINATION_PLAN_EXPIRED"):
            transition.validate_plan(
                plan,
                before,
                bind_before=True,
                authority_now=NOW + timedelta(seconds=2),
            )

    def test_remote_time_regression_is_rejected(self):
        before = coordination.empty_state(revision=HEAD0)
        plan = transition.plan_intent(
            before,
            authority_head=HEAD0,
            authority_now=NOW,
            owner=OWNER,
            resources=[RESOURCE],
            reason="intent",
            transition_id="cv1b-time",
        )
        with self.assertRaisesRegex(RuntimeError, "COORDINATION_REMOTE_TIME_REGRESSION"):
            transition.validate_plan(
                plan,
                before,
                bind_before=True,
                authority_now=NOW - timedelta(seconds=1),
            )

    def test_renew_cannot_resurrect_expired_lease(self):
        base = coordination.empty_state(revision=HEAD0)
        acquired, _ = coordination.plan_acquire(
            base,
            [RESOURCE],
            OWNER,
            "short lease",
            NOW,
            "cv1b-seed",
            1,
        )
        acquired["revision"] = HEAD0
        plan = transition.plan_renew(
            acquired,
            authority_head=HEAD0,
            authority_now=NOW,
            owner=OWNER,
            transition_id="cv1b-renew",
        )
        with self.assertRaisesRegex(RuntimeError, "COORDINATION_RENEW_TARGET_EXPIRED"):
            transition.validate_plan(
                plan,
                acquired,
                bind_before=True,
                authority_now=NOW + timedelta(seconds=2),
            )

    def test_wrong_authority_locator_is_rejected(self):
        before = coordination.empty_state(revision=HEAD0)
        plan = transition.plan_acquire(
            before,
            authority_head=HEAD0,
            authority_now=NOW,
            owner=OWNER,
            resources=[RESOURCE],
            reason="wrong locator test",
            transition_id="cv1b-locator",
        )
        broken = copy.deepcopy(plan)
        broken["authority"]["locator"]["branch"] = "main"
        core = {k: copy.deepcopy(v) for k, v in broken.items() if k != "planHash"}
        broken["planHash"] = stable_hash(core)
        protocol.validate_plan(broken)
        with self.assertRaisesRegex(RuntimeError, "COORDINATION_PLAN_AUTHORITY_INVALID"):
            transition.validate_plan(broken)


if __name__ == "__main__":
    unittest.main()
