import unittest

from tools import continuation
from tools import continuation_transition as transition


def base():
    return transition.create("task-one", "developer-ui", ["a", "b"], "do a")["candidate"]


class ContinuationState01Tests(unittest.TestCase):
    def test_create_is_ready_and_requires_work(self):
        value = base()
        self.assertEqual(value["status"], "READY")
        self.assertEqual(value["remaining"], ["a", "b"])
        with self.assertRaisesRegex(RuntimeError, "CREATE_REQUIRES_WORK"):
            transition.create("empty", "actor", [], "nothing")

    def test_advance_moves_work_and_requires_next_when_remaining(self):
        first = transition.advance(base(), ["a"], "do b", sha="1" * 40, checkpoint="after-a")["candidate"]
        self.assertEqual(first["completed"], ["a"])
        self.assertEqual(first["remaining"], ["b"])
        self.assertEqual(first["status"], "IN_PROGRESS")
        with self.assertRaisesRegex(RuntimeError, "NEXT_ACTION_REQUIRED"):
            transition.advance(base(), ["a"])

    def test_wait_and_resume_are_explicit(self):
        waiting = transition.wait(base(), ["external-input"])["candidate"]
        self.assertEqual(waiting["status"], "WAITING")
        resumed = transition.resume(waiting, "developer-ui")["candidate"]
        self.assertEqual(resumed["status"], "IN_PROGRESS")
        self.assertEqual(resumed["blockedBy"], [])

    def test_handoff_requires_target_actor_on_resume(self):
        handed = transition.handoff(base(), "developer-engine", "continue b")["candidate"]
        self.assertEqual(handed["status"], "HANDOFF")
        with self.assertRaisesRegex(RuntimeError, "HANDOFF_ACTOR_MISMATCH"):
            transition.resume(handed, "developer-ui")
        resumed = transition.resume(handed, "developer-engine")["candidate"]
        self.assertEqual(resumed["actor"], "developer-engine")

    def test_done_requires_no_remaining_work(self):
        with self.assertRaisesRegex(RuntimeError, "DONE_REMAINING_WORK"):
            transition.done(base())
        empty = transition.advance(base(), ["a", "b"])["candidate"]
        done = transition.done(empty)["candidate"]
        self.assertEqual(done["status"], "DONE")
        self.assertIsNone(done["nextAction"])

    def test_common_plan_hash_is_stable(self):
        first = transition.handoff(base(), "developer-engine", "continue b")
        second = transition.handoff(base(), "developer-engine", "continue b")
        self.assertEqual(first, second)
        self.assertEqual(first["schemaVersion"], "TransitionPlan 0.1")
        self.assertEqual(first["domain"], "continuation")
        self.assertEqual(first["subject"], {"kind": "continuation", "id": "task-one"})

    def test_local_model_has_no_mutation_surface(self):
        for name in ("create", "advance", "wait", "handoff", "resume", "done", "apply", "plan"):
            self.assertFalse(hasattr(continuation, name), name)

    def test_validation_rejects_inconsistent_handoff(self):
        value = base()
        value["status"] = "HANDOFF"
        self.assertIn("CONTINUATION_HANDOFF_STATE_INVALID", continuation.validate(value))


if __name__ == "__main__":
    unittest.main()
