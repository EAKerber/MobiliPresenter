from __future__ import annotations

import copy
import unittest

from tools import agent_cycle_close
from tools.canonical import stable_hash
from tools import hosted_cycle_external_delta_recovery as recovery


WORK_ID = "e5-governed-mutation-request-client"
WORK_BRANCH = "work/operations/e5-governed-mutation-request-client"
CONTINUATION_BEFORE = "d" * 40
CONTINUATION_AFTER = "e" * 40
CONTROL_BEFORE = "1" * 40
CONTROL_MIDDLE = "2" * 40
CONTROL_AFTER = "3" * 40


class HostedCycleExternalDeltaRecoveryTests(unittest.TestCase):
    def _work(self):
        return {
            "id": WORK_ID,
            "branch": WORK_BRANCH,
            "prNumber": None,
            "status": "IN_PROGRESS",
            "workerId": "manager-gitops-chat",
        }

    def _context(self):
        work = self._work()
        return {
            "cycleId": "cycle-test-external-delta",
            "workRef": {"workId": WORK_ID},
            "baseline": {
                "sourceHeads": {
                    "continuation": {
                        "branch": "coordination/continuations",
                        "sha": CONTINUATION_BEFORE,
                    },
                    "control": {"branch": "main", "sha": CONTROL_BEFORE},
                },
            },
            "projectMachine": {
                "sensors": {
                    "continuations": {"data": {"items": [work]}},
                },
            },
        }

    def _closure(self):
        before = self._context()
        after = copy.deepcopy(before)
        change = {
            "kind": "source-head",
            "name": "control",
            "branch": "main",
            "before": CONTROL_BEFORE,
            "after": CONTROL_AFTER,
        }
        return {
            "afterContext": after,
            "status": "UNKNOWN",
            "receipt": {
                "blockers": ["UNATTRIBUTED_DURABLE_DELTA"],
                "delta": {"durableChanges": [change]},
                "aggregateReadback": {
                    "uncoveredDurableChanges": ["source-head:control:0"],
                },
            },
        }

    def _pulls(self):
        return [
            {
                "commitSha": CONTROL_MIDDLE,
                "prNumber": 351,
                "headBranch": "work/operations/e5e-lineage-invalid-transport-repair",
                "baseSha": CONTROL_BEFORE,
            },
            {
                "commitSha": CONTROL_AFTER,
                "prNumber": 352,
                "headBranch": "work/operations/e5f-terminal-begin-failure-lineage",
                "baseSha": CONTROL_MIDDLE,
            },
        ]

    def test_builds_existing_noninterference_contract_for_external_chain(self):
        before = self._context()
        evidence = recovery.build_noninterference_evidence(
            before_context=before,
            failed_closure=self._closure(),
            continuation_after_sha=CONTINUATION_AFTER,
            continuation_changed_paths=[
                "ops/continuations/e5g-sealed-close-external-delta-recovery.json"
            ],
            merged_pull_requests=self._pulls(),
        )
        self.assertEqual(
            agent_cycle_close.NONINTERFERENCE_SCHEMA,
            evidence["schemaVersion"],
        )
        self.assertEqual(WORK_BRANCH, evidence["workBranch"])
        self.assertEqual(stable_hash(self._work()), evidence["workStateHash"])
        self.assertEqual(
            [351, 352],
            [item["prNumber"] for item in evidence["controlReadback"]["mergedPullRequests"]],
        )
        agent_cycle_close.verify_evidence(evidence)

    def test_own_work_continuation_delta_remains_blocked(self):
        with self.assertRaisesRegex(
            recovery.HostedCycleExternalDeltaRecoveryError,
            "HOSTED_CYCLE_EXTERNAL_DELTA_WORK_CHANGED",
        ):
            recovery.build_noninterference_evidence(
                before_context=self._context(),
                failed_closure=self._closure(),
                continuation_after_sha=CONTINUATION_AFTER,
                continuation_changed_paths=[f"ops/continuations/{WORK_ID}.json"],
                merged_pull_requests=self._pulls(),
            )

    def test_own_work_pull_request_remains_blocked(self):
        pulls = self._pulls()
        pulls[0]["headBranch"] = WORK_BRANCH
        with self.assertRaisesRegex(
            recovery.HostedCycleExternalDeltaRecoveryError,
            "HOSTED_CYCLE_EXTERNAL_DELTA_CONTROL_READBACK_INVALID",
        ):
            recovery.build_noninterference_evidence(
                before_context=self._context(),
                failed_closure=self._closure(),
                continuation_after_sha=CONTINUATION_AFTER,
                continuation_changed_paths=["ops/continuations/other.json"],
                merged_pull_requests=pulls,
            )

    def test_control_chain_gap_remains_blocked(self):
        pulls = self._pulls()
        pulls[1]["baseSha"] = "4" * 40
        with self.assertRaisesRegex(
            recovery.HostedCycleExternalDeltaRecoveryError,
            "HOSTED_CYCLE_EXTERNAL_DELTA_CONTROL_READBACK_INVALID",
        ):
            recovery.build_noninterference_evidence(
                before_context=self._context(),
                failed_closure=self._closure(),
                continuation_after_sha=CONTINUATION_AFTER,
                continuation_changed_paths=["ops/continuations/other.json"],
                merged_pull_requests=pulls,
            )

    def test_non_control_uncovered_delta_is_not_generalized(self):
        closure = self._closure()
        closure["receipt"]["delta"]["durableChanges"][0]["name"] = "continuation"
        closure["receipt"]["aggregateReadback"]["uncoveredDurableChanges"] = [
            "source-head:continuation:0"
        ]
        with self.assertRaisesRegex(
            recovery.HostedCycleExternalDeltaRecoveryError,
            "HOSTED_CYCLE_EXTERNAL_DELTA_CHANGE_UNSUPPORTED",
        ):
            recovery.build_noninterference_evidence(
                before_context=self._context(),
                failed_closure=closure,
                continuation_after_sha=CONTINUATION_AFTER,
                continuation_changed_paths=["ops/continuations/other.json"],
                merged_pull_requests=self._pulls(),
            )


if __name__ == "__main__":
    unittest.main()
