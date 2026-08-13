import copy,unittest
from tools import scheduler_plan as scheduler
from tools.capability_gates import stable_hash

def inspection(action="CONTINUE",focus="development",continuations=None):
    value={"schemaVersion":"MaintenanceInspection 0.2","repository":"EAKerber/MobiliPresenter","continuations":continuations or [],"recommendation":{"action":action,"reasonCode":"TEST","focus":focus,"detail":"test","decisionScope":"operational-only","semanticAuthority":False,"allowedActions":["CONTINUE","RECONCILE","HANDOFF","PAUSE","NEEDS_HUMAN"]},"readOnly":True}
    value["inspectionHash"]=stable_hash(value);return value

def task(status="IN_PROGRESS",actor="developer-ui",target=None):
    return {"id":"task-one","actor":actor,"status":status,"branch":None,"prNumber":None,"completed":[],"remaining":["a"],"nextAction":"do a","lastKnownGood":{"sha":None,"checkpoint":None},"blockedBy":[],"handoffTo":target,"stateHash":"a"*64}

class SchedulerPlan01Tests(unittest.TestCase):
    def test_rejects_tampered_inspection(self):
        value=inspection();value["recommendation"]["focus"]="tampered"
        with self.assertRaisesRegex(RuntimeError,"HASH_MISMATCH"):scheduler.build_plan(value)
    def test_handoff_routes_only_explicit_target(self):
        value=inspection("HANDOFF","continuation:task-one",[task("HANDOFF",target="developer-engine")]);plan=scheduler.build_plan(value);self.assertEqual(plan["dispatch"]["target"],"developer-engine");self.assertEqual(plan["dispatch"]["channelClass"],"worker")
        bad=inspection("HANDOFF","continuation:task-one",[task("HANDOFF",target=None)])
        with self.assertRaisesRegex(RuntimeError,"HANDOFF_TARGET_INVALID"):scheduler.build_plan(bad)
    def test_continue_continuation_routes_actor(self):
        plan=scheduler.build_plan(inspection("CONTINUE","continuation:task-one",[task()]));self.assertEqual(plan["dispatch"]["target"],"developer-ui")
    def test_generic_continue_stays_with_supervisor(self):
        plan=scheduler.build_plan(inspection());self.assertEqual(plan["dispatch"],{"shouldWake":True,"channelClass":"supervisor","target":"gitops-supervisor","continuationId":None})
    def test_non_actionable_routing(self):
        self.assertFalse(scheduler.build_plan(inspection("PAUSE"))["dispatch"]["shouldWake"])
        self.assertEqual(scheduler.build_plan(inspection("RECONCILE"))["dispatch"]["channelClass"],"supervisor")
        self.assertEqual(scheduler.build_plan(inspection("NEEDS_HUMAN"))["dispatch"]["channelClass"],"human")
    def test_plan_is_deterministic_read_only_and_transport_free(self):
        value=inspection();a=scheduler.build_plan(value);b=scheduler.build_plan(copy.deepcopy(value));self.assertEqual(a["planHash"],b["planHash"]);self.assertTrue(a["readOnly"]);self.assertFalse(a["transportSideEffects"]);self.assertFalse(a["semanticAuthority"])
    def test_unsupported_or_semantic_inspection_is_rejected(self):
        value=inspection();value["schemaVersion"]="MaintenanceInspection 99";value["inspectionHash"]=stable_hash({k:v for k,v in value.items() if k!="inspectionHash"})
        with self.assertRaisesRegex(RuntimeError,"SCHEMA_UNSUPPORTED"):scheduler.build_plan(value)
        value=inspection();value["recommendation"]["semanticAuthority"]=True;value["inspectionHash"]=stable_hash({k:v for k,v in value.items() if k!="inspectionHash"})
        with self.assertRaisesRegex(RuntimeError,"SEMANTIC_AUTHORITY_INVALID"):scheduler.build_plan(value)

if __name__=="__main__":unittest.main()
