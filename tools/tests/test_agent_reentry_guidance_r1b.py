from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools import agent, agent_reentry_guidance, continuation, hosted_agent_cycle as hosted

WORK_ID = "m13-r1b-reentry-test"
HEAD = "a" * 40


def _work() -> dict:
    return continuation.valid(
        {
            "schemaVersion": continuation.CURRENT_SCHEMA_VERSION,
            "id": WORK_ID,
            "workerId": "manager-gitops-a",
            "status": "IN_PROGRESS",
            "branch": None,
            "prNumber": None,
            "dependsOn": [],
            "completed": [],
            "remaining": ["finish-r1b"],
            "nextAction": "continue-r1b",
            "lastKnownGood": {"sha": HEAD, "checkpoint": "M13-R1B"},
            "blockers": [],
            "handoffToWorkerId": None,
        },
        WORK_ID,
    )


def _pending_begin_comment(comment_id: int) -> dict:
    command = {
        "schemaVersion": hosted.COMMAND_SCHEMA_V03,
        "requestId": "r1b-pending-begin",
        "action": "begin",
        "actor": {
            "role": "manager-gitops",
            "workerId": "manager-gitops-a",
            "sessionId": "m13-r1b",
        },
        "declaredIntent": "inspect-and-plan",
        "machineScope": "live",
        "workRef": {"workId": WORK_ID},
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {
        "id": comment_id,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": hosted.REQUEST_MARKER_V03 + "\n" + json.dumps(command),
    }


class _Transport:
    def __init__(self, comment_pages: dict[int, list[dict]]):
        self.comment_pages = comment_pages
        self.calls: list[str] = []

    def request(self, method, endpoint, payload=None):
        self.calls.append(endpoint)
        if endpoint.startswith(f"repos/{hosted.REPOSITORY}/issues?state=open"):
            page = int(endpoint.rsplit("page=", 1)[1])
            values = (
                [{"number": 145, "title": hosted.BUS_TITLE}]
                if page == 1
                else []
            )
            return SimpleNamespace(body=json.dumps(values))
        if endpoint.startswith(f"repos/{hosted.REPOSITORY}/issues/145/comments"):
            page = int(endpoint.rsplit("page=", 1)[1])
            return SimpleNamespace(body=json.dumps(self.comment_pages.get(page, [])))
        raise AssertionError(endpoint)


class AgentReentryGuidanceR1BTests(unittest.TestCase):
    @patch("tools.agent_reentry_guidance.continuation_remote.GitHubContinuationAuthority")
    def test_complete_pagination_prevents_false_clean_reentry(self, authority_cls):
        authority_cls.return_value.observe.return_value = SimpleNamespace(
            head_sha=HEAD,
            items={WORK_ID: _work()},
        )
        irrelevant = [
            {"id": index + 1, "author_association": "NONE", "body": "noise"}
            for index in range(agent_reentry_guidance.PER_PAGE)
        ]
        transport = _Transport({1: irrelevant, 2: [_pending_begin_comment(1001)]})

        result = agent_reentry_guidance.observe_live(WORK_ID, transport=transport)

        self.assertEqual("INSUFFICIENT_OBSERVATION", result["state"])
        self.assertEqual("OBSERVE", result["nextSafeAction"])
        self.assertEqual(["HOSTED_BEGIN_PENDING"], result["reasonCodes"])
        self.assertTrue(any("comments" in call and "page=2" in call for call in transport.calls))

    def test_status_bootstrap_prioritizes_canonical_reentry_action(self):
        inspection = {
            "state": "LEGITIMATE_WAIT",
            "nextSafeAction": "WAIT",
            "reasonCodes": ["WORK_WAITING"],
            "targetCycle": None,
        }
        guidance = agent._reentry_success(WORK_ID, inspection)
        bootstrap = agent._bootstrap_projection(guidance)

        self.assertEqual("WAIT", bootstrap["nextSafeAction"])
        self.assertEqual("LEGITIMATE_WAIT", bootstrap["reentryDisposition"])
        self.assertEqual({"workId": WORK_ID}, bootstrap["workRef"])
        self.assertIsNone(bootstrap["commandTemplate"])
        self.assertFalse(bootstrap["authorizesMutation"])

    def test_unknown_observation_routes_to_observe_not_begin(self):
        error = agent_reentry_guidance.AgentReentryGuidanceError(
            "AGENT_REENTRY_PROVIDER_UNAVAILABLE", "comments"
        )
        guidance = agent._reentry_unknown(WORK_ID, error)
        bootstrap = agent._bootstrap_projection(guidance)

        self.assertEqual("UNKNOWN", guidance["status"])
        self.assertEqual("INSUFFICIENT_OBSERVATION", guidance["reentryDisposition"])
        self.assertEqual("OBSERVE", bootstrap["nextSafeAction"])
        self.assertEqual(["AGENT_REENTRY_PROVIDER_UNAVAILABLE"], bootstrap["reasonCodes"])
        self.assertFalse(bootstrap["authorizesMutation"])


if __name__ == "__main__":
    unittest.main()
