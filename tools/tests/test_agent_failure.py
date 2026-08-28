from __future__ import annotations

import copy
import json
import unittest

from tools import (
    agent_failure,
    agent_write_lifecycle,
    hosted_agent_tool,
    remote_canonical_issue,
)
from tools.canonical import stable_hash
from tools.semantics.registry import ROOT, load_registry, validate_registry


def _rehash(value: dict) -> dict:
    core = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "failureCoreHash"
    }
    value["failureCoreHash"] = stable_hash(core)
    return value


def _legacy_hosted_cycle_failure(
    code: str = "HOSTED_AGENT_BEGIN_NOT_READY",
) -> dict:
    body = {
        "schemaVersion": "HostedAgentCycleFailure 0.1",
        "requestId": None,
        "commandHash": None,
        "status": "BLOCKED",
        "blockers": [code],
        "detail": code,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "failureHash": stable_hash(body)}


def _hosted_cycle_v02(core: dict, *, correlated: bool = False) -> dict:
    body = {
        "schemaVersion": agent_failure.HOSTED_CYCLE_FAILURE_SCHEMA,
        "requestId": "hosted-cycle-1" if correlated else None,
        "commandHash": "a" * 64 if correlated else None,
        "status": "BLOCKED",
        "failureCore": copy.deepcopy(core),
    }
    return {**body, "failureHash": stable_hash(body)}


class AgentFailureCoreTests(unittest.TestCase):
    def build_core(self) -> dict:
        return agent_failure.build_failure_core(
            surface="AGENT_CYCLE",
            phase="BEGIN",
            status="BLOCKED",
            causes=[
                {
                    "code": "ROOT_PROVIDER_SCOPE_MISSING",
                    "source": "agent-cycle",
                    "phase": "RESOLVE",
                },
                {
                    "code": "HOSTED_AGENT_BEGIN_NOT_READY",
                    "source": "hosted-agent-cycle",
                    "phase": "BEGIN",
                },
            ],
            observation_retry="SAFE",
            operation_replay="NOT_APPLICABLE",
            mutation_state="NOT_APPLICABLE",
        )

    def test_core_is_registered_and_structurally_aligned(self):
        registry = load_registry()
        self.assertEqual([], validate_registry(registry))
        contract = registry["contracts"]["agent-failure-core"]
        self.assertEqual(
            "tools.agent_failure.validate_failure_core",
            contract["semanticValidator"],
        )
        self.assertEqual(
            "ops/schemas/agent-failure-core.schema.json",
            contract["structuralSchema"],
        )
        schema = json.loads(
            (ROOT / contract["structuralSchema"]).read_text(encoding="utf-8")
        )
        self.assertEqual(agent_failure.FAILURE_CORE_SCHEMA, schema["title"])
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(agent_failure.FAILURE_CORE_FIELDS, set(schema["properties"]))
        self.assertEqual(agent_failure.FAILURE_CORE_FIELDS, set(schema["required"]))

    def test_core_preserves_root_to_wrapper_order_and_hash(self):
        value = self.build_core()
        self.assertEqual(
            [
                "ROOT_PROVIDER_SCOPE_MISSING",
                "HOSTED_AGENT_BEGIN_NOT_READY",
            ],
            [item["code"] for item in value["causes"]],
        )
        self.assertTrue(value["readOnly"])
        self.assertFalse(value["semanticAuthority"])
        self.assertFalse(value["authorizesMutation"])
        self.assertEqual(value, agent_failure.validate_failure_core(value))
        core = {key: item for key, item in value.items() if key != "failureCoreHash"}
        self.assertEqual(stable_hash(core), value["failureCoreHash"])

    def test_boundary_tamper_is_rejected_even_when_rehashed(self):
        value = self.build_core()
        value["authorizesMutation"] = True
        _rehash(value)
        with self.assertRaisesRegex(
            agent_failure.AgentFailureError, "AGENT_FAILURE_CORE_BOUNDARY_INVALID"
        ):
            agent_failure.validate_failure_core(value)

    def test_post_write_ambiguity_cannot_be_blocked_or_safe_to_replay(self):
        with self.assertRaisesRegex(
            agent_failure.AgentFailureError,
            "AGENT_FAILURE_CORE_POST_WRITE_STATUS_INVALID",
        ):
            agent_failure.build_failure_core(
                surface="REMOTE_CANONICAL",
                phase="READBACK",
                status="BLOCKED",
                causes=[{
                    "code": "TRANSPORT_DROPPED_AFTER_WRITE",
                    "source": "remote-canonical",
                    "phase": "READBACK",
                }],
                observation_retry="SAFE",
                operation_replay="UNKNOWN",
                mutation_state="UNKNOWN",
            )

        with self.assertRaisesRegex(
            agent_failure.AgentFailureError,
            "AGENT_FAILURE_CORE_REPLAY_UNSAFE_STATE",
        ):
            agent_failure.build_failure_core(
                surface="REMOTE_CANONICAL",
                phase="READBACK",
                status="UNKNOWN",
                causes=[{
                    "code": "TRANSPORT_DROPPED_AFTER_WRITE",
                    "source": "remote-canonical",
                    "phase": "READBACK",
                }],
                observation_retry="SAFE",
                operation_replay="SAFE",
                mutation_state="UNKNOWN",
            )

    def test_duplicate_cause_is_rejected(self):
        value = self.build_core()
        value["causes"].append(copy.deepcopy(value["causes"][0]))
        _rehash(value)
        with self.assertRaisesRegex(
            agent_failure.AgentFailureError, "AGENT_FAILURE_CORE_CAUSES_DUPLICATE"
        ):
            agent_failure.validate_failure_core(value)


