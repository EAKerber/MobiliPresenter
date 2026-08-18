import importlib.util
import io
import json
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from tools import project_state

MODULE_PATH=Path(__file__).resolve().parents[1]/"agent.py";spec=importlib.util.spec_from_file_location("agent_tool",MODULE_PATH);agent=importlib.util.module_from_spec(spec);assert spec and spec.loader;spec.loader.exec_module(agent)

class GitOps12Tests(unittest.TestCase):
    def base_state(self):
        return {"schemaVersion":"ProjectState 2.1","project":{"id":"mobilipresenter","repository":"EAKerber/MobiliPresenter"},"git":{"controlBranch":"main","protectedBranches":["integration/viewer-parallel-v0.1","ui/product-shell-v0.1"]},"published":{"url":"x","artifactManifest":"ops/published/viewer-next-current.json"},"development":{"initiative":"Renderer","phase":"between-increments","checkpoint":"FH-00","nextTransition":"fh-01"}}
    def test_state_shape_accepts_projectstate_21_only(self):
        state=self.base_state();self.assertEqual(project_state.validate_current(state),[]);old=dict(state);old["schemaVersion"]="ProjectState 2.0";self.assertTrue(project_state.validate_current(old))
    def test_ci_aggregation_remains_factual_sensor_primitive(self):
        self.assertEqual(agent.aggregate_ci([]),"unknown");self.assertEqual(agent.aggregate_ci([{"status":"IN_PROGRESS","conclusion":None}]),"pending");self.assertEqual(agent.aggregate_ci([{"status":"COMPLETED","conclusion":"FAILURE"}]),"failed");self.assertEqual(agent.aggregate_ci([{"status":"COMPLETED","conclusion":"SUCCESS"}]),"green")
    def test_verification_summary_distinguishes_unknown_from_failure(self):
        self.assertEqual(agent.verification_summary([{"status":"PASS"}]),{"status":"PASS","ok":True,"complete":True});self.assertEqual(agent.verification_summary([{"status":"PASS"},{"status":"UNKNOWN"}]),{"status":"UNKNOWN","ok":True,"complete":False});self.assertEqual(agent.verification_summary([{"status":"UNKNOWN"},{"status":"FAIL"}]),{"status":"FAIL","ok":False,"complete":False})
    def test_agent_has_no_parallel_remote_execution_identity_surface(self):
        self.assertFalse(hasattr(agent,"observe_remote"));self.assertFalse(hasattr(agent,"remote_verification_checks"))
    def test_control_and_protected_branches_are_known_repository_contexts(self):
        self.assertEqual(agent.git_context_check(self.base_state(),{"worktree":True,"branch":"main"})["context"],"control");self.assertEqual(agent.git_context_check(self.base_state(),{"worktree":True,"branch":"ui/product-shell-v0.1"})["context"],"protected-parallel")
    def test_operations_work_and_experiment_are_known_contexts(self):
        for branch in ("work/operations/project-state-v2","experiment/operations/peer-health"):
            check=agent.git_context_check(self.base_state(),{"worktree":True,"branch":branch});self.assertEqual(check["status"],"PASS");self.assertEqual(check["context"],"operations")
    def test_authority_name_does_not_grant_operational_work_context(self):
        check=agent.git_context_check(self.base_state(),{"worktree":True,"branch":"authority/operations/control"});self.assertEqual(check["status"],"FAIL")
    def test_status_projection_does_not_copy_execution_state(self):
        summary=agent.project_summary(project_state.operational_view(self.base_state()));self.assertNotIn("activeDevelopmentBranch",summary);self.assertNotIn("prNumber",summary);self.assertNotIn("blockers",summary)
    def test_handoff_21_does_not_embed_full_projectstate(self):
        state=self.base_state();view=project_state.operational_view(state);published={"release":"x","sourceBranch":"main","url":"https://example.invalid/"};verification={"status":"PASS","ok":True,"complete":True,"checks":[],"remote":None};observed={"worktree":True,"branch":"work/operations/test"}
        with mock.patch.object(agent,"_state_and_publication",return_value=(state,view,published)),mock.patch.object(agent,"verify_state",return_value=verification),mock.patch.object(agent,"observed_git",return_value=observed),mock.patch.object(agent,"recent_commits",return_value={"available":True,"entries":[]}):
            output=io.StringIO()
            with redirect_stdout(output):self.assertEqual(agent.command_handoff(True),0)
        payload=json.loads(output.getvalue());self.assertEqual(payload["schemaVersion"],"AgentHandoff 2.1");self.assertNotIn("projectState",payload);self.assertNotIn("activeDevelopmentBranch",payload["project"]);self.assertNotIn("prNumber",payload["project"]);self.assertNotIn("blockers",payload["project"])
    def test_legacy_prune_classifier_is_removed(self):
        self.assertFalse(hasattr(agent,"build_prune_plan"));self.assertFalse(hasattr(agent,"stable_plan_hash"))
    def test_ci_branch_name_uses_pull_request_head_ref(self):
        with mock.patch.dict(os.environ,{"GITHUB_HEAD_REF":"work/operations/test","GITHUB_REF_NAME":"31/merge"},clear=False):self.assertEqual(agent.ci_branch_name(),"work/operations/test")

if __name__=="__main__":unittest.main()
