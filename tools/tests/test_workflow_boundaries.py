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
    def test_branch_hygiene_owns_prune_plan_validation(self):
        hygiene=self.text("branch-hygiene.yml");agent=self.text("agent-ops.yml")
        forbidden=("GitPrunePlan","branchInventoryComplete","prHistoryComplete","ancestryComplete","requiresPlanFile","requiresExpectedPlan","requiresExplicitAuthorization","autoDeleteEligible")
        for name,text in (("agent-ops.yml",agent),("branch-hygiene.yml",hygiene)):
            for token in forbidden:self.assertNotIn(token,text,f"{name} encodes prune-plan internals: {token}")
        self.assertIn("tools/prune_plan.py validate",hygiene)
        self.assertNotIn("tools/prune_plan.py",agent)
    def test_agent_ops_does_not_reintroduce_m11_convergence_pipeline(self):
        text=self.text("agent-ops.yml")
        for token in ("tools.semantics convergence","convergence-inspection","Generate branch prune audit","git-prune-plan"):
            self.assertNotIn(token,text)
    def test_branch_hygiene_does_not_duplicate_cleanup_for_merged_prs(self):
        text=self.text("branch-hygiene.yml")
        self.assertIn("push:\n    branches: [main]",text)
        self.assertIn("pull_request:\n    types: [closed]",text)
        self.assertIn("if: github.event_name != 'pull_request' || github.event.pull_request.merged == false",text)
    def test_agent_ops_uses_project_machine_as_live_remote_proof(self):
        text=self.text("agent-ops.yml");self.assertNotIn("Verify remote PR identity",text);self.assertNotIn("agent.py verify --remote",text);self.assertIn("project_machine.py inspect --live",text)
    def test_agent_ops_does_not_reintroduce_local_work_authority_gate(self):
        text=self.text("agent-ops.yml");self.assertNotIn("Verify continuation state",text);self.assertNotIn("continuation.py verify",text);self.assertIn("docs/kickstarts/**",text)
    def test_hosted_cycle_owns_trace_lifecycle_internally(self):
        text=self.text("hosted-agent-cycle.yml")
        self.assertIn("python tools/hosted_agent_cycle.py close",text)
        self.assertNotIn("python tools/hosted_agent_cycle_trace.py",text)
        self.assertNotIn("Detect trace-capable begin",text)
        self.assertNotIn("-f tools/hosted_agent_cycle_trace.py",text)
    def test_hosted_agent_tool_remains_repository_read_only(self):
        text=self.text("hosted-agent-tool.yml")
        self.assertIn("contents: read",text)
        self.assertNotIn("contents: write",text)
        self.assertNotIn("actions: write",text)
        self.assertNotIn("repository_dispatch",text)
        self.assertNotIn("workflow_dispatch",text)
    def test_remote_canonical_workflow_owns_write_permission_and_consumes_hosted_artifact(self):
        hosted=self.text("hosted-agent-tool.yml");remote=self.text("remote-canonical-execution.yml")
        self.assertNotIn("contents: write",hosted)
        self.assertIn("contents: write",remote)
        self.assertIn("workflow_run:",remote)
        self.assertIn("workflows: [\"Hosted Agent Tool\"]",remote)
        self.assertIn("types: [completed]",remote)
        self.assertIn("actions/download-artifact@v4",remote)
        self.assertIn("tools.agent_tools.dispatch_host",remote)
        self.assertIn("MOBILIPRESENTER_AGENT_TOOL_MUTATION_ATTEMPT_V0_1",remote)
    def test_privileged_workflow_run_is_bound_to_default_branch_and_exact_origin_run(self):
        remote=self.text("remote-canonical-execution.yml")
        self.assertIn("github.event.workflow_run.event == 'issue_comment'",remote)
        self.assertIn("github.event.workflow_run.head_branch == github.event.repository.default_branch",remote)
        self.assertIn("name: agent-tool-${{ github.event.workflow_run.id }}",remote)
        self.assertIn("run-id: ${{ github.event.workflow_run.id }}",remote)
        self.assertGreaterEqual(remote.count('--hosted-run-id "$HOSTED_RUN_ID"'),2)
    def test_privileged_dispatch_hosts_preserve_evidence_before_fail_closed_gate(self):
        cases=(
            ("remote-canonical-execution.yml","Preserve remote canonical execution evidence","Fail closed on blocked execution","remote-canonical-execution-${{ github.run_id }}-${{ github.run_attempt }}","/tmp/remote-canonical-result.json"),
            ("remote-canonical-execution.yml","Preserve Agent Tool dispatch evidence","Require terminal dispatch outcome","agent-tool-dispatch-${{ github.run_id }}-${{ github.run_attempt }}","/tmp/agent-tool-*.json"),
            ("agent-write-lease-dispatch.yml","Preserve Agent Write Lease dispatch evidence","Require terminal lifecycle outcome","agent-write-lease-dispatch-${{ github.run_id }}-${{ github.run_attempt }}","/tmp/agent-write-lease-*.json"),
        )
        for workflow,upload_name,gate_name,artifact_name,path in cases:
            text=self.text(workflow);upload=f"- name: {upload_name}";gate=f"- name: {gate_name}"
            self.assertIn(upload,text);self.assertIn(gate,text);self.assertLess(text.index(upload),text.index(gate))
            segment=text[text.index(upload):text.index(gate)]
            self.assertIn("if: always()",segment);self.assertIn("uses: actions/upload-artifact@v4",segment)
            self.assertIn(f"name: {artifact_name}",segment);self.assertIn(path,segment)
            self.assertIn("if-no-files-found: warn",segment);self.assertIn("retention-days: 14",segment)
            self.assertNotIn("continue-on-error: true",segment)
            self.assertIn(f"- name: {gate_name}\n        if: always()",text)
    def test_operational_workflows_do_not_implement_domain_hashing_or_direct_ref_writes(self):
        for name in ("agent-ops.yml","branch-hygiene.yml","coordination-guard.yml","supervisor-snapshot.yml"):
            text=self.text(name);self.assertNotIn("stable_hash",text);self.assertNotIn("git update-ref",text);self.assertNotIn("git push",text);self.assertNotRegex(text,r"gh\s+api[^\n]*(?:--method|-X)\s+(?:POST|PATCH|PUT|DELETE)")

if __name__=="__main__":unittest.main()
