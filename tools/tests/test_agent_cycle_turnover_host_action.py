from __future__ import annotations

import unittest
from unittest import mock

from tools import agent_cycle_turnover_host


class AgentCycleTurnoverHostActionTests(unittest.TestCase):
    @mock.patch("tools.agent_cycle_turnover_host.hosted_cycle_handle.decode_handle")
    @mock.patch("tools.agent_cycle_turnover_host.agent_ownership.release_ownership")
    @mock.patch("tools.agent_cycle_turnover_host.agent_ownership.observe_write_lifecycle_state")
    @mock.patch("tools.agent_cycle_turnover_host._readiness")
    @mock.patch("tools.agent_cycle_turnover_host.agent_reentry_guidance.observe_turnover_context")
    def test_release_projects_exact_connector_host_action(
        self,
        observe_turnover: mock.Mock,
        readiness: mock.Mock,
        observe_lifecycle: mock.Mock,
        release_ownership: mock.Mock,
        decode_handle: mock.Mock,
    ) -> None:
        handle = {"opaque": True}
        observe_turnover.return_value = {
            "work": {"branch": "work/operations/example"},
            "actor": {"role": "manager-gitops"},
            "currentIntent": "governed-mutation",
            "handle": handle,
            "reentry": {"nextSafeAction": "RESUME_EXACT_CYCLE"},
            "busIssueNumber": 145,
        }
        readiness.return_value = {
            "nextSafeAction": {
                "action": "SELECT_INTENT",
                "candidateIntents": ["inspect-and-plan"],
            }
        }
        observe_lifecycle.return_value = {"state": "ACTIVE"}
        release_ownership.return_value = {
            "request": {"requestId": "release-1"},
            "requestCommentId": None,
        }
        decode_handle.return_value = ({}, {"issueNumber": 145})

        value = agent_cycle_turnover_host.continue_work(
            work_id="example",
            machine={},
            runtime_inspection={},
            tool_surfaces=["github-connector-tools"],
            inventory_complete=True,
            submit=False,
            transport=object(),
        )

        action = value["hostAction"]
        self.assertIsNotNone(action)
        self.assertEqual(action["operation"], "issue-comment.create")
        self.assertEqual(
            action["request"]["endpoint"],
            "repos/EAKerber/MobiliPresenter/issues/145/comments",
        )
        self.assertIn("MOBILIPRESENTER", action["request"]["payload"]["body"])
        self.assertFalse(value["submitted"])

    @mock.patch("tools.agent_cycle_turnover_host.hosted_cycle_handle.decode_handle")
    @mock.patch("tools.agent_cycle_turnover_host.agent_ownership.release_ownership")
    @mock.patch("tools.agent_cycle_turnover_host.agent_ownership.observe_write_lifecycle_state")
    @mock.patch("tools.agent_cycle_turnover_host._readiness")
    @mock.patch("tools.agent_cycle_turnover_host.agent_reentry_guidance.observe_turnover_context")
    def test_existing_release_request_does_not_emit_duplicate_host_action(
        self,
        observe_turnover: mock.Mock,
        readiness: mock.Mock,
        observe_lifecycle: mock.Mock,
        release_ownership: mock.Mock,
        decode_handle: mock.Mock,
    ) -> None:
        handle = {"opaque": True}
        observe_turnover.return_value = {
            "work": {"branch": "work/operations/example"},
            "actor": {"role": "manager-gitops"},
            "currentIntent": "governed-mutation",
            "handle": handle,
            "reentry": {"nextSafeAction": "RESUME_EXACT_CYCLE"},
            "busIssueNumber": 145,
        }
        readiness.return_value = {
            "nextSafeAction": {
                "action": "SELECT_INTENT",
                "candidateIntents": ["inspect-and-plan"],
            }
        }
        observe_lifecycle.return_value = {"state": "ACTIVE"}
        release_ownership.return_value = {
            "request": {"requestId": "release-1"},
            "requestCommentId": 777,
        }
        decode_handle.return_value = ({}, {"issueNumber": 145})

        value = agent_cycle_turnover_host.continue_work(
            work_id="example",
            machine={},
            runtime_inspection={},
            tool_surfaces=["github-connector-tools"],
            inventory_complete=True,
            submit=False,
            transport=object(),
        )

        self.assertIsNone(value["hostAction"])


if __name__ == "__main__":
    unittest.main()
