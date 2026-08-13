import tempfile, unittest
from pathlib import Path
from tools import continuation


def base():
    return continuation.create("task-one","developer-ui",["a","b"],"do a")["after"]


class ContinuationState01Tests(unittest.TestCase):
    def test_create_is_ready_and_requires_work(self):
        value=base(); self.assertEqual(value["status"],"READY"); self.assertEqual(value["remaining"],["a","b"])
        with self.assertRaisesRegex(RuntimeError,"CREATE_REQUIRES_WORK"): continuation.create("empty","actor",[],"nothing")

    def test_advance_moves_work_and_requires_next_when_remaining(self):
        first=continuation.advance(base(),["a"],"do b",sha="1"*40,checkpoint="after-a")["after"]
        self.assertEqual(first["completed"],["a"]); self.assertEqual(first["remaining"],["b"]); self.assertEqual(first["status"],"IN_PROGRESS")
        with self.assertRaisesRegex(RuntimeError,"NEXT_ACTION_REQUIRED"): continuation.advance(base(),["a"])

    def test_wait_and_resume_are_explicit(self):
        waiting=continuation.wait(base(),["external-input"])["after"]; self.assertEqual(waiting["status"],"WAITING")
        resumed=continuation.resume(waiting,"developer-ui")["after"]; self.assertEqual(resumed["status"],"IN_PROGRESS"); self.assertEqual(resumed["blockedBy"],[])

    def test_handoff_requires_target_actor_on_resume(self):
        handed=continuation.handoff(base(),"developer-engine","continue b")["after"]; self.assertEqual(handed["status"],"HANDOFF")
        with self.assertRaisesRegex(RuntimeError,"HANDOFF_ACTOR_MISMATCH"): continuation.resume(handed,"developer-ui")
        resumed=continuation.resume(handed,"developer-engine")["after"]; self.assertEqual(resumed["actor"],"developer-engine")

    def test_done_requires_no_remaining_work(self):
        with self.assertRaisesRegex(RuntimeError,"DONE_REMAINING_WORK"): continuation.done(base())
        empty=continuation.advance(base(),["a","b"])["after"]; done=continuation.done(empty)["after"]; self.assertEqual(done["status"],"DONE"); self.assertIsNone(done["nextAction"])

    def test_plan_hash_is_stable_and_stale_apply_fails(self):
        p1=continuation.handoff(base(),"developer-engine","continue b"); p2=continuation.handoff(base(),"developer-engine","continue b"); self.assertEqual(p1["planHash"],p2["planHash"])
        with self.assertRaisesRegex(RuntimeError,"PLAN_HASH_MISMATCH"): continuation.apply(p1,"bad")

    def test_apply_create_and_readback(self):
        old=continuation.DIR
        try:
            with tempfile.TemporaryDirectory() as td:
                continuation.DIR=Path(td)/"ops/continuations"
                p=continuation.create("task-one","developer-ui",["a"],"do a"); result=continuation.apply(p,p["planHash"])
                self.assertTrue(result["applied"]); self.assertEqual(continuation.load("task-one")["status"],"READY")
        finally: continuation.DIR=old

    def test_validation_rejects_inconsistent_handoff(self):
        value=base(); value["status"]="HANDOFF"; self.assertIn("CONTINUATION_HANDOFF_STATE_INVALID",continuation.validate(value))


if __name__=="__main__": unittest.main()
