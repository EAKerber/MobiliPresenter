from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools import (
    agent_cycle,
    agent_cycle_obligations,
    agent_cycle_resources,
    continuation,
    hosted_agent_cycle_trace,
    project_machine,
    runtime_capabilities,
)
from tools.canonical import stable_hash
from tools.semantics import registry

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "EAKerber/MobiliPresenter"
CYCLE_INSTANCE_ID = "cycle-instance-106d282fa4a74ea8a0330c37"
WORK_ID = "m12-at3d-r3b1-test"
RESOURCE_SCHEMA_PATH = ROOT / "ops" / "schemas" / "agent-cycle-touched-resource-set.schema.json"
OBLIGATION_SCHEMA_PATH = ROOT / "ops" / "schemas" / "agent-cycle-obligation-inventory.schema.json"


def _origin(source: str = "test", operation: str = "observe") -> dict[str, object]:
    return agent_cycle_resources.origin(
        source,
        stable_hash({"source": source, "operation": operation}),
        operation,
    )


def _resource_set(resources: list[dict[str, object]] | None = None) -> dict[str, object]:
    return agent_cycle_resources.build_resource_set(
        repository=REPOSITORY,
        cycle_instance_id=CYCLE_INSTANCE_ID,
        resources=[] if resources is None else resources,
    )


def _context(work_ref: dict[str, str] | None = None) -> dict[str, object]:
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


def _manifest() -> dict[str, object]:
    return {
        "schemaVersion": "HostedAgentCycleBeginManifest 0.3",
        "requestId": "begin-r3b1",
        "commandHash": "c" * 64,
        "actor": {
            "role": "manager-gitops",
            "workerId": "manager-gitops-a",
            "sessionId": "r3b1-test",
        },
        "declaredIntent": "inspect-and-plan",
        "machineScope": "live",
        "source": {
            "workflow": "hosted-agent-cycle",
            "runId": 123,
            "sourceSha": "b" * 40,
            "issueNumber": 145,
            "commentId": 100,
        },
        "artifactName": "agent-cycle-begin-123",
        "cycleId": "cycle-" + "d" * 20,
        "cycleInstanceId": CYCLE_INSTANCE_ID,
        "contextHash": "e" * 64,
        "carrierFeatures": [
            "agent-write-lease-lifecycle-0.1",
            "execution-trace-0.1",
        ],
        "status": "READY",
        "semanticAuthority": False,
        "authorizesMutation": False,
        "manifestHash": "f" * 64,
    }


def _comments() -> list[dict[str, object]]:
    return [
        {
            "id": 100,
            "author_association": "OWNER",
            "user": {"login": "EAKerber"},
            "body": "begin",
        },
        {
            "id": 200,
            "author_association": "OWNER",
            "user": {"login": "EAKerber"},
            "body": "close",
        },
    ]


