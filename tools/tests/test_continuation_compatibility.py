import copy
import unittest
from unittest import mock

from tools import continuation, continuation_transition as transition
from tools.continuation_remote import ContinuationRemoteError, GitHubContinuationAuthority


GOLDEN_HASHES = {
    "create": "e6c33eb1c548e434cbb84b717d955a710dd7020700c93d3f8ef5fe8e0606ea1e",
    "advance": "feeeb34436f30a3703413681b7c0c44a893864f5633e1c1754997fec9c31c454",
    "wait": "c19a4ca50d4bda212a0dd597447851615b485909188ebd2307d8106a554bfb61",
    "handoff": "bf081cf2d5da430600dfb886e157c43ce94bb78bd02ea090860e0f26807370df",
    "resume": "df45dd4c54168e78706b5939538a9f7712e5e70abb970fe32bd139fcff174731",
    "done": "daa690fe6287b9722be7b3e8c23a794b787850bca7594a218a07bb95c31ce6ea",
}


def v01():
    return transition.create("task-one", "developer-ui", ["a", "b"], "do a")["candidate"]


def v02(work_id="task-one", worker="developer-ui", *, depends=None):
    return transition.create(
        work_id, worker, ["a", "b"], "do a",
        schema_version=continuation.CANDIDATE_SCHEMA_VERSION,
        depends_on=depends or [],
    )["candidate"]


class ContinuationCompatibilityTests(unittest.TestCase):
    def test_current_schema_remains_v01(self):
        self.assertEqual(continuation.CURRENT_SCHEMA_VERSION, "ContinuationState 0.1")
        self.assertEqual(continuation.CANDIDATE_SCHEMA_VERSION, "ContinuationState 0.2")
        self.assertEqual(continuation.validate_current(v01()), [])
        self.assertIn("CONTINUATION_SCHEMA_UNSUPPORTED", continuation.validate_current(v02()))

    def test_migration_is_deterministic_and_operationally_equivalent(self):
        source = v01()
        first = continuation.migrate_v01_to_v02(source)
        second = continuation.migrate_v01_to_v02(copy.deepcopy(source))
        self.assertEqual(first, second)
        self.assertEqual(first["workerId"], "developer-ui")
        self.assertEqual(first["dependsOn"], [])
        self.assertEqual(continuation.operational_view(source), continuation.operational_view(first))
        self.assertEqual(source["schemaVersion"], "ContinuationState 0.1")

    def test_invalid_legacy_actor_blocks_migration(self):
        source = v01()
        source["actor"] = "Developer UI"
        self.assertEqual(continuation.validate_v01(source), [])
        with self.assertRaisesRegex(RuntimeError, "CONTINUATION_WORKER_ID_INVALID"):
            continuation.migrate_v01_to_v02(source)

    def test_v01_transition_plan_hashes_are_unchanged(self):
        base = v01()
        create = transition.create("task-one", "developer-ui", ["a", "b"], "do a")
        advance = transition.advance(base, ["a"], "do b", sha="1" * 40, checkpoint="after-a")
        waiting = transition.wait(base, ["external"])
        handed = transition.handoff(base, "developer-engine", "continue b")
        resumed = transition.resume(handed["candidate"], "developer-engine")
        emptied = transition.advance(base, ["a", "b"])["candidate"]
        done = transition.done(emptied)
        actual = {
            "create": create["planHash"], "advance": advance["planHash"], "wait": waiting["planHash"],
            "handoff": handed["planHash"], "resume": resumed["planHash"], "done": done["planHash"],
        }
        self.assertEqual(actual, GOLDEN_HASHES)

    def test_v02_bind_execution_and_restart_are_candidate_only(self):
        bound = transition.bind_execution(v02(), "work/ui/example", 42)["candidate"]
        self.assertEqual(bound["branch"], "work/ui/example")
        self.assertEqual(bound["prNumber"], 42)
        completed = transition.advance(bound, ["a", "b"])["candidate"]
        terminal = transition.done(completed)["candidate"]
        restarted = transition.restart(terminal, ["again"], "repeat")["candidate"]
        self.assertEqual(restarted["status"], "READY")
        self.assertEqual(restarted["remaining"], ["again"])
        with self.assertRaisesRegex(RuntimeError, "RESTART_REQUIRES_V02"):
            transition.restart(transition.advance(v01(), ["a", "b"])["candidate"], ["again"], "repeat")

    def test_dependencies_block_advance_until_done_and_rebuild_with_inventory(self):
        dependency = v02("dep", "developer-engine")
        dependent = v02("child", depends=["dep"])
        with self.assertRaisesRegex(RuntimeError, "DEPENDENCY_NOT_DONE"):
            transition.advance(dependent, ["a"], "do b", inventory=[dependent, dependency])
        dep_empty = transition.advance(dependency, ["a", "b"])["candidate"]
        dep_done = transition.done(dep_empty)["candidate"]
        inventory = [dependent, dep_done]
        plan = transition.advance(dependent, ["a"], "do b", inventory=inventory)
        self.assertEqual(plan["candidate"]["completed"], ["a"])
        self.assertEqual(transition.validate_plan(plan, dependent, bind_before=True, inventory=inventory), plan)
        with self.assertRaisesRegex(RuntimeError, "WORK_GRAPH_INVENTORY_REQUIRED"):
            transition.validate_plan(plan, dependent, bind_before=True)

    def test_live_executor_rejects_v02_before_observation(self):
        plan = transition.create(
            "candidate", "developer-ui", ["x"], "do x",
            schema_version=continuation.CANDIDATE_SCHEMA_VERSION,
        )
        authority = GitHubContinuationAuthority(transport=object())
        with mock.patch.object(authority, "observe") as observe:
            with self.assertRaises(ContinuationRemoteError) as caught:
                authority.apply(plan, plan["planHash"])
        self.assertEqual(caught.exception.code, "CONTINUATION_SCHEMA_NOT_CURRENT")
        observe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
