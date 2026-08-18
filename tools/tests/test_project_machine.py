import unittest

from tools import maintenance_inspect, project_machine, project_sensors


def state():
    return {
        "schemaVersion": "ProjectState 2.1",
        "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
        "git": {"controlBranch": "main", "protectedBranches": ["architecture/tpc"]},
        "published": {"url": "x", "artifactManifest": "ops/published/viewer-next-current.json"},
        "development": {"initiative": "I", "phase": "between-increments", "checkpoint": "C", "nextTransition": "next"},
    }


def work_item(work_id="probe-one", status="DONE", *, branch=None, pr=None, worker="developer-ui"):
    if branch is None and status == "DONE": branch = "ops/old"
    if pr is None and status == "DONE": pr = 7
    return {"id":work_id,"workerId":worker,"status":status,"branch":branch,"prNumber":pr,"dependsOn":[],"completed":["probe"] if status=="DONE" else [],"remaining":[] if status=="DONE" else ["probe"],"nextAction":None if status=="DONE" else "probe","lastKnownGood":{"sha":None,"checkpoint":None},"blockers":[],"handoffToWorkerId":None,"sourceSchemaVersion":"ContinuationState 0.2","stateHash":"a"*64}


def base_sensors():
    verification={"status":"PASS","ok":True,"complete":True,"checks":[],"remote":None};capability={"id":"coordination-leases","policy":"canonical","supervisorParticipation":"active","reviewAction":"NO_EXPERIMENTAL_REVIEW","nextGates":[],"backlogCount":0,"roundsWithoutActiveGates":0,"maxRoundsWithoutActiveGates":3,"deferReason":None,"reviewPlanHash":"a"*64}
    return {
        "projectState":project_sensors.sensor("PASS",data={"verification":verification,"checks":[]},authority={"kind":"repository","path":"ops/state/project.json"}),
        "publication":project_sensors.sensor("PASS",data={"checks":[]},authority={"kind":"repository","path":"ops/published/current.json"}),
        "git":project_sensors.sensor("PASS",data={"observed":{"worktree":True,"branch":"work/operations/project-state-v2-prep","head":"1"*40,"dirty":False},"checks":[]},authority={"kind":"worktree"}),
        "repository":project_sensors.sensor("PASS",data={"checks":[]},authority={"kind":"repository","name":"EAKerber/MobiliPresenter"}),
        "control":project_sensors.sensor("PASS",data={"branch":"main","sha":"2"*40,"mode":"remote"},authority={"kind":"git-ref","branch":"main"}),
        "capabilities":project_sensors.sensor("PASS",data={"items":[capability]},authority={"kind":"repository","path":"ops/capabilities"}),
        "pullRequests":project_sensors.sensor("PASS",data={"available":True,"items":[]},authority={"kind":"github","resource":"pull-requests"}),
        "coordination":project_sensors.sensor("PASS",data={"available":True,"authorityBranch":"coordination/leases","authorityHead":"3"*40,"intents":[],"leases":[]},authority={"kind":"git-authority","branch":"coordination/leases"}),
        "continuations":project_sensors.sensor("PASS",data={"available":True,"authorityBranch":"coordination/continuations","authorityHead":"4"*40,"items":[]},authority={"kind":"git-authority","branch":"coordination/continuations"}),
    }