class AgentCycleObligationR3B1Tests(unittest.TestCase):
    def test_public_contracts_are_registered_and_structurally_aligned(self):
        resource_schema = json.loads(RESOURCE_SCHEMA_PATH.read_text(encoding="utf-8"))
        obligation_schema = json.loads(OBLIGATION_SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(agent_cycle_resources.SCHEMA_VERSION, resource_schema["title"])
        self.assertEqual(
            agent_cycle_resources.SET_FIELDS, set(resource_schema["required"])
        )
        self.assertEqual(
            agent_cycle_resources.SET_FIELDS, set(resource_schema["properties"])
        )
        self.assertFalse(resource_schema["additionalProperties"])
        self.assertEqual(
            agent_cycle_resources.COVERAGE_FIELDS,
            set(resource_schema["properties"]["coverage"]["required"]),
        )
        self.assertEqual(
            agent_cycle_resources.coverage()["status"],
            resource_schema["properties"]["coverage"]["properties"]["status"]["const"],
        )
        self.assertEqual(
            agent_cycle_resources.coverage()["scope"],
            resource_schema["properties"]["coverage"]["properties"]["scope"]["const"],
        )
        self.assertEqual(
            agent_cycle_resources.coverage()["reasonCode"],
            resource_schema["properties"]["coverage"]["properties"]["reasonCode"]["const"],
        )

        resource_defs = resource_schema["$defs"]
        schema_resource_kinds = {
            resource_defs[ref["$ref"].split("/")[-1]]["properties"]["kind"]["const"]
            for ref in resource_defs["resource"]["oneOf"]
        }
        self.assertEqual(agent_cycle_resources.RESOURCE_KINDS, schema_resource_kinds)

        self.assertEqual(
            agent_cycle_obligations.SCHEMA_VERSION, obligation_schema["title"]
        )
        self.assertEqual(
            agent_cycle_obligations.INVENTORY_FIELDS,
            set(obligation_schema["required"]),
        )
        self.assertEqual(
            agent_cycle_obligations.INVENTORY_FIELDS,
            set(obligation_schema["properties"]),
        )
        self.assertFalse(obligation_schema["additionalProperties"])
        work_specs = [
            item
            for item in obligation_schema["properties"]["workRef"]["oneOf"]
            if item.get("type") == "object"
        ]
        self.assertEqual(1, len(work_specs))
        self.assertEqual(
            continuation.ID_RE.pattern,
            work_specs[0]["properties"]["workId"]["pattern"],
        )

        obligation_defs = obligation_schema["$defs"]
        schema_obligation_kinds = {
            obligation_defs[ref["$ref"].split("/")[-1]]["properties"]["kind"]["const"]
            for ref in obligation_defs["obligation"]["oneOf"]
        }
        self.assertEqual(
            agent_cycle_obligations.OBLIGATION_KINDS, schema_obligation_kinds
        )

        live = registry.load_registry()
        self.assertEqual(
            "tools.agent_cycle_resources.validate_resource_set",
            live["contracts"]["agent-cycle-touched-resource-set"]["semanticValidator"],
        )
        self.assertEqual(
            "tools.agent_cycle_obligations.validate_inventory",
            live["contracts"]["agent-cycle-obligation-inventory"]["semanticValidator"],
        )
        component = live["components"]["agent-cycle-resource-collector"]
        self.assertEqual([], component["writesAuthorities"])
        self.assertEqual([], component["writesResources"])
        self.assertFalse(component["sideEffects"])

    def test_branch_paths_work_and_lease_collapse_to_three_bounded_obligations(self):
        source = _origin()
        resources = [
            agent_cycle_resources.resource(
                "git-branch",
                {"repository": REPOSITORY, "branch": "work/operations/example"},
                source,
            ),
            agent_cycle_resources.resource(
                "git-path",
                {
                    "repository": REPOSITORY,
                    "branch": "work/operations/example",
                    "path": "docs/a.md",
                },
                source,
            ),
            agent_cycle_resources.resource(
                "git-path",
                {
                    "repository": REPOSITORY,
                    "branch": "work/operations/example",
                    "path": "docs/b.md",
                },
                source,
            ),
            agent_cycle_resources.resource(
                "domain-subject",
                {
                    "domain": "continuation",
                    "subjectKind": "continuation",
                    "subjectId": WORK_ID,
                },
                source,
            ),
            agent_cycle_resources.resource(
                "lease-scope",
                {
                    "repository": REPOSITORY,
                    "branch": "work/operations/example",
                    "role": "manager-gitops",
                    "sessionId": "session-1",
                },
                source,
            ),
            agent_cycle_resources.resource(
                "coordination-lease",
                {"leaseId": "lease-one"},
                source,
            ),
        ]
        resource_set = _resource_set(resources)
        inventory = agent_cycle_obligations.build_inventory(
            resource_set, work_ref={"workId": WORK_ID}
        )
        agent_cycle_obligations.validate_inventory(
            inventory, resource_set, work_ref={"workId": WORK_ID}
        )

        self.assertEqual(3, len(inventory["obligations"]))
        by_kind = {item["kind"]: item for item in inventory["obligations"]}
        self.assertEqual(
            {"repository": REPOSITORY, "branch": "work/operations/example"},
            by_kind["git-branch-disposition"]["locator"],
        )
        self.assertEqual(
            {"workId": WORK_ID}, by_kind["work-disposition"]["locator"]
        )
        self.assertEqual(
            {
                "repository": REPOSITORY,
                "branch": "work/operations/example",
                "role": "manager-gitops",
                "sessionId": "session-1",
            },
            by_kind["write-lifecycle-disposition"]["locator"],
        )
        self.assertFalse(inventory["enforcementEligible"])
        self.assertEqual(resource_set["coverage"], inventory["coverage"])

    def test_generic_domain_subject_and_coordination_lease_do_not_invent_obligations(self):
        source = _origin()
        resource_set = _resource_set(
            [
                agent_cycle_resources.resource(
                    "domain-subject",
                    {
                        "domain": "project-state",
                        "subjectKind": "checkpoint",
                        "subjectId": "next",
                    },
                    source,
                ),
                agent_cycle_resources.resource(
                    "coordination-lease",
                    {"leaseId": "lease-one"},
                    source,
                ),
            ]
        )
        inventory = agent_cycle_obligations.build_inventory(resource_set)
        self.assertEqual([], inventory["obligations"])
        self.assertFalse(inventory["enforcementEligible"])

    def test_rehashed_enforcement_or_authority_tamper_is_rejected(self):
        inventory = agent_cycle_obligations.build_inventory(
            _resource_set(), work_ref={"workId": WORK_ID}
        )
        for field in (
            "enforcementEligible",
            "semanticAuthority",
            "authorizesMutation",
        ):
            tampered = copy.deepcopy(inventory)
            tampered[field] = True
            body = {
                key: copy.deepcopy(value)
                for key, value in tampered.items()
                if key != "inventoryHash"
            }
            tampered["inventoryHash"] = stable_hash(body)
            with self.subTest(field=field):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "AGENT_CYCLE_OBLIGATION_INVENTORY_AUTHORITY_INVALID",
                ):
                    agent_cycle_obligations.validate_inventory(tampered)

    def test_cross_artifact_binding_rejects_another_resource_set(self):
        branch = agent_cycle_resources.resource(
            "git-branch",
            {"repository": REPOSITORY, "branch": "work/operations/one"},
            _origin("one"),
        )
        other = agent_cycle_resources.resource(
            "git-branch",
            {"repository": REPOSITORY, "branch": "work/operations/two"},
            _origin("two"),
        )
        first = _resource_set([branch])
        second = _resource_set([other])
        inventory = agent_cycle_obligations.build_inventory(first)
        with self.assertRaisesRegex(
            RuntimeError,
            "AGENT_CYCLE_OBLIGATION_INVENTORY_BINDING_MISMATCH",
        ):
            agent_cycle_obligations.validate_inventory(inventory, second)

    def test_work_id_shape_matches_runtime_and_schema(self):
        good = {"workId": WORK_ID}
        self.assertEqual(good, agent_cycle.validate_work_ref(good))
        with self.assertRaisesRegex(RuntimeError, "AGENT_CYCLE_WORK_ID_INVALID"):
            agent_cycle.validate_work_ref({"workId": "bad_work"})
        schema = json.loads(OBLIGATION_SCHEMA_PATH.read_text(encoding="utf-8"))
        work_spec = next(
            item
            for item in schema["properties"]["workRef"]["oneOf"]
            if item.get("type") == "object"
        )
        self.assertEqual(
            continuation.ID_RE.pattern,
            work_spec["properties"]["workId"]["pattern"],
        )

    def test_hosted_shadow_materializes_inventory_from_same_comment_observation(self):
        comments = _comments()
        fetcher = Mock(return_value=comments)
        command = {"evidenceCommentIds": []}
        meta = {"issueNumber": 145, "commentId": 200}
        context = _context({"workId": WORK_ID})
        with tempfile.TemporaryDirectory() as directory:
            resource_path = Path(directory) / "agent-cycle-touched-resources.json"
            obligation_path = Path(directory) / "agent-cycle-obligation-inventory.json"
            amended, trace = hosted_agent_cycle_trace.prepare_close_stabilized(
                command,
                meta,
                _manifest(),
                context,
                repository=REPOSITORY,
                fetch_comments=fetcher,
                sleep=lambda _seconds: None,
                attempts=1,
                resource_output_path=str(resource_path),
                obligation_output_path=str(obligation_path),
            )
            resource_set = json.loads(resource_path.read_text(encoding="utf-8"))
            inventory = json.loads(obligation_path.read_text(encoding="utf-8"))

        self.assertEqual(1, fetcher.call_count)
        self.assertEqual(command, amended)
        self.assertEqual("PASS", trace["traceStatus"])
        agent_cycle_resources.validate_resource_set(resource_set)
        agent_cycle_obligations.validate_inventory(
            inventory, resource_set, work_ref={"workId": WORK_ID}
        )
        self.assertEqual({"workId": WORK_ID}, inventory["workRef"])
        self.assertFalse(inventory["enforcementEligible"])

    def test_shadow_failure_cannot_change_close_trace_result(self):
        comments = _comments()
        fetcher = Mock(return_value=comments)
        command = {"evidenceCommentIds": []}
        meta = {"issueNumber": 145, "commentId": 200}
        with tempfile.TemporaryDirectory() as directory:
            resource_path = Path(directory) / "agent-cycle-touched-resources.json"
            obligation_path = Path(directory) / "agent-cycle-obligation-inventory.json"
            with patch(
                "tools.agent_cycle_resource_collect.build_obligation_inventory",
                side_effect=RuntimeError("R3B1_SHADOW_TEST_FAILURE"),
            ):
                amended, trace = hosted_agent_cycle_trace.prepare_close_stabilized(
                    command,
                    meta,
                    _manifest(),
                    {},
                    repository=REPOSITORY,
                    fetch_comments=fetcher,
                    sleep=lambda _seconds: None,
                    attempts=1,
                    resource_output_path=str(resource_path),
                    obligation_output_path=str(obligation_path),
                )
            resource_error = json.loads(
                resource_path.with_suffix(".json.error.json").read_text(
                    encoding="utf-8"
                )
            )
            obligation_error = json.loads(
                obligation_path.with_suffix(".json.error.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(1, fetcher.call_count)
        self.assertEqual(command, amended)
        self.assertEqual("PASS", trace["traceStatus"])
        self.assertEqual("R3B1_SHADOW_TEST_FAILURE", resource_error["error"])
        self.assertEqual("R3B1_SHADOW_TEST_FAILURE", obligation_error["error"])


if __name__ == "__main__":
    unittest.main()