class AgentFailureHostedCycleV02Tests(unittest.TestCase):
    def build_core(self, *, phase: str = "BEGIN") -> dict:
        return agent_failure.build_failure_core(
            surface="AGENT_CYCLE",
            phase=phase,
            status="BLOCKED",
            causes=[{
                "code": "HOSTED_AGENT_BEGIN_NOT_READY",
                "source": "hosted-agent-cycle",
                "phase": phase,
            }],
            observation_retry="UNKNOWN",
            operation_replay="NOT_APPLICABLE",
            mutation_state="NOT_APPLICABLE",
            lossy_projection=True,
        )

    def test_v02_returns_embedded_core_without_external_phase(self):
        core = self.build_core()
        value = _hosted_cycle_v02(core, correlated=True)
        self.assertEqual(value, agent_failure.validate_hosted_cycle_failure(value))
        self.assertEqual(core, agent_failure.normalize_failure(value))
        self.assertEqual(core, agent_failure.normalize_failure(value, phase="BEGIN"))

    def test_v02_phase_mismatch_is_rejected(self):
        value = _hosted_cycle_v02(self.build_core())
        with self.assertRaisesRegex(
            agent_failure.AgentFailureError, "AGENT_FAILURE_CORE_PHASE_MISMATCH"
        ):
            agent_failure.normalize_failure(value, phase="CLOSE")

    def test_v02_shell_tamper_is_rejected(self):
        value = _hosted_cycle_v02(self.build_core())
        value["failureCore"]["lossyProjection"] = False
        with self.assertRaisesRegex(
            agent_failure.AgentFailureError, "AGENT_FAILURE_CORE_HASH_MISMATCH"
        ):
            agent_failure.validate_hosted_cycle_failure(value)

    def test_v02_correlation_is_all_or_nothing(self):
        value = _hosted_cycle_v02(self.build_core())
        value["requestId"] = "partial-correlation"
        value["failureHash"] = stable_hash(
            {key: item for key, item in value.items() if key != "failureHash"}
        )
        with self.assertRaisesRegex(
            agent_failure.AgentFailureError, "HOSTED_AGENT_FAILURE_CORRELATION_INVALID"
        ):
            agent_failure.validate_hosted_cycle_failure(value)


