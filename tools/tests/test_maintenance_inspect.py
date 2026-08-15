import copy
import unittest
from tools import maintenance_inspect as maintenance


def state():
    return {"project":{"repository":"EAKerber/MobiliPresenter"},"git":{"activeDevelopmentBranch":None},"development":{"phase":"between-increments","checkpoint":"CHECKPOINT","nextTransition":"open-next-slice","prNumber":None,"blockers":[]}}


def verification(ok=True):
    return {"ok":ok,"checks":[] if ok else [{"name":"project-state","status":"FAIL"}],"remote":None}


def cap():
    return {"id":"coordination-leases","policy":"canonical","supervisorParticipation":"active","reviewAction":"NO_EXPERIMENTAL_REVIEW","nextGates":[],"backlogCount":0,"roundsWithoutActiveGates":0,"maxRoundsWithoutActiveGates":3,"deferReason":None,"reviewPlanHash":"a"*64}


class MaintenanceInspect01Tests(unittest.TestCase):
    def build(self,s=None,v=None,caps=None,remote=False,prs=None,coord=None):
        return maintenance.build_inspection(s or state(),v or verification(),{"worktree":True,"branch":"main","head":"1"*40,"dirty":False},caps if caps is not None else [cap()],remote_requested=remote,pull_requests=prs or {"available":False,"reason":"NOT_REQUESTED","items":[]},coordination_state=coord or {"available":False,"reason":"NOT_REQUESTED","intents":[],"leases":[]})

    def test_coherent_state_continues(self):
        result=self.build(); self.assertEqual(result["recommendation"]["action"],"CONTINUE"); self.assertEqual(result["recommendation"]["reasonCode"],"NEXT_TRANSITION_AVAILABLE"); self.assertTrue(result["readOnly"])

    def test_verification_failure_reconciles(self):
        self.assertEqual(self.build(v=verification(False))["recommendation"]["action"],"RECONCILE")

    def test_blocker_pauses(self):
        s=state(); s["development"]["blockers"]=["waiting-on-input"]; self.assertEqual(self.build(s=s)["recommendation"]["action"],"PAUSE")

    def test_gate_limit_requires_human(self):
        c=cap(); c.update({"id":"experiment","policy":"experimental","reviewAction":"REVIEW_EMPTY_LIMIT","roundsWithoutActiveGates":3,"maxRoundsWithoutActiveGates":3})
        result=self.build(caps=[c]); self.assertEqual(result["recommendation"]["action"],"NEEDS_HUMAN"); self.assertEqual(result["recommendation"]["focus"],"experiment")

    def test_active_gates_are_actionable(self):
        c=cap(); c.update({"id":"experiment","policy":"experimental","reviewAction":"TEST_NEXT_GATES","nextGates":["rollback"],"backlogCount":1})
        result=self.build(caps=[c]); self.assertEqual(result["recommendation"]["reasonCode"],"CAPABILITY_GATES_DUE"); self.assertFalse(result["recommendation"]["semanticAuthority"])

    def test_isolated_experimental_capability_does_not_change_recommendation(self):
        c=cap(); c.update({"id":"peer-recovery","policy":"experimental","supervisorParticipation":"isolated","reviewAction":"TEST_NEXT_GATES","nextGates":["runtime-shadow"],"backlogCount":1})
        result=self.build(caps=[c])
        self.assertEqual(result["recommendation"]["reasonCode"],"NEXT_TRANSITION_AVAILABLE")
        self.assertEqual(result["recommendation"]["focus"],"development")
        self.assertEqual(result["capabilities"][0]["supervisorParticipation"],"isolated")

    def test_remote_unavailable_requires_human(self):
        result=self.build(remote=True,prs={"available":False,"reason":"GH_NOT_FOUND","items":[]},coord={"available":False,"reason":"GH_NOT_FOUND","intents":[],"leases":[]}); self.assertEqual(result["recommendation"]["action"],"NEEDS_HUMAN")

    def test_unclassified_pr_reconciles(self):
        prs={"available":True,"items":[{"number":55,"headRef":"feature/mystery","classification":"unclassified","ci":"green"}]}; coord={"available":True,"authorityHead":"2"*40,"intents":[],"leases":[]}
        result=self.build(remote=True,prs=prs,coord=coord); self.assertEqual(result["recommendation"]["reasonCode"],"UNCLASSIFIED_OPEN_PR")

    def test_active_pr_pending_and_failed(self):
        s=state(); s["git"]["activeDevelopmentBranch"]="engine/work"; s["development"]["prNumber"]=7; coord={"available":True,"authorityHead":"2"*40,"intents":[],"leases":[]}
        prs={"available":True,"items":[{"number":7,"headRef":"engine/work","classification":"active-development","ci":"pending"}]}; self.assertEqual(self.build(s=s,remote=True,prs=prs,coord=coord)["recommendation"]["action"],"PAUSE")
        failed=copy.deepcopy(prs); failed["items"][0]["ci"]="failed"; self.assertEqual(self.build(s=s,remote=True,prs=failed,coord=coord)["recommendation"]["action"],"RECONCILE")

    def test_closed_pr_lease_reconciles(self):
        coord={"available":True,"authorityHead":"2"*40,"intents":[],"leases":[{"leaseId":"l1","owner":{"pr":99}}]}; result=self.build(remote=True,prs={"available":True,"items":[]},coord=coord); self.assertEqual(result["recommendation"]["reasonCode"],"LEASE_OWNER_PR_NOT_OPEN")

    def test_hash_stable_sensitive_and_handoff_reserved(self):
        first=self.build(); second=self.build(); self.assertEqual(first["inspectionHash"],second["inspectionHash"]); self.assertIn("HANDOFF",first["recommendation"]["allowedActions"]); self.assertNotEqual(first["recommendation"]["action"],"HANDOFF")
        s=state(); s["development"]["nextTransition"]="different"; self.assertNotEqual(first["inspectionHash"],self.build(s=s)["inspectionHash"])


if __name__=="__main__": unittest.main()
