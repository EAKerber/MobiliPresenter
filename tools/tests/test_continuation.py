import unittest
from pathlib import Path

from tools import continuation
from tools import continuation_transition as transition

TEST_ROOT = Path(__file__).resolve().parent


def base():
    return transition.create("task-one","developer-ui",["a","b"],"do a")["candidate"]


class WorkItem02Tests(unittest.TestCase):
    def test_current_contract_is_v02(self):
        value=base();self.assertEqual(continuation.CURRENT_SCHEMA_VERSION,"ContinuationState 0.2");self.assertEqual(value["workerId"],"developer-ui");self.assertEqual(value["dependsOn"],[]);self.assertEqual(continuation.validate_current(value),[])
    def test_advance_moves_work_and_requires_next_when_remaining(self):
        first=transition.advance(base(),["a"],"do b",sha="1"*40,checkpoint="after-a")["candidate"];self.assertEqual(first["completed"],["a"]);self.assertEqual(first["remaining"],["b"]);self.assertEqual(first["status"],"IN_PROGRESS")
        with self.assertRaisesRegex(RuntimeError,"NEXT_ACTION_REQUIRED"):transition.advance(base(),["a"])
    def test_wait_resume_and_handoff_use_worker_vocabulary(self):
        waiting=transition.wait(base(),["external-input"])["candidate"];self.assertEqual(waiting["blockers"],["external-input"]);resumed=transition.resume(waiting,"developer-ui")["candidate"];self.assertEqual(resumed["blockers"],[])
        handed=transition.handoff(base(),"developer-engine","continue b")["candidate"];self.assertEqual(handed["handoffToWorkerId"],"developer-engine")
        with self.assertRaisesRegex(RuntimeError,"HANDOFF_WORKER_MISMATCH"):transition.resume(handed,"developer-ui")
        self.assertEqual(transition.resume(handed,"developer-engine")["candidate"]["workerId"],"developer-engine")
    def test_done_restart_and_bind_execution_are_current(self):
        empty=transition.advance(base(),["a","b"])["candidate"];done=transition.done(empty)["candidate"];restarted=transition.restart(done,["again"],"repeat")["candidate"];bound=transition.bind_execution(restarted,"work/ui/example",42)["candidate"];self.assertEqual(bound["branch"],"work/ui/example");self.assertEqual(bound["prNumber"],42)
    def test_dependencies_are_execution_guards(self):
        dep=transition.create("dep","developer-engine",["x"],"do x")["candidate"];child=transition.create("child","developer-ui",["y"],"do y",depends_on=["dep"])["candidate"]
        with self.assertRaisesRegex(RuntimeError,"DEPENDENCY_NOT_DONE"):transition.advance(child,["y"],inventory=[child,dep])
        dep_empty=transition.advance(dep,["x"])["candidate"];dep_done=transition.done(dep_empty)["candidate"];advanced=transition.advance(child,["y"],inventory=[child,dep_done])["candidate"];self.assertEqual(advanced["completed"],["y"])
    def test_work_graph_rejects_duplicate_active_execution_identity(self):
        a=transition.bind_execution(base(),"work/ui/shared",7)["candidate"];b=transition.bind_execution(transition.create("task-two","developer-engine",["x"],"do x")["candidate"],"work/ui/shared",8)["candidate"]
        with self.assertRaisesRegex(RuntimeError,"ACTIVE_BRANCH_CONFLICT"):transition.validate_work_inventory({"task-one":a,"task-two":b})
    def test_local_model_has_no_local_authority_cli(self):
        for name in ("discover","load","parser","main","create","advance","apply","plan"):self.assertFalse(hasattr(continuation,name),name)
    def test_current_test_fixtures_do_not_pin_v01_source_schema(self):
        obsolete = "ContinuationState " + "0.1"
        token = f'"sourceSchemaVersion": "{obsolete}"'
        violations=[]
        for path in sorted(TEST_ROOT.glob("test_*.py")):
            if path == Path(__file__):
                continue
            if token in path.read_text(encoding="utf-8"):
                violations.append(path.name)
        self.assertEqual(violations,[])

if __name__=="__main__":unittest.main()
