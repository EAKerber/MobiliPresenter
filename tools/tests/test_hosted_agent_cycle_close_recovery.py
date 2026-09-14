import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import hosted_agent_cycle as hosted
from tools import hosted_agent_cycle_close_recovery as recovery


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

    def test_compatibility_source_must_match_request_and_hash(self):
        command = {
            "schemaVersion": "HostedAgentCycleCommand 0.2",
            "requestId": "close-r0-2",
            "action": "close",
            "handle": mock.ANY,
            "evidenceCommentIds": [],
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        failure = {
            "schemaVersion": "HostedAgentCycleFailure 0.2",
            "requestId": "close-r0-2",
            "commandHash": "h" * 64,
            "status": "BLOCKED",
            "failureCore": self.exact_failure_core(),
        }
        failure["failureHash"] = hosted.stable_hash({key: value for key, value in failure.items() if key != "failureHash"})
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "compatibility-recovery-source.json"
            path.write_text(json.dumps(failure), encoding="utf-8")
            with mock.patch.object(recovery.hosted, "transport_command_hash", return_value="h" * 64), \
                 mock.patch.object(recovery.hosted, "validate_transport_command", return_value=command), \
                 mock.patch.object(recovery.agent_failure, "validate_hosted_cycle_failure", return_value=failure):
                self.assertTrue(recovery._compatibility_source_allows(path, command))
            failure["requestId"] = "other"
            path.write_text(json.dumps(failure), encoding="utf-8")
            with mock.patch.object(recovery.agent_failure, "validate_hosted_cycle_failure", return_value=failure), \
                 mock.patch.object(recovery.hosted, "transport_command_hash", return_value="h" * 64):
                self.assertFalse(recovery._compatibility_source_allows(path, command))

    def test_exact_failure_routes_through_recovery_and_persists_evidence(self):
        command = {"requestId": "close-r0-2"}
        meta = {"issueNumber": 145, "commentId": 1}
        original_error = hosted.HostedAgentCycleError(
            "HOSTED_AGENT_CLOSE_NOT_PASS",
            failure_core=self.exact_failure_core(),
        )
        recovered_closure = {
            "cycleId": "cycle-test",
            "status": "PASS",
            "receipt": {"receiptHash": "r" * 64},
            "closureHash": "c" * 64,
        }
        with tempfile.TemporaryDirectory() as root:
            begin = Path(root) / "begin"
            close = Path(root) / "close"
            evidence = Path(root) / "evidence"
            begin.mkdir(); close.mkdir(); evidence.mkdir()
            (begin / "context.json").write_text("{}", encoding="utf-8")
            (begin / "manifest.json").write_text(json.dumps({
                "source": {"runId": 123},
                "contextHash": "x" * 64,
            }), encoding="utf-8")
            (close / "compatibility-recovery-source.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(recovery.hosted, "validate_transport_command", return_value=command), \
                 mock.patch.object(recovery.hosted, "close_from_envelope", side_effect=original_error), \
                 mock.patch.object(recovery, "_compatibility_source_allows", return_value=True), \
                 mock.patch.object(recovery, "_load", side_effect=lambda path: recovered_closure if str(path).endswith("closure.json") else ({"source": {"runId": 123}, "contextHash": "x" * 64} if str(path).endswith("manifest.json") else {})), \
                 mock.patch.object(recovery.agent_cycle_close_recovery, "recover_closure", return_value=recovered_closure) as recover_call, \
                 mock.patch.object(recovery.agent_cycle_close, "load_evidence", return_value=[]), \
                 mock.patch.object(recovery.agent_cycle_close, "validate_closure"), \
                 mock.patch.object(recovery, "_hosted_close_result", return_value={"status": "PASS"}):
                recovery_path = evidence / "evidence-recovery-merge.json"
                def materialize(*args, **kwargs):
                    Path(kwargs["recovery_evidence_path"]).write_text("{}", encoding="utf-8")
                    return recovered_closure
                recover_call.side_effect = materialize
                result = recovery.close_with_compatibility_recovery(
                    command, meta,
                    begin_dir=str(begin),
                    output_path=str(close / "closure.json"),
                    evidence_dir=str(evidence),
                )
                self.assertEqual(result["status"], "PASS")
                self.assertTrue(recovery_path.is_file())

    def test_missing_compatibility_source_fails_closed(self):
        original_error = hosted.HostedAgentCycleError(
            "HOSTED_AGENT_CLOSE_NOT_PASS",
            failure_core=self.exact_failure_core(),
        )
        with tempfile.TemporaryDirectory() as root, \
             mock.patch.object(recovery.hosted, "validate_transport_command", return_value={"requestId": "x"}), \
             mock.patch.object(recovery.hosted, "close_from_envelope", side_effect=original_error):
            with self.assertRaises(hosted.HostedAgentCycleError):
                recovery.close_with_compatibility_recovery(
                    {"requestId": "x"}, {},
                    begin_dir=root,
                    output_path=str(Path(root) / "closure.json"),
                    evidence_dir=str(Path(root) / "evidence"),
                )


if __name__ == "__main__":
    unittest.main()
