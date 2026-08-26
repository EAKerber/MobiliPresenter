import io
import json
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from tools import agent, git_mutation_plan


class AgentMutationPlanFacadeTests(unittest.TestCase):
    def args(self, **overrides):
        base = {
            "operation": "create-branch",
            "branch": "work/operations/example",
            "base_sha": "a" * 40,
            "branch_head": None,
            "path": None,
            "blob_sha": None,
            "content_sha256": None,
            "changes_json": None,
            "changes_file": None,
            "head": None,
            "base": None,
            "head_sha": None,
            "title": None,
            "body_sha256": None,
            "pr_number": None,
            "merge_method": "squash",
            "current_sha": None,
            "new_sha": None,
            "force": False,
        }
        base.update(overrides)
        return types.SimpleNamespace(**base)

    def test_toolbox_exposes_mutation_plan_but_no_mutation_apply_alias(self):
        self.assertIn("git mutation-plan", agent.TOOLBOX_COMMANDS)
        self.assertNotIn("git mutation-apply", agent.TOOLBOX_COMMANDS)

    def test_agent_delegates_to_read_only_planner(self):
        expected = git_mutation_plan.create_branch(branch="work/operations/example", base_sha="a" * 40, control_branch="main")
        state = {
            "schemaVersion": "ProjectState 2.1",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
            "git": {"controlBranch": "main", "protectedBranches": []},
            "published": {"url": "https://example.invalid", "artifactManifest": "ops/published/viewer-next-current.json"},
            "development": {"initiative": "x", "phase": "between-increments", "checkpoint": "c", "nextTransition": "n"},
        }
        with patch.object(agent.project_state, "load_state", return_value=state), patch.object(agent.git_mutation_plan, "create_branch", return_value=expected) as build:
            out = io.StringIO()
            with redirect_stdout(out):
                result = agent.command_git_mutation_plan(True, self.args())
        self.assertEqual(result, 0)
        build.assert_called_once_with(branch="work/operations/example", base_sha="a" * 40, control_branch="main")
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["planHash"], expected["planHash"])
        self.assertFalse(payload["authorizesMutation"])

    def test_missing_observed_precondition_fails_before_planning(self):
        state = {
            "schemaVersion": "ProjectState 2.1",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
            "git": {"controlBranch": "main", "protectedBranches": []},
            "published": {"url": "https://example.invalid", "artifactManifest": "ops/published/viewer-next-current.json"},
            "development": {"initiative": "x", "phase": "between-increments", "checkpoint": "c", "nextTransition": "n"},
        }
        args = self.args(operation="update-file", branch_head=None, path="tools/x.py", blob_sha="b" * 40, content_sha256="c" * 64)
        with patch.object(agent.project_state, "load_state", return_value=state):
            with self.assertRaisesRegex(RuntimeError, "GIT_MUTATION_BRANCH_HEAD_REQUIRED"):
                agent.command_git_mutation_plan(True, args)

    def test_agent_exposes_multi_path_bundle_plan(self):
        state = {
            "schemaVersion": "ProjectState 2.1",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
            "git": {"controlBranch": "main", "protectedBranches": []},
            "published": {"url": "https://example.invalid", "artifactManifest": "ops/published/viewer-next-current.json"},
            "development": {"initiative": "x", "phase": "between-increments", "checkpoint": "c", "nextTransition": "n"},
        }
        changes = [
            {"path": "docs/a.txt", "content": "a\n"},
            {"path": "docs/b.txt", "delete": True},
        ]
        args = self.args(
            operation="mutate-files",
            branch_head="a" * 40,
            changes_file="changes.json",
        )
        with patch.object(agent.project_state, "load_state", return_value=state), patch(
            "tools.agent_commands.impl.Path.read_text", return_value=json.dumps(changes)
        ):
            out = io.StringIO()
            with redirect_stdout(out):
                result = agent.command_git_mutation_plan(True, args)
        self.assertEqual(result, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["operation"], "mutate-files")
        self.assertEqual(payload["readback"]["expectedChangedPaths"], ["docs/a.txt", "docs/b.txt"])


if __name__ == "__main__":
    unittest.main()
