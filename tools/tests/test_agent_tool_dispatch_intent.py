from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.agent_tools import dispatch_host


CATALOG = {
    "targetPolicies": {
        "manager-non-control-git": {
            "kind": "git-file",
            "branchPrefixes": [],
            "forbiddenBranches": ["main"],
            "pathPrefixes": [],
        }
    },
    "tools": {
        "git.file.create": {
            "adapter": "remote-git-file",
            "effectClass": "shared-durable-mutation",
            "mode": "plan-only",
            "roles": {
                "manager-gitops": {
                    "allowedIntents": ["governed-mutation", "inspect-and-plan"],
                    "guards": ["coordination-lease-owned", "git-cas"],
                    "modesByIntent": {"governed-mutation": "mutation-execute"},
                    "requiredCapabilities": ["remote.canonical.execute"],
                    "targetPolicy": "manager-non-control-git",
                }
            },
        }
    },
}

PLAN = {
    "actor": {
        "role": "manager-gitops",
        "workerId": "manager-gitops-a",
        "sessionId": "session-1",
    },
    "toolId": "git.file.create",
    "effectClass": "shared-durable-mutation",
    "adapter": "remote-git-file",
    "guards": ["coordination-lease-owned", "git-cas"],
    "requiredCapabilities": ["remote.canonical.execute"],
    "targetPolicy": "manager-non-control-git",
    "target": {"branch": "work/operations/test", "path": "docs/test.txt"},
}


class AgentToolDispatchIntentTests(unittest.TestCase):
    @patch("tools.agent_tools.dispatch_host.validate_target")
    @patch("tools.agent_tools.dispatch_host.tool_policy.load_policy", return_value=CATALOG)
    def test_current_policy_uses_governed_mutation_intent_for_effective_mode(
        self, load_policy, validate_target
    ):
        context = {
            "semanticContext": {
                "role": "manager-gitops",
                "declaredIntent": "governed-mutation",
            }
        }
        dispatch_host._validate_current_policy(PLAN, context)
        load_policy.assert_called_once_with()
        validate_target.assert_called_once()

    @patch("tools.agent_tools.dispatch_host.validate_target")
    @patch("tools.agent_tools.dispatch_host.tool_policy.load_policy", return_value=CATALOG)
    def test_current_policy_rejects_plan_only_intent_for_dispatch(
        self, load_policy, validate_target
    ):
        context = {
            "semanticContext": {
                "role": "manager-gitops",
                "declaredIntent": "inspect-and-plan",
            }
        }
        with self.assertRaisesRegex(
            RuntimeError, "AGENT_TOOL_DISPATCH_CURRENT_MODE_FORBIDDEN"
        ):
            dispatch_host._validate_current_policy(PLAN, context)
        validate_target.assert_not_called()


if __name__ == "__main__":
    unittest.main()
