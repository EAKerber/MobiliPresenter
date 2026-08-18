import unittest

from tools import work_graph


def item(work_id, status="READY", *, depends=None, branch=None, pr=None):
    return {
        "id": work_id,
        "workerId": "developer-ui",
        "status": status,
        "branch": branch,
        "prNumber": pr,
        "dependsOn": list(depends or []),
        "completed": [],
        "remaining": [] if status == "DONE" else ["work"],
        "nextAction": None if status == "DONE" else "work",
        "lastKnownGood": {"sha": None, "checkpoint": None},
        "blockers": ["external"] if status == "WAITING" else [],
        "handoffToWorkerId": "developer-engine" if status == "HANDOFF" else None,
    }


class WorkGraphTests(unittest.TestCase):
    def test_empty_graph(self):
        graph = work_graph.build([])
        self.assertEqual(graph["schemaVersion"], "WorkGraph 0.1")
        self.assertEqual(graph["nodes"], [])

    def test_independent_work_is_runnable(self):
        graph = work_graph.build([item("a"), item("b")])
        self.assertEqual(graph["runnable"], ["a", "b"])

    def test_dependency_controls_runnable_state(self):
        blocked = work_graph.build([item("a", depends=["b"]), item("b")])
        self.assertEqual(blocked["dependencyBlocked"], ["a"])
        self.assertEqual(blocked["runnable"], ["b"])
        ready = work_graph.build([item("a", depends=["b"]), item("b", "DONE")])
        self.assertEqual(ready["runnable"], ["a"])

    def test_missing_self_and_cycle_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, "DEPENDENCY_MISSING"):
            work_graph.build([item("a", depends=["missing"])])
        with self.assertRaisesRegex(RuntimeError, "SELF_DEPENDENCY"):
            work_graph.build([item("a", depends=["a"])])
        with self.assertRaisesRegex(RuntimeError, "WORK_GRAPH_CYCLE"):
            work_graph.build([item("a", depends=["b"]), item("b", depends=["a"])])

    def test_active_execution_identity_is_unique(self):
        with self.assertRaisesRegex(RuntimeError, "ACTIVE_BRANCH_CONFLICT"):
            work_graph.build([item("a", branch="work/ui/x"), item("b", branch="work/ui/x")])
        with self.assertRaisesRegex(RuntimeError, "ACTIVE_PR_CONFLICT"):
            work_graph.build([item("a", pr=7, branch="work/ui/a"), item("b", pr=7, branch="work/ui/b")])

    def test_active_execution_bindings_are_derived_and_terminal_items_are_excluded(self):
        bindings = work_graph.active_execution_bindings([
            item("b", "WAITING", branch="work/ui/b", pr=8),
            item("a", "IN_PROGRESS", branch="work/ui/a", pr=7),
            item("done", "DONE", branch="work/ui/old", pr=6),
        ])
        self.assertEqual(bindings, [
            {"workId": "a", "workerId": "developer-ui", "status": "IN_PROGRESS", "branch": "work/ui/a", "prNumber": 7},
            {"workId": "b", "workerId": "developer-ui", "status": "WAITING", "branch": "work/ui/b", "prNumber": 8},
        ])

    def test_terminal_items_may_share_historical_identity(self):
        graph = work_graph.build([
            item("a", "DONE", branch="work/ui/old", pr=7),
            item("b", "DONE", branch="work/ui/old", pr=7),
        ])
        self.assertEqual(graph["terminal"], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
