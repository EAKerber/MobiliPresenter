import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import hosted_agent_cycle as hosted
from tools.agent_cycle_close_recovery import hosted as recovery


class HostedAgentCycleCloseRecoveryTests(unittest.TestCase):
    def exact_failure_core(self):
        body = {
            "schemaVersion": "AgentFailureCore 0.1",
            "surface": "AGENT_CYCLE",
            "phase": "CLOSE",
            "status": "UNKNOWN",
            "causes": [
                {"code": "UNATTRIBUTED_DURABLE_DELTA", "source": "agent-cycle-close", "phase": "CLOSE"},
                {"code": "HOSTED_AGENT_CLOSE_NOT_PASS", "source": "hosted-agent-cycle", "phase": "CLOSE"},
            ],
            "recovery": {"observationRetry": "UNKNOWN", "operationReplay": "NOT_APPLICABLE"},
            "mutationState": "NOT_APPLICABLE",
            "lossyProjection": False,
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        return {**body, "failureCoreHash": hosted.stable_hash(body)}

    def test_exact_core_is_narrow(self):
        core = self.exact_failure_core()
        self.assertTrue(recovery._exact_core(core))
        changed = dict(core)
        changed["lossyProjection"] = True
        self.assertFalse(recovery._exact_core(changed))

    def test_canonical_runner_delegates_directly_to_close_from_files(self):
        with mock.patch.object(
            recovery.agent_cycle_close,
            "close_from_files",
            return_value={"status": "UNKNOWN"},
        ) as close:
            rc, payload = recovery._canonical_close_runner([
                "close", "--context", "context.json", "--machine-scope", "live", "--json"
            ])
        self.assertEqual(1, rc)
        self.assertEqual("UNKNOWN", payload["status"])
        close.assert_called_once_with(
            context_path="context.json",
            machine_scope="live",
            observations_path=None,
            runtime_providers=None,
            evidence_paths=[],
        )

    def test_missing_compatibility_source_preserves_original_failure_and_restores_runner(self):
        command = {"requestId": "close-r0-2"}
        original_runner = hosted._run_agent
        error = hosted.HostedAgentCycleError(
            "HOSTED_AGENT_CLOSE_NOT_PASS",
            failure_core=self.exact_failure_core(),
        )
        with tempfile.TemporaryDirectory() as root, \
             mock.patch.object(recovery.hosted, "validate_transport_command", return_value=command), \
             mock.patch.object(recovery.hosted, "close_from_envelope", side_effect=error):
            with self.assertRaises(hosted.HostedAgentCycleError):
                recovery.close_with_compatibility_recovery(
                    command,
                    {},
                    begin_dir=root,
                    output_path=str(Path(root) / "closure.json"),
                    evidence_dir=str(Path(root) / "evidence"),
                )
        self.assertIs(hosted._run_agent, original_runner)

    def test_compatibility_source_must_match_request_and_command_hash(self):
        command = {"requestId": "close-r0-2"}
        failure = {
            "schemaVersion": "HostedAgentCycleFailure 0.2",
            "requestId": "close-r0-2",
            "commandHash": "h" * 64,
            "status": "BLOCKED",
            "failureCore": self.exact_failure_core(),
        }
        failure["failureHash"] = hosted.stable_hash({k: v for k, v in failure.items() if k != "failureHash"})
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "compatibility-recovery-source.json"
            path.write_text(json.dumps(failure), encoding="utf-8")
            with mock.patch.object(recovery.agent_failure, "validate_hosted_cycle_failure", return_value=failure), \
                 mock.patch.object(recovery.hosted, "transport_command_hash", return_value="h" * 64):
                self.assertTrue(recovery._compatibility_source_allows(path, command))
            failure["requestId"] = "other"
            with mock.patch.object(recovery.agent_failure, "validate_hosted_cycle_failure", return_value=failure), \
                 mock.patch.object(recovery.hosted, "transport_command_hash", return_value="h" * 64):
                self.assertFalse(recovery._compatibility_source_allows(path, command))


if __name__ == "__main__":
    unittest.main()