class ProjectMachineTests(unittest.TestCase):
    def test_complete_live_inspection_is_slim_and_valid(self):
        value=project_machine.build_inspection(state(),base_sensors(),scope="live")
        self.assertEqual(value["schemaVersion"],"ProjectMachineInspection 0.5")
        self.assertEqual(set(value["project"]),{"stateHash","controlBranch","protectedBranches","phase","checkpoint","nextTransition"})
        self.assertNotIn("activeDevelopmentBranch",value["project"]);self.assertNotIn("developmentPrNumber",value["project"]);self.assertNotIn("blockers",value["project"])
        self.assertEqual(value["trust"]["status"],"PASS");self.assertEqual(value["coherence"]["status"],"PASS");self.assertTrue(project_machine.validate_inspection(value)["ok"])

    def test_base_scope_is_explicit_and_valid(self):
        value=project_machine.build_inspection(state(),base_sensors(),scope="base");self.assertEqual(value["scope"],"base");self.assertTrue(project_machine.validate_inspection(value)["ok"])

    def test_unknown_sensor_is_not_green(self):
        sensors=base_sensors();sensors["coordination"]=project_sensors.sensor("UNKNOWN",code="COORDINATION_AUTHORITY_UNAVAILABLE",data={"available":False,"intents":[],"leases":[]},authority={"kind":"git-authority","branch":"coordination/leases"});value=project_machine.build_inspection(state(),sensors,scope="live");self.assertEqual(value["trust"]["status"],"UNKNOWN")

    def test_known_work_pr_contradiction_separates_trust_and_coherence(self):
        sensors=base_sensors();sensors["continuations"]["data"]["items"]=[work_item(status="IN_PROGRESS",branch="work/operations/work",pr=7)];sensors["pullRequests"]["data"]["items"]=[{"number":7,"headRef":"wrong","baseRef":"main","ci":"green","ciObserved":True}];value=project_machine.build_inspection(state(),sensors,scope="live");self.assertEqual(value["trust"]["status"],"PASS");self.assertEqual(value["coherence"]["status"],"FAIL")

    def test_unknown_live_work_fails_closed_in_maintenance(self):
        sensors=base_sensors();sensors["continuations"]=project_sensors.sensor("UNKNOWN",code="CONTINUATION_AUTHORITY_UNAVAILABLE",data={"available":False,"items":[]},authority={"kind":"git-authority","branch":"coordination/continuations"});machine=project_machine.build_inspection(state(),sensors,scope="live");maintenance=maintenance_inspect.from_project_inspection(machine);self.assertEqual(maintenance["recommendation"]["action"],"NEEDS_HUMAN")

    def test_unobserved_work_in_base_scope_does_not_authorize_next_transition(self):
        sensors=base_sensors();sensors["continuations"]=project_sensors.observe_continuations_local();machine=project_machine.build_inspection(state(),sensors,scope="base");maintenance=maintenance_inspect.from_project_inspection(machine);self.assertEqual(maintenance["recommendation"]["action"],"PAUSE");self.assertEqual(maintenance["recommendation"]["reasonCode"],"NOT_OBSERVED_IN_LOCAL_SCOPE")

    def test_failed_sensor_reconciles_with_sensor_reason(self):
        sensors=base_sensors();sensors["publication"]=project_sensors.sensor("FAIL",code="PUBLISHED_ARTIFACT_MISMATCH",data={},authority={"kind":"repository","path":"ops/published/current.json"});machine=project_machine.build_inspection(state(),sensors,scope="live");maintenance=maintenance_inspect.from_project_inspection(machine);self.assertEqual(maintenance["recommendation"]["action"],"RECONCILE");self.assertEqual(maintenance["recommendation"]["reasonCode"],"PUBLISHED_ARTIFACT_MISMATCH")

    def test_work_pr_coherence_failure_reconciles(self):
        sensors=base_sensors();sensors["continuations"]["data"]["items"]=[work_item(status="IN_PROGRESS",branch="work/operations/work",pr=7)];machine=project_machine.build_inspection(state(),sensors,scope="live");maintenance=maintenance_inspect.from_project_inspection(machine);self.assertEqual(machine["coherence"]["status"],"FAIL");self.assertEqual(maintenance["recommendation"]["reasonCode"],"WORK_PR_NOT_OPEN")

    def test_work_ci_policy_is_derived_from_work_without_projectstate_execution_identity(self):
        item=work_item(status="IN_PROGRESS",branch="work/operations/work",pr=7)
        for ci,expected in (("pending","PAUSE"),("failed","RECONCILE"),("unknown","NEEDS_HUMAN")):
            sensors=base_sensors();sensors["continuations"]["data"]["items"]=[item];sensors["pullRequests"]["data"]["items"]=[{"number":7,"headRef":"work/operations/work","baseRef":"main","ci":ci,"ciObserved":ci!="unknown"}];machine=project_machine.build_inspection(state(),sensors,scope="live");maintenance=maintenance_inspect.from_project_inspection(machine);self.assertEqual(maintenance["recommendation"]["action"],expected)

    def test_hash_is_stable_and_sensitive(self):
        first=project_machine.build_inspection(state(),base_sensors(),scope="live");second=project_machine.build_inspection(state(),base_sensors(),scope="live");self.assertEqual(first["inspectionHash"],second["inspectionHash"]);changed=base_sensors();changed["control"]["data"]["sha"]="9"*40;third=project_machine.build_inspection(state(),changed,scope="live");self.assertNotEqual(first["inspectionHash"],third["inspectionHash"])

    def test_derived_surfaces_reject_tampering(self):
        value=project_machine.build_inspection(state(),base_sensors(),scope="live");value["workGraph"]["terminal"]=["fake"];body={k:v for k,v in value.items() if k!="inspectionHash"};value["inspectionHash"]=project_machine.stable_hash(body)
        with self.assertRaisesRegex(RuntimeError,"PROJECT_MACHINE_WORK_GRAPH_MISMATCH"):project_machine.validate_inspection(value)

    def test_done_continuation_is_terminal_work_observation_not_failure(self):
        sensors=base_sensors();sensors["continuations"]["data"]["items"]=[work_item()];value=project_machine.build_inspection(state(),sensors,scope="live");self.assertEqual(value["trust"]["status"],"PASS");self.assertEqual(value["coherence"]["status"],"PASS");self.assertEqual(value["workGraph"]["terminal"],["probe-one"])

    def test_project_machine_has_no_apply_surface(self):
        forbidden={"checkpoint_candidate","prune_apply","capability_apply","update_ref","atomic_write_json"};self.assertTrue(forbidden.isdisjoint(set(project_machine.__dict__)))


if __name__=="__main__":unittest.main()
