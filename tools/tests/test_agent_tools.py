from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from tools import agent_cycle
from tools.agent_tools import contracts, policy, projection, resolver
from tools.semantics.registry import load_registry


def brief(*available: str):
    return {
        "capabilityProjection": {
            "required": [],
            "relevantAvailable": sorted(available),
            "conditional": [],
            "requiredUnavailable": [],
        }
    }


def context(role="manager-gitops", *, available=("project.inspect", "routine.inspect")):
    return {
        "contextHash": "b" * 64,
        "semanticContext": {"role": role, "declaredIntent": "inspect-and-plan"},
        "semanticBrief": brief(*available),
        "projectMachine": {"schemaVersion": "test-project-machine", "scope": "live"},
        "routineInspection": {"status": "PASS", "value": {"schemaVersion": "test-routine"}, "reasonCode": None},
    }


def request(tool_id, role="manager-gitops", *, target=None, input_value=None):
    actor = {
        "role": role,
        "workerId": "manager-gitops-a" if role == "manager-gitops" else "ui-ux-a",
        "sessionId": "session-1",
    }
    begin = {"runId": 123, "sourceSha": "a" * 40, "contextHash": "b" * 64}
    target = {} if target is None else target
    input_value = {} if input_value is None else input_value
    return {
        "schemaVersion": contracts.REQUEST_SCHEMA,
        "requestId": contracts.deterministic_request_id(
            begin=begin, actor=actor, tool_id=tool_id, target=target, input_value=input_value
        ),
        "begin": begin,
        "actor": actor,
        "toolId": tool_id,
        "target": target,
        "input": input_value,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


class AgentToolPolicyTests(unittest.TestCase):
    def test_current_policy_is_valid_and_entry_profiles_are_behavior_preserving(self):
        catalog = policy.load_policy()
        self.assertEqual(
            agent_cycle.entry_profile("manager-gitops", "bootstrap-discovery"),
            {
                "lifecyclePhase": "bootstrap",
                "objects": ["capability", "project-state", "repository"],
                "operations": ["bootstrap", "inspection", "repository-discovery"],
                "scope": ["repository:read"],
            },
        )
        self.assertEqual(
            agent_cycle.entry_profile("ui-ux", "inspect-and-plan"),
            {
                "lifecyclePhase": "bootstrap",
                "objects": ["artifact", "branch", "pull-request", "repository", "workflow"],
                "operations": ["inspection", "repository-discovery", "validation"],
                "scope": ["repository:read", "workflow:read"],
            },
        )
        self.assertEqual(catalog["schemaVersion"], policy.POLICY_SCHEMA)

    def test_projection_is_role_specific_without_resolver_role_branches(self):
        manager = projection.build_projection(
            {"role": "manager-gitops", "declaredIntent": "inspect-and-plan"}, brief("project.inspect", "routine.inspect")
        )
        self.assertEqual([item["toolId"] for item in manager["available"]], ["project.inspect", "routine.inspect"])
        self.assertEqual(
            [item["toolId"] for item in manager["plannable"]],
            ["git.file.create", "git.file.delete", "git.file.update"],
        )
        ui = projection.build_projection(
            {"role": "ui-ux", "declaredIntent": "inspect-and-plan"}, brief("project.inspect")
        )
        self.assertEqual([item["toolId"] for item in ui["available"]], ["project.inspect"])
        self.assertNotIn("routine.inspect", [item["toolId"] for item in ui["available"]])

    def test_third_role_can_be_added_by_policy_and_registry_data_only(self):
        registry = copy.deepcopy(load_registry())
        registry["facetVocabulary"]["roles"] = sorted(registry["facetVocabulary"]["roles"] + ["synthetic-engine"])
        registry["logicalCapabilities"]["project.inspect"]["facets"]["roles"] = sorted(
            registry["logicalCapabilities"]["project.inspect"]["facets"]["roles"] + ["synthetic-engine"]
        )
        catalog = copy.deepcopy(policy.load_policy())
        catalog["entryProfiles"]["synthetic-engine"] = copy.deepcopy(catalog["entryProfiles"]["ui-ux"])
        catalog["entryProfiles"] = dict(sorted(catalog["entryProfiles"].items()))
        roles = catalog["tools"]["project.inspect"]["roles"]
        roles["synthetic-engine"] = {
            "allowedIntents": ["inspect-and-plan"],
            "guards": [],
            "requiredCapabilities": ["project.inspect"],
            "targetPolicy": "none",
        }
        catalog["tools"]["project.inspect"]["roles"] = dict(sorted(roles.items()))
        policy.validate_policy(catalog, registry=registry)
        result = projection.build_projection(
            {"role": "synthetic-engine", "declaredIntent": "inspect-and-plan"},
            brief("project.inspect"),
            policy=catalog,
            registry=registry,
        )
        self.assertEqual([item["toolId"] for item in result["available"]], ["project.inspect"])


class AgentToolResolverTests(unittest.TestCase):
    @patch("tools.agent_tools.adapters.remote_git_file._observe_blob", return_value=("c" * 40, None))
    def test_ui_git_create_builds_valid_plan_without_writing(self, observe):
        value = request(
            "git.file.create",
            "ui-ux",
            target={"branch": "work/ui/at1", "path": "docs/ui/at1.json"},
            input_value={"content": "{}\n", "message": "AT1 plan"},
        )
        resolved = resolver.resolve_request(value, context("ui-ux", available=("project.inspect",)))
        self.assertEqual(resolved["result"]["status"], "PLANNED")
        command = resolved["plan"]["concrete"]["command"]
        self.assertEqual(command["target"]["operation"], "create-file")
        self.assertEqual(command["expected"]["branchHead"], "c" * 40)
        self.assertFalse(resolved["plan"]["concrete"]["mutationEnabled"])
        observe.assert_called_once()

    @patch("tools.agent_tools.adapters.remote_git_file._observe_blob")
    def test_ui_scope_blocks_before_git_observation(self, observe):
        value = request(
            "git.file.create",
            "ui-ux",
            target={"branch": "work/ui/at1", "path": "viewer-next/src/api/forbidden.ts"},
            input_value={"content": "x", "message": "forbidden"},
        )
        with self.assertRaisesRegex(RuntimeError, "AGENT_TOOL_TARGET_PATH_FORBIDDEN"):
            resolver.resolve_request(value, context("ui-ux", available=("project.inspect",)))
        observe.assert_not_called()

    def test_project_inspect_executes_read_only_through_same_interface(self):
        value = request("project.inspect", target={}, input_value={})
        resolved = resolver.resolve_request(value, context())
        self.assertEqual(resolved["result"]["status"], "PASS")
        self.assertEqual(resolved["result"]["value"]["schemaVersion"], "test-project-machine")
        self.assertTrue(resolved["plan"]["readOnly"])
        self.assertFalse(resolved["plan"]["authorizesMutation"])


if __name__ == "__main__":
    unittest.main()
