from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tools import (
    agent_cycle,
    agent_cycle_close,
    agent_cycle_obligation_inspect,
    agent_cycle_obligations,
    agent_cycle_resources,
    agent_write_lifecycle_guard,
    git_observation,
    project_machine,
    runtime_capabilities,
)
from tools.canonical import stable_hash
from tools.continuation_remote import ContinuationRemoteError

REPOSITORY = "EAKerber/MobiliPresenter"
CYCLE_ID = "cycle-instance-" + "a" * 24
WORK_ID = "m12-at3d-r3b2-test"
BRANCH = "work/operations/r3b2-test"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "r3b2-session",
}


def _origin(label: str = "r3b2") -> dict[str, object]:
    return agent_cycle_resources.origin(label, stable_hash({"label": label}), "observe")


def _resource(kind: str, locator: dict[str, object], label: str = "r3b2") -> dict[str, object]:
    return agent_cycle_resources.resource(kind, locator, _origin(label))


def _inventory(
    *,
    work: bool = False,
    branches: list[str] | None = None,
    lease_branches: list[str] | None = None,
) -> dict[str, object]:
    resources: list[dict[str, object]] = []
    for index, branch in enumerate(branches or []):
        resources.append(
            _resource(
                "git-branch",
                {"repository": REPOSITORY, "branch": branch},
                f"branch-{index}",
            )
        )
    for index, branch in enumerate(lease_branches or []):
        resources.append(
            _resource(
                "lease-scope",
                {
                    "repository": REPOSITORY,
                    "branch": branch,
                    "role": ACTOR["role"],
                    "sessionId": ACTOR["sessionId"],
                },
                f"lease-{index}",
            )
        )
    resource_set = agent_cycle_resources.build_resource_set(
        repository=REPOSITORY,
        cycle_instance_id=CYCLE_ID,
        resources=resources,
    )
    return agent_cycle_obligations.build_inventory(
        resource_set,
        work_ref={"workId": WORK_ID} if work else None,
    )


def _work_item(
    *,
    work_id: str = WORK_ID,
    branch: str | None = BRANCH,
    status: str = "IN_PROGRESS",
) -> dict[str, object]:
    return {
        "schemaVersion": "ContinuationState 0.2",
        "id": work_id,
        "workerId": "manager-gitops-a",
        "status": status,
        "branch": branch,
        "prNumber": None,
        "dependsOn": [],
        "completed": [],
        "remaining": [],
        "nextAction": None,
        "lastKnownGood": {"sha": None, "checkpoint": None},
        "blockers": [],
        "handoffToWorkerId": None,
    }


