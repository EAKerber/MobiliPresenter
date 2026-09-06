from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools import hosted_cycle_close_compat_recovery as recovery


def eligible_failure() -> dict:
    return {
        "schemaVersion": "HostedAgentCycleFailure 0.2",
        "requestId": "close-v1",
        "commandHash": "a" * 64,
        "status": "UNKNOWN",
        "failureCore": {
            "schemaVersion": "AgentFailureCore 0.1",
            "surface": "AGENT_CYCLE",
            "phase": "CLOSE",
            "status": "UNKNOWN",
            "causes": [{
                "code": "HOSTED_CYCLE_RECORD_LEASE_REQUEST_INVALID",
                "source": "hosted-agent-cycle-trace",
                "phase": "CLOSE",
            }],
            "recovery": {
                "observationRetry": "UNKNOWN",
                "operationReplay": "NOT_APPLICABLE",
            },
            "mutationState": "NOT_APPLICABLE",
            "lossyProjection": False,
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
            "failureCoreHash": "b" * 64,
        },
        "failureHash": "c" * 64,
    }


class HostedCycleCloseCompatibilityRecoveryTests(unittest.TestCase):
    def test_exact_observational_compatibility_failure_is_eligible(self) -> None:
        self.assertTrue(recovery.qualifies_close_compatibility_recovery(eligible_failure()))

    def test_other_trace_failure_is_not_eligible(self) -> None:
        value = eligible_failure()
        value["failureCore"]["causes"][0]["code"] = "EXECUTION_TRACE_INCOMPLETE"
        self.assertFalse(recovery.qualifies_close_compatibility_recovery(value))

    def test_additional_cause_is_not_eligible(self) -> None:
        value = eligible_failure()
        value["failureCore"]["causes"].append({
            "code": "HOSTED_AGENT_CLOSE_NOT_PASS",
            "source": "hosted-agent-cycle",
            "phase": "CLOSE",
        })
        self.assertFalse(recovery.qualifies_close_compatibility_recovery(value))

    def test_replay_or_mutation_uncertainty_is_not_eligible(self) -> None:
        for field, replacement in (
            ("recovery", {"observationRetry": "UNKNOWN", "operationReplay": "SAFE"}),
            ("mutationState", "UNKNOWN"),
            ("lossyProjection", True),
        ):
            with self.subTest(field=field):
                value = eligible_failure()
                value["failureCore"][field] = replacement
                self.assertFalse(recovery.qualifies_close_compatibility_recovery(value))

    def test_cli_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_text(json.dumps(eligible_failure()), encoding="utf-8")
            self.assertEqual(0, recovery.main(["--result", str(path)]))

            invalid = copy.deepcopy(eligible_failure())
            invalid["failureCore"]["readOnly"] = False
            path.write_text(json.dumps(invalid), encoding="utf-8")
            self.assertEqual(2, recovery.main(["--result", str(path)]))


if __name__ == "__main__":
    unittest.main()
