import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];WORKFLOWS=ROOT/".github"/"workflows"

class WorkflowBoundaryTests(unittest.TestCase):
    def text(self,name):return (WORKFLOWS/name).read_text(encoding="utf-8")
    def test_python_tool_entrypoints_referenced_by_workflows_exist(self):
        pattern=re.compile(r"\bpython(?:3)?\s+tools/([A-Za-z0-9_.-]+\.py)\b");missing=[]
        for workflow in sorted(WORKFLOWS.glob("*.yml")):
            for relative in pattern.findall(workflow.read_text(encoding="utf-8")):
                if not (ROOT/"tools"/relative).is_file():missing.append(f"{workflow.name}:tools/{relative}")
        self.assertEqual(missing,[])
    def test_unittest_modules_referenced_by_workflows_exist(self):
        pattern=re.compile(r"\btools\.tests\.(test_[A-Za-z0-9_]+)\b");missing=[]
        for workflow in sorted(WORKFLOWS.glob("*.yml")):
            for module in pattern.findall(workflow.read_text(encoding="utf-8")):
                if not (ROOT/"tools"/"tests"/f"{module}.py").is_file():missing.append(f"{workflow.name}:tools.tests.{module}")
        self.assertEqual(missing,[])
    def test_viewer_validation_has_no_repository_write_path(self):
        text=self.text("viewer-next.yml");self.assertIn("contents: read",text);self.assertNotIn("contents: write",text);self.assertNotIn("persist-viewer-artifacts.py",text);self.assertNotIn("artifact/viewer-next-",text)
    def test_workflows_do_not_encode_git_prune_plan_internals(self):
        forbidden=("GitPrunePlan","branchInventoryComplete","prHistoryComplete","ancestryComplete","requiresPlanFile","requiresExpectedPlan","requiresExplicitAuthorization","autoDeleteEligible")
        for name in ("agent-ops.yml","branch-hygiene.yml"):
            text=self.text(name)
            for token in forbidden:self.assertNotIn(token,text,f"{name} encodes prune-plan internals: {token}")
            self.assertIn("tools/prune_plan.py validate",text)
    def test_branch_hygiene_does_not_duplicate_cleanup_for_merged_prs(self):
        text=self.text("branch-hygiene.yml")
        self.assertIn("push:\n    branches: [main]",text)
        self.assertIn("pull_request:\n    types: [closed]",text)
        self.assertIn("if: github.event_name != 'pull_request' || github.event.pull_request.merged == false",text)
    def test_agent_ops_uses_project_machine_as_live_remote_proof(self):
        text=self.text("agent-ops.yml");self.assertNotIn("Verify remote PR identity",text);self.assertNotIn("agent.py verify --remote",text);self.assertIn("project_machine.py inspect --live",text)
    def test_agent_ops_does_not_reintroduce_local_work_authority_gate(self):
        text=self.text("agent-ops.yml");self.assertNotIn("Verify continuation state",text);self.assertNotIn("continuation.py verify",text);self.assertIn("docs/kickstarts/**",text)
    def test_operational_workflows_do_not_implement_domain_hashing_or_direct_ref_writes(self):
        for name in ("agent-ops.yml","branch-hygiene.yml","coordination-guard.yml","supervisor-snapshot.yml"):
            text=self.text(name);self.assertNotIn("stable_hash",text);self.assertNotIn("git update-ref",text);self.assertNotIn("git push",text);self.assertNotRegex(text,r"gh\s+api[^\n]*(?:--method|-X)\s+(?:POST|PATCH|PUT|DELETE)")

if __name__=="__main__":unittest.main()
