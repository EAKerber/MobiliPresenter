from __future__ import annotations

import copy
import unittest

from tools import provider_host_action


class ProviderHostActionTests(unittest.TestCase):
    def test_issue_comment_is_exact_read_only_host_plan(self) -> None:
        value = provider_host_action.issue_comment(
            repository="EAKerber/MobiliPresenter",
            issue_number=145,
            body="MARKER\n{}",
        )
        provider_host_action.validate(value)
        self.assertEqual(value["toolSurface"], "github-connector-tools")
        self.assertEqual(value["operation"], "issue-comment.create")
        self.assertEqual(
            value["request"]["endpoint"],
            "repos/EAKerber/MobiliPresenter/issues/145/comments",
        )
        self.assertTrue(value["readOnly"])
        self.assertFalse(value["authorizesMutation"])

    def test_workflow_rerun_binds_exact_head_and_next_attempt(self) -> None:
        value = provider_host_action.workflow_rerun(
            repository="EAKerber/MobiliPresenter",
            run_id=123,
            head_sha="a" * 40,
            run_attempt=2,
        )
        provider_host_action.validate(value)
        self.assertEqual(value["operation"], "workflow-run.rerun")
        self.assertEqual(value["preconditions"]["headSha"], "a" * 40)
        self.assertEqual(value["readback"]["minimumRunAttempt"], 3)

    def test_tampered_endpoint_fails_validation(self) -> None:
        value = provider_host_action.issue_comment(
            repository="EAKerber/MobiliPresenter",
            issue_number=145,
            body="MARKER\n{}",
        )
        tampered = copy.deepcopy(value)
        tampered["request"]["endpoint"] = "repos/EAKerber/MobiliPresenter/issues/999/comments"
        with self.assertRaisesRegex(
            provider_host_action.ProviderHostActionError,
            "PROVIDER_HOST_ACTION_SEMANTICS_INVALID",
        ):
            provider_host_action.validate(tampered)


if __name__ == "__main__":
    unittest.main()
