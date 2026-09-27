from __future__ import annotations

import json
import unittest

from tools import agent_cycle_close
from tools import hosted_cycle_own_work_delta_recovery as recovery


WORK_BRANCH = "work/operations/e5g-sealed-close-external-delta-recovery"
CONTROL_BEFORE = "1" * 40
CONTROL_MIDDLE = "2" * 40
CONTROL_AFTER = "3" * 40
HEAD_ONE = "4" * 40
HEAD_TWO = "5" * 40


class FakeResponse:
    def __init__(self, body):
        self.body = json.dumps(body)


class FakeTransport:
    def __init__(self, responses):
        self.responses = responses

    def request(self, method, endpoint):
        self.assert_method(method)
        return FakeResponse(self.responses[endpoint])

    @staticmethod
    def assert_method(method):
        if method != "GET":
            raise AssertionError(method)


class HostedCycleOwnWorkDeltaRecoveryTests(unittest.TestCase):
    def _pulls(self):
        return [
            {
                "commitSha": CONTROL_MIDDLE,
                "prNumber": 353,
                "headBranch": WORK_BRANCH,
                "headSha": HEAD_ONE,
                "baseSha": CONTROL_BEFORE,
                "mergedAt": "2026-09-26T22:28:04Z",
            },
            {
                "commitSha": CONTROL_AFTER,
                "prNumber": 354,
                "headBranch": WORK_BRANCH,
                "headSha": HEAD_TWO,
                "baseSha": CONTROL_MIDDLE,
                "mergedAt": "2026-09-26T22:38:17Z",
            },
        ]

    def _validate(self, pulls=None, *, active_until="2026-09-26T22:55:05Z"):
        return recovery.validate_own_work_chain(
            self._pulls() if pulls is None else pulls,
            before_sha=CONTROL_BEFORE,
            after_sha=CONTROL_AFTER,
            work_branch=WORK_BRANCH,
            work_pr_number=None,
            active_from="2026-09-26T22:00:00Z",
            active_until=active_until,
        )

    def test_accepts_complete_own_work_chain_inside_authority_window(self):
        pulls = self._validate()
        self.assertEqual([353, 354], [item["prNumber"] for item in pulls])
        evidence = [recovery.build_merge_evidence(item) for item in pulls]
        self.assertEqual(2, len(evidence))
        for item in evidence:
            self.assertEqual("git-mutation-plan-readback", item["kind"])
            agent_cycle_close.verify_evidence(item)

    def test_foreign_branch_is_not_reclassified_as_own_work(self):
        pulls = self._pulls()
        pulls[0]["headBranch"] = "work/operations/other"
        with self.assertRaisesRegex(
            recovery.HostedCycleOwnWorkDeltaRecoveryError,
            "HOSTED_CYCLE_OWN_WORK_CONTROL_CHAIN_INVALID",
        ):
            self._validate(pulls)

    def test_merge_after_authority_expiry_remains_blocked(self):
        with self.assertRaisesRegex(
            recovery.HostedCycleOwnWorkDeltaRecoveryError,
            "HOSTED_CYCLE_OWN_WORK_CONTROL_CHAIN_INVALID",
        ):
            self._validate(active_until="2026-09-26T22:35:00Z")

    def test_control_chain_gap_remains_blocked(self):
        pulls = self._pulls()
        pulls[1]["baseSha"] = "6" * 40
        with self.assertRaisesRegex(
            recovery.HostedCycleOwnWorkDeltaRecoveryError,
            "HOSTED_CYCLE_OWN_WORK_CONTROL_CHAIN_INVALID",
        ):
            self._validate(pulls)

    def test_bound_pr_number_anchors_multi_pr_own_branch_chain(self):
        pulls = recovery.validate_own_work_chain(
            self._pulls(),
            before_sha=CONTROL_BEFORE,
            after_sha=CONTROL_AFTER,
            work_branch=WORK_BRANCH,
            work_pr_number=354,
            active_from="2026-09-26T22:00:00Z",
            active_until="2026-09-26T22:55:05Z",
        )
        self.assertEqual([353, 354], [item["prNumber"] for item in pulls])

    def test_bound_pr_number_missing_from_chain_is_rejected(self):
        with self.assertRaisesRegex(
            recovery.HostedCycleOwnWorkDeltaRecoveryError,
            "HOSTED_CYCLE_OWN_WORK_CONTROL_CHAIN_INVALID",
        ):
            recovery.validate_own_work_chain(
                self._pulls(),
                before_sha=CONTROL_BEFORE,
                after_sha=CONTROL_AFTER,
                work_branch=WORK_BRANCH,
                work_pr_number=355,
                active_from="2026-09-26T22:00:00Z",
                active_until="2026-09-26T22:55:05Z",
            )

    def test_discovery_allows_earlier_same_branch_pr_before_bound_anchor(self):
        responses = {
            f"repos/{recovery.hosted_agent_cycle.REPOSITORY}/commits/{CONTROL_AFTER}": {
                "parents": [{"sha": CONTROL_MIDDLE}, {"sha": HEAD_TWO}],
            },
            f"repos/{recovery.hosted_agent_cycle.REPOSITORY}/commits/{CONTROL_AFTER}/pulls": [
                {
                    "number": 354,
                    "merged_at": "2026-09-26T22:38:17Z",
                    "merge_commit_sha": CONTROL_AFTER,
                    "head": {"ref": WORK_BRANCH, "sha": HEAD_TWO},
                    "base": {"ref": "main"},
                }
            ],
            f"repos/{recovery.hosted_agent_cycle.REPOSITORY}/commits/{CONTROL_MIDDLE}": {
                "parents": [{"sha": CONTROL_BEFORE}, {"sha": HEAD_ONE}],
            },
            f"repos/{recovery.hosted_agent_cycle.REPOSITORY}/commits/{CONTROL_MIDDLE}/pulls": [
                {
                    "number": 353,
                    "merged_at": "2026-09-26T22:28:04Z",
                    "merge_commit_sha": CONTROL_MIDDLE,
                    "head": {"ref": WORK_BRANCH, "sha": HEAD_ONE},
                    "base": {"ref": "main"},
                }
            ],
        }
        pulls = recovery.merged_pull_request_chain(
            before_sha=CONTROL_BEFORE,
            after_sha=CONTROL_AFTER,
            work_branch=WORK_BRANCH,
            work_pr_number=354,
            active_from="2026-09-26T22:00:00Z",
            active_until="2026-09-26T22:55:05Z",
            transport=FakeTransport(responses),
        )
        self.assertEqual([353, 354], [item["prNumber"] for item in pulls])


if __name__ == "__main__":
    unittest.main()
