from __future__ import annotations

import copy
import unittest

from tools import hosted_project_state_checkpoint as hosted


def request():
    return {
        "schemaVersion": hosted.REQUEST_SCHEMA,
        "requestId": "m13-project-state-checkpoint-test",
        "actor": {
            "role": "manager-gitops",
            "workerId": "interactive-manager-gitops",
            "sessionId": "session-1",
        },
        "cycleInstanceId": "cycle-instance-1",
        "branch": "work/operations/m13-project-state-closure-v0.1",
        "expectedBranchHead": "a" * 40,
        "checkpoint": "M13-REFLECTION-QUIESCENCE-0.1-CLOSED",
        "nextTransition": "reassess-pcs-01b-module-presentation-metadata-admission-v0.1",
        "phase": "between-increments",
        "expectedPlanHash": "b" * 64,
        "message": "M13: apply ProjectState closure",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


class HostedProjectStateCheckpointTests(unittest.TestCase):
    def test_canonical_request_is_accepted(self):
        value = request()
        self.assertEqual(value, hosted.validate(value))

    def test_control_branch_is_rejected(self):
        value = request()
        value["branch"] = "main"
        with self.assertRaisesRegex(RuntimeError, "BRANCH_FORBIDDEN"):
            hosted.validate(value)

    def test_non_manager_role_is_rejected(self):
        value = request()
        value["actor"]["role"] = "ui-ux"
        with self.assertRaisesRegex(RuntimeError, "ROLE_FORBIDDEN"):
            hosted.validate(value)

    def test_request_never_authorizes_mutation(self):
        for field in ("semanticAuthority", "authorizesMutation"):
            value = copy.deepcopy(request())
            value[field] = True
            with self.assertRaisesRegex(RuntimeError, "REQUEST_NOT_CANONICAL"):
                hosted.validate(value)

    def test_plan_hash_and_head_are_exactly_bound(self):
        value = request()
        value["expectedPlanHash"] = "b" * 63
        with self.assertRaisesRegex(RuntimeError, "PLAN_INVALID"):
            hosted.validate(value)
        value = request()
        value["expectedBranchHead"] = "a" * 39
        with self.assertRaisesRegex(RuntimeError, "HEAD_INVALID"):
            hosted.validate(value)


if __name__ == "__main__":
    unittest.main()
