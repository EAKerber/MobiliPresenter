import unittest
from unittest import mock

from tools import agent,project_state,publication

class AgentProjectionTests(unittest.TestCase):
    def live_inputs(self):
        state=project_state.load_state();view=project_state.operational_view(state);manifest=publication.load_manifest(view["published"]["artifactManifest"]);published=publication.publication_view(view,manifest);return state,view,published
    def test_handoff_21_contains_project_summary_not_full_state(self):
        state,view,published=self.live_inputs();verification={"status":"PASS","ok":True,"complete":True,"checks":[],"remote":None}
        with mock.patch("tools.agent._state_and_publication",return_value=(state,view,published)),mock.patch("tools.agent.observed_git",return_value={"worktree":False}),mock.patch("tools.agent.verify_state",return_value=verification),mock.patch("builtins.print") as output:
            self.assertEqual(agent.command_handoff(True),0)
        rendered=output.call_args.args[0];self.assertIn('"schemaVersion": "AgentHandoff 2.1"',rendered);self.assertNotIn('"projectState":',rendered)
        for token in ("productInvariants","publishedBranch","preserveBranches","artifactSha256","constraints","toolboxPhase","canonicalState","activeDevelopmentBranch","developmentPrNumber"):
            self.assertNotIn(token,rendered)
        self.assertIn('"sourceBuildFingerprint"',rendered);self.assertIn('"projectStateHash"',rendered)
    def test_status_projection_uses_derived_publication_without_execution_state(self):
        state,view,published=self.live_inputs()
        with mock.patch("tools.agent._state_and_publication",return_value=(state,view,published)),mock.patch("tools.agent.observed_git",return_value={"worktree":False}),mock.patch("builtins.print") as output:
            self.assertEqual(agent.command_status(True),0)
        rendered=output.call_args.args[0];self.assertIn(published["release"],rendered);self.assertIn('"sourceBuildFingerprint"',rendered);self.assertNotIn('"artifactSha256"',rendered);self.assertNotIn('"activeDevelopmentBranch"',rendered);self.assertNotIn('"blockers"',rendered)

if __name__=="__main__":unittest.main()
