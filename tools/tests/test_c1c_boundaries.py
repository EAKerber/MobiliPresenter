import copy
import unittest
from pathlib import Path

from tools import coordination, prune_plan, scheduler_snapshot
from tools.tests.test_scheduler_snapshot import pipeline

ROOT = Path(__file__).resolve().parents[2]


class C1CBoundaryTests(unittest.TestCase):
    def test_snapshot_rejects_consumer_time_authority_drift(self):
        machine, _, _, value = pipeline()
        expected = {name: value["sourceHeads"][name]["sha"] for name in scheduler_snapshot.CURRENT_HEAD_KEYS}
        scheduler_snapshot.validate_snapshot(
            value, source_machine=machine, readback_machine=copy.deepcopy(machine), expected_heads=expected
        )
        changed = dict(expected)
        changed["continuation"] = "9" * 40
        with self.assertRaisesRegex(RuntimeError, "SCHEDULER_SNAPSHOT_STALE_CURRENT_CONTINUATION"):
            scheduler_snapshot.validate_snapshot(
                value, source_machine=machine, readback_machine=copy.deepcopy(machine), expected_heads=changed
            )

    def test_open_pr_base_is_dynamic_prune_protection(self):
        state = {
            "schemaVersion": "ProjectState 2.0",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
            "git": {"controlBranch": "main", "activeDevelopmentBranch": None, "protectedBranches": []},
            "published": {"url": "x", "artifactManifest": "ops/published/viewer-next-current.json"},
            "development": {"initiative": "I", "phase": "between-increments", "checkpoint": "C", "nextTransition": "N", "blockers": [], "prNumber": None},
        }
        refs = {"main": "a" * 40, "feature/base": "b" * 40, "work/head": "c" * 40}
        prs = [{"number": 12, "state": "open", "merged": False, "headRef": "work/head", "headSha": "c" * 40, "baseRef": "feature/base"}]
        ancestry = {name: "ancestor-of-control" for name in refs}
        plan = prune_plan.build_prune_plan(state, refs, prs, ancestry, published_source_branch="main")
        by = {entry["branch"]: entry for entry in plan["entries"]}
        self.assertEqual(plan["openPrBases"], ["feature/base"])
        self.assertIn("open-pr-base", by["feature/base"]["protections"])
        self.assertEqual(by["feature/base"]["action"], "keep")

    def test_coordination_runtime_matches_closed_schema_shape(self):
        root = coordination.empty_state()
        extra_root = dict(root, unexpected=True)
        with self.assertRaisesRegex(coordination.CoordinationError, "root fields are invalid"):
            coordination.validate_state(extra_root)
        bad_revision = coordination.empty_state("")
        with self.assertRaisesRegex(coordination.CoordinationError, "revision must be null or a non-empty string"):
            coordination.validate_state(bad_revision)
        owner = {"role": "ui", "session": "s", "branch": None, "pr": None, "unexpected": True}
        with self.assertRaisesRegex(coordination.CoordinationError, "owner fields are invalid"):
            coordination.validate_owner(owner)

    def test_current_bootstrap_has_no_retired_operational_surfaces_or_delta_chain(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        current = (ROOT / "docs/kickstarts/roles/manager-gitops-current.md").read_text(encoding="utf-8")
        v05 = (ROOT / "docs/kickstarts/roles/manager-gitops-v0.5.md").read_text(encoding="utf-8")
        combined = agents + "\n" + current + "\n" + v05
        for retired in ("maintenance_live.py", "scheduler_plan.py --live", "maintenance_inspect.py --remote"):
            self.assertNotIn(retired, combined)
        self.assertIn("manager-gitops-v0.5.md", current)
        self.assertNotIn("manager-gitops-v0.4.md", current)
        self.assertNotIn("manager-gitops-v0.3.md", current)
        self.assertNotIn("manager-gitops-v0.4.md", v05)
        self.assertNotIn("manager-gitops-v0.3.md", v05)


if __name__ == "__main__":
    unittest.main()