class AgentFailureLegacyNormalizationTests(unittest.TestCase):
    def test_hosted_cycle_literal_v01_is_readable_without_inferred_retry(self):
        legacy = _legacy_hosted_cycle_failure()
        core = agent_failure.normalize_failure(legacy, phase="BEGIN")
        self.assertEqual("AGENT_CYCLE", core["surface"])
        self.assertEqual("BLOCKED", core["status"])
        self.assertEqual("NOT_APPLICABLE", core["mutationState"])
        self.assertEqual("UNKNOWN", core["recovery"]["observationRetry"])
        self.assertEqual("NOT_APPLICABLE", core["recovery"]["operationReplay"])
        self.assertEqual(
            ["HOSTED_AGENT_BEGIN_NOT_READY"],
            [item["code"] for item in core["causes"]],
        )
        self.assertTrue(core["lossyProjection"])

    def test_each_current_failure_carrier_has_a_fail_closed_projection(self):
        cases = [
            (
                hosted_agent_tool.failure_payload(
                    hosted_agent_tool.HostedAgentToolError("HOSTED_AGENT_TOOL_BLOCKED")
                ),
                "ADMIT",
                "AGENT_TOOL",
                "BLOCKED",
                "NOT_APPLIED",
            ),
            (
                remote_canonical_issue.failure_payload(
                    remote_canonical_issue.RemoteCanonicalExecutionError(
                        "REMOTE_CANONICAL_EXECUTION_FAILED"
                    )
                ),
                "APPLY",
                "REMOTE_CANONICAL",
                "UNKNOWN",
                "UNKNOWN",
            ),
            (
                agent_write_lifecycle.build_failure(
                    None,
                    status="UNKNOWN",
                    blockers=["TRANSPORT_DROPPED_AFTER_WRITE"],
                ),
                "READBACK",
                "AGENT_WRITE_LEASE",
                "UNKNOWN",
                "UNKNOWN",
            ),
        ]
        for legacy, phase, surface, status, mutation_state in cases:
            with self.subTest(schema=legacy["schemaVersion"]):
                core = agent_failure.normalize_failure(legacy, phase=phase)
                self.assertEqual(surface, core["surface"])
                self.assertEqual(status, core["status"])
                self.assertEqual(mutation_state, core["mutationState"])
                self.assertEqual("UNKNOWN", core["recovery"]["observationRetry"])
                self.assertEqual("UNKNOWN", core["recovery"]["operationReplay"])
                self.assertTrue(core["lossyProjection"])

    def test_legacy_hash_and_closed_fields_are_required(self):
        legacy = _legacy_hosted_cycle_failure("EXPECTED_FAILURE")
        legacy["failureHash"] = ""
        with self.assertRaisesRegex(
            agent_failure.AgentFailureError, "AGENT_FAILURE_LEGACY_HASH_INVALID"
        ):
            agent_failure.normalize_failure(legacy, phase="BEGIN")

        legacy = _legacy_hosted_cycle_failure("EXPECTED_FAILURE")
        legacy["unexpected"] = True
        legacy["failureHash"] = stable_hash(
            {key: item for key, item in legacy.items() if key != "failureHash"}
        )
        with self.assertRaisesRegex(
            agent_failure.AgentFailureError, "AGENT_FAILURE_LEGACY_FIELDS_INVALID"
        ):
            agent_failure.normalize_failure(legacy, phase="BEGIN")

    def test_legacy_phase_is_never_inferred(self):
        legacy = _legacy_hosted_cycle_failure("EXPECTED_FAILURE")
        with self.assertRaisesRegex(
            agent_failure.AgentFailureError, "AGENT_FAILURE_LEGACY_PHASE_REQUIRED"
        ):
            agent_failure.normalize_failure(legacy)


if __name__ == "__main__":
    unittest.main()