def _lease_report(state: str = "RELEASED") -> dict[str, object]:
    core = {
        "schemaVersion": agent_write_lifecycle_guard.REPORT_SCHEMA,
        "cycleInstanceId": CYCLE_ID,
        "actor": copy.deepcopy(ACTOR),
        "state": state,
        "latestBindingHash": "b" * 64 if state != "NONE" else None,
        "authorityHead": "c" * 40,
        "authorityNow": "2026-08-28T22:00:00Z",
        "matchingLeaseIds": [],
        "blockers": [],
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    value = {**core, "reportHash": stable_hash(core)}
    return agent_write_lifecycle_guard.validate_report(value)


def _context(work_ref: dict[str, str] | None) -> dict[str, object]:
    machine = project_machine.inspect_local()
    runtime = runtime_capabilities.build_inspection(
        {
            "schemaVersion": runtime_capabilities.PROVIDER_OBSERVATIONS_SCHEMA,
            "providers": {},
        }
    )
    profile = agent_cycle.entry_profile("manager-gitops", "inspect-and-plan")
    return agent_cycle.build_context(
        role="manager-gitops",
        declared_intent="inspect-and-plan",
        lifecycle_phase=profile["lifecyclePhase"],
        objects=profile["objects"],
        operations=profile["operations"],
        scopes=profile["scope"],
        machine=machine,
        runtime_inspection=runtime,
        work_ref=work_ref,
    )


class AgentCycleDispositionContractR3B2Tests(unittest.TestCase):
    def test_empty_inventory_builds_standalone_valid_pass_set_without_promoting_coverage(self):
        inventory = _inventory()
        value = agent_cycle_obligations.build_disposition_set(inventory, [])
        self.assertEqual("PASS", value["observationStatus"])
        self.assertEqual([], value["dispositions"])
        self.assertEqual("UNKNOWN", value["coverage"]["status"])
        self.assertFalse(value["enforcementEligible"])
        agent_cycle_obligations.validate_disposition_set(value)
        agent_cycle_obligations.validate_disposition_set(value, inventory)

    def test_set_requires_exactly_one_disposition_per_obligation_and_canonical_order(self):
        inventory = _inventory(work=True, branches=[BRANCH])
        obligations = {item["kind"]: item for item in inventory["obligations"]}
        work = agent_cycle_obligations.disposition(
            obligations["work-disposition"],
            observation_status="PASS",
            reason_codes=[],
            domain_state={
                "authorityHead": "1" * 40,
                "exists": True,
                "status": "IN_PROGRESS",
            },
        )
        branch = agent_cycle_obligations.disposition(
            obligations["git-branch-disposition"],
            observation_status="PASS",
            reason_codes=[],
            domain_state={
                "exists": True,
                "headSha": "2" * 40,
                "workAuthorityHead": "1" * 40,
                "activeWorkBindings": [
                    {
                        "workId": WORK_ID,
                        "workerId": "manager-gitops-a",
                        "status": "IN_PROGRESS",
                        "branch": BRANCH,
                        "prNumber": None,
                    }
                ],
            },
        )
        value = agent_cycle_obligations.build_disposition_set(
            inventory, [work, branch]
        )
        self.assertEqual(
            sorted(item["obligationHash"] for item in value["dispositions"]),
            [item["obligationHash"] for item in value["dispositions"]],
        )
        agent_cycle_obligations.validate_disposition_set(value)
        agent_cycle_obligations.validate_disposition_set(value, inventory)
        with self.assertRaisesRegex(
            RuntimeError, "AGENT_CYCLE_DISPOSITION_COVERAGE_INVALID"
        ):
            agent_cycle_obligations.build_disposition_set(inventory, [work])

    def test_rehashed_authority_or_enforcement_tampering_is_rejected(self):
        value = agent_cycle_obligations.build_disposition_set(_inventory(), [])
        for field in (
            "enforcementEligible",
            "semanticAuthority",
            "authorizesMutation",
        ):
            tampered = copy.deepcopy(value)
            tampered[field] = True
            body = {
                key: copy.deepcopy(item)
                for key, item in tampered.items()
                if key != "dispositionSetHash"
            }
            tampered["dispositionSetHash"] = stable_hash(body)
            with self.subTest(field=field):
                with self.assertRaisesRegex(
                    RuntimeError, "AGENT_CYCLE_DISPOSITION_SET_AUTHORITY_INVALID"
                ):
                    agent_cycle_obligations.validate_disposition_set(tampered)

    def test_cross_artifact_binding_rejects_another_inventory(self):
        first = _inventory(branches=[BRANCH])
        second = _inventory(branches=["work/operations/other"])
        obligation = first["obligations"][0]
        disposition = agent_cycle_obligations.disposition(
            obligation,
            observation_status="PASS",
            reason_codes=[],
            domain_state={
                "exists": False,
                "headSha": None,
                "workAuthorityHead": "1" * 40,
                "activeWorkBindings": [],
            },
        )
        value = agent_cycle_obligations.build_disposition_set(first, [disposition])
        with self.assertRaisesRegex(
            RuntimeError, "AGENT_CYCLE_DISPOSITION_SET_BINDING_MISMATCH"
        ):
            agent_cycle_obligations.validate_disposition_set(value, second)


class AgentCycleDispositionObserverR3B2Tests(unittest.TestCase):
    def _authority_patch(self, *, items: dict[str, dict[str, object]] | None = None):
        authority = Mock()
        authority.observe.return_value = SimpleNamespace(
            head_sha="1" * 40,
            items={} if items is None else items,
        )
        return patch(
            "tools.agent_cycle_obligation_inspect.GitHubContinuationAuthority",
            return_value=authority,
        ), authority

    def test_one_work_snapshot_serves_work_and_multiple_branch_obligations(self):
        inventory = _inventory(
            work=True,
            branches=[BRANCH, "work/operations/second"],
        )
        authority_patch, authority = self._authority_patch(
            items={WORK_ID: _work_item()}
        )
        with authority_patch, patch(
            "tools.agent_cycle_obligation_inspect.git_observation.ref_head",
            side_effect=["2" * 40, None],
        ):
            value = agent_cycle_obligation_inspect.inspect_inventory(
                inventory, transport=Mock()
            )
        self.assertEqual(1, authority.observe.call_count)
        self.assertEqual("PASS", value["observationStatus"])
        by_kind = {}
        for item in value["dispositions"]:
            by_kind.setdefault(item["kind"], []).append(item)
        self.assertEqual(
            "IN_PROGRESS",
            by_kind["work-disposition"][0]["domainState"]["status"],
        )
        branch_states = [item["domainState"] for item in by_kind["git-branch-disposition"]]
        self.assertEqual({False, True}, {state["exists"] for state in branch_states})
        self.assertEqual(
            1,
            sum(len(state["activeWorkBindings"]) for state in branch_states),
        )

    def test_successful_work_authority_absence_is_fact_not_unknown(self):
        inventory = _inventory(work=True)
        authority_patch, _ = self._authority_patch(items={})
        with authority_patch:
            value = agent_cycle_obligation_inspect.inspect_inventory(
                inventory, transport=Mock()
            )
        item = value["dispositions"][0]
        self.assertEqual("PASS", item["observationStatus"])
        self.assertFalse(item["domainState"]["exists"])
        self.assertIsNone(item["domainState"]["status"])

    def test_unavailable_work_authority_is_unknown_without_inference(self):
        inventory = _inventory(work=True)
        authority = Mock()
        authority.observe.side_effect = ContinuationRemoteError("TEST_WORK_DOWN")
        with patch(
            "tools.agent_cycle_obligation_inspect.GitHubContinuationAuthority",
            return_value=authority,
        ):
            value = agent_cycle_obligation_inspect.inspect_inventory(
                inventory, transport=Mock()
            )
        item = value["dispositions"][0]
        self.assertEqual("UNKNOWN", item["observationStatus"])
        self.assertEqual(
            [agent_cycle_obligation_inspect.WORK_UNAVAILABLE],
            item["reasonCodes"],
        )
        self.assertIsNone(item["domainState"]["authorityHead"])

    def test_git_ref_failure_is_unknown_and_missing_ref_is_factual_absence(self):
        inventory = _inventory(branches=[BRANCH])
        authority_patch, _ = self._authority_patch(items={})
        with authority_patch, patch(
            "tools.agent_cycle_obligation_inspect.git_observation.ref_head",
            return_value=None,
        ):
            absent = agent_cycle_obligation_inspect.inspect_inventory(
                inventory, transport=Mock()
            )
        absent_item = absent["dispositions"][0]
        self.assertEqual("PASS", absent_item["observationStatus"])
        self.assertFalse(absent_item["domainState"]["exists"])

        authority_patch, _ = self._authority_patch(items={})
        with authority_patch, patch(
            "tools.agent_cycle_obligation_inspect.git_observation.ref_head",
            side_effect=git_observation.GitObservationError("TEST_GIT_DOWN"),
        ):
            unknown = agent_cycle_obligation_inspect.inspect_inventory(
                inventory, transport=Mock()
            )
        unknown_item = unknown["dispositions"][0]
        self.assertEqual("UNKNOWN", unknown_item["observationStatus"])
        self.assertIn(
            agent_cycle_obligation_inspect.GIT_UNAVAILABLE,
            unknown_item["reasonCodes"],
        )

    def test_lifecycle_reuses_exact_report_and_multiple_scopes_are_explicitly_ambiguous(self):
        single = _inventory(lease_branches=[BRANCH])
        report = _lease_report("RELEASED")
        single_value = agent_cycle_obligation_inspect.inspect_inventory(
            single,
            lifecycle_report=report,
            transport=Mock(),
        )
        item = single_value["dispositions"][0]
        self.assertEqual("PASS", item["observationStatus"])
        self.assertEqual("RELEASED", item["domainState"]["state"])
        self.assertEqual(report["reportHash"], item["domainState"]["reportHash"])

        multiple = _inventory(
            lease_branches=[BRANCH, "work/operations/second"]
        )
        multiple_value = agent_cycle_obligation_inspect.inspect_inventory(
            multiple,
            lifecycle_report=report,
            transport=Mock(),
        )
        self.assertEqual("UNKNOWN", multiple_value["observationStatus"])
        self.assertEqual(2, len(multiple_value["dispositions"]))
        self.assertTrue(
            all(
                item["reasonCodes"]
                == [agent_cycle_obligation_inspect.LIFECYCLE_SCOPE_AMBIGUOUS]
                for item in multiple_value["dispositions"]
            )
        )


class AgentCycleCloseWorkBindingR3B2Tests(unittest.TestCase):
    def test_current_context_delta_rejects_work_drop_or_rebind(self):
        before = _context({"workId": WORK_ID})
        dropped = _context(None)
        with self.assertRaisesRegex(
            RuntimeError, "AGENT_CYCLE_CLOSE_WORK_REF_MISMATCH"
        ):
            agent_cycle_close.build_delta(before, dropped)

    def test_close_from_files_preserves_current_work_ref(self):
        before = _context({"workId": WORK_ID})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "context.json"
            path.write_text(
                json.dumps(before, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            with patch(
                "tools.agent_cycle_close._machine",
                return_value=copy.deepcopy(before["projectMachine"]),
            ), patch(
                "tools.agent_cycle_close._runtime_inspection",
                return_value=copy.deepcopy(before["runtimeCapabilities"]),
            ):
                closure = agent_cycle_close.close_from_files(
                    context_path=str(path),
                    machine_scope=before["projectMachine"]["scope"],
                )
        self.assertEqual(
            {"workId": WORK_ID}, closure["afterContext"]["workRef"]
        )
        agent_cycle_close.validate_closure(closure, before)


if __name__ == "__main__":
    unittest.main()
