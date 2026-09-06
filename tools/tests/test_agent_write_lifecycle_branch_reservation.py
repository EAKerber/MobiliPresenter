from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools import agent_write_lifecycle as lifecycle
from tools import git_observation


BRANCH = "work/operations/m13-branch-reservation-test"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "session-m13-branch-reservation",
}
BEGIN = {
    "runId": 123,
    "sourceSha": "a" * 40,
    "contextHash": "b" * 64,
}
CYCLE_INSTANCE_ID = "cycle-instance-" + "8" * 24
AUTHORITY_HEAD = "c" * 40


def acquire_request(*, expected_branch_head=None) -> dict:
    return {
        "schemaVersion": lifecycle.REQUEST_SCHEMA,
        "requestId": "request-acquire-branch-reservation",
        "action": "acquire",
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "branch": BRANCH,
        "expectedAuthorityHead": AUTHORITY_HEAD,
        "expectedBranchHead": expected_branch_head,
        "expectedBindingHash": None,
        "ttlSeconds": 3600,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def manifest() -> dict:
    return {"cycleInstanceId": CYCLE_INSTANCE_ID}


def authority() -> SimpleNamespace:
    observed = SimpleNamespace(head_sha=AUTHORITY_HEAD)
    return SimpleNamespace(observe=lambda: observed)


class AgentWriteLifecycleBranchReservationTests(unittest.TestCase):
    def test_acquire_request_accepts_explicit_absent_branch_precondition(self) -> None:
        value = acquire_request()
        self.assertIsNone(lifecycle.validate_request(value)["expectedBranchHead"])

    def test_followup_request_still_requires_concrete_branch_head(self) -> None:
        value = acquire_request()
        value["action"] = "release"
        value["expectedBindingHash"] = "d" * 64
        value["ttlSeconds"] = None
        with self.assertRaisesRegex(
            RuntimeError, "AGENT_WRITE_LIFECYCLE_BRANCH_HEAD_INVALID"
        ):
            lifecycle.validate_request(value)

    @patch("tools.agent_write_lifecycle.validate_begin_binding")
    @patch("tools.agent_write_lifecycle._prepare_previous_binding", return_value=(None, None))
    @patch("tools.agent_write_lifecycle.git_observation.ref_head", return_value=None)
    def test_absent_branch_can_be_reserved_before_creation(
        self, ref_head, prepare_previous, validate_begin
    ) -> None:
        value = acquire_request()
        with patch(
            "tools.agent_write_lifecycle.GitHubCoordinationAuthority",
            return_value=authority(),
        ):
            dispatch = lifecycle.prepare_dispatch(
                value,
                manifest(),
                {},
                issue_number=145,
                request_comment_id=900,
                hosted_run_id=456,
                transport=object(),
            )
        ref_head.assert_called_once_with(object.__class__ if False else unittest.mock.ANY, BRANCH, missing_ok=True)
        self.assertIsNone(dispatch["expectedBranchHead"])
        self.assertIsNone(lifecycle.validate_dispatch(dispatch)["expectedBranchHead"])
        self.assertEqual([f"branch:{BRANCH}"], dispatch["command"]["payload"]["resources"])

    @patch("tools.agent_write_lifecycle.validate_begin_binding")
    @patch("tools.agent_write_lifecycle.git_observation.ref_head", return_value="9" * 40)
    def test_branch_created_before_reservation_is_drift(self, ref_head, validate_begin) -> None:
        with patch("tools.agent_write_lifecycle.GitHubCoordinationAuthority") as authority_cls:
            with self.assertRaisesRegex(
                RuntimeError, "AGENT_WRITE_LIFECYCLE_BRANCH_DRIFT"
            ):
                lifecycle.prepare_dispatch(
                    acquire_request(),
                    manifest(),
                    {},
                    issue_number=145,
                    request_comment_id=901,
                    hosted_run_id=457,
                    transport=object(),
                )
            authority_cls.assert_not_called()

    @patch("tools.agent_write_lifecycle.validate_begin_binding")
    @patch("tools.agent_write_lifecycle.git_observation.ref_head")
    def test_provider_failure_is_not_treated_as_branch_absence(
        self, ref_head, validate_begin
    ) -> None:
        ref_head.side_effect = git_observation.GitObservationError(
            "GIT_OBSERVATION_REF_UNAVAILABLE"
        )
        with patch("tools.agent_write_lifecycle.GitHubCoordinationAuthority") as authority_cls:
            with self.assertRaisesRegex(
                RuntimeError, "GIT_OBSERVATION_REF_UNAVAILABLE"
            ):
                lifecycle.prepare_dispatch(
                    acquire_request(),
                    manifest(),
                    {},
                    issue_number=145,
                    request_comment_id=902,
                    hosted_run_id=458,
                    transport=object(),
                )
            authority_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
