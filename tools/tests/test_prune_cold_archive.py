import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "prune_plan.py"
spec = importlib.util.spec_from_file_location("prune_plan_cold_archive", MODULE_PATH)
prune = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(prune)


class PruneColdArchiveTests(unittest.TestCase):
    def state(self, protected=None):
        return {
            "schemaVersion": "ProjectState 2.1",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
            "git": {"controlBranch": "main", "protectedBranches": list(protected or [])},
            "published": {"url": "x", "artifactManifest": "ops/published/viewer-next-current.json"},
            "development": {
                "initiative": "I", "phase": "between-increments", "checkpoint": "C",
                "nextTransition": "N",
            },
        }

    def index(self, branch="tmp/fh06-user-artifacts", head="b" * 40, classification="ARTIFACT_HISTORY"):
        return {
            "schemaVersion": "ColdArchiveIndex 0.1",
            "repository": "EAKerber/MobiliPresenter",
            "archiveBranch": "archive/cold",
            "controlSha": "a" * 40,
            "entries": [{
                "branch": branch,
                "headSha": head,
                "classification": classification,
                "evidencePath": "ops/evidence/m6-k-knowledge-salvage-2026-08-18.json",
            }],
        }

    def build(self, refs, *, cold=None, protected=None):
        return prune.build_prune_plan(
            self.state(protected), refs, [], {branch: "diverged" for branch in refs},
            work_items=[], work_authority_complete=True, work_authority_head="f" * 40,
            branch_inventory_complete=True, ancestry_complete=True,
            branch_inventory_source="remote-git-refs", published_source_branch="main",
            cold_archive_evidence=cold or {},
        )

    def test_cold_archive_root_protection_wins_over_strong_ancestry(self):
        refs = {"main": "a" * 40, "archive/cold": "c" * 40}
        ancestry = {"main": "identical-to-control", "archive/cold": "ancestor-of-control"}
        plan = prune.build_prune_plan(
            self.state(), refs, [], ancestry,
            work_items=[], work_authority_complete=True, work_authority_head="f" * 40,
            branch_inventory_complete=True, ancestry_complete=True,
            branch_inventory_source="remote-git-refs", published_source_branch="main",
            cold_archive_evidence={},
        )
        entry = next(item for item in plan["entries"] if item["branch"] == "archive/cold")
        self.assertEqual(entry["action"], "keep")
        self.assertFalse(entry["autoDeleteEligible"])
        self.assertIn("cold-archive-root", entry["protections"])
        self.assertIn("ancestor-of-control", entry["evidence"])

    def test_verified_cold_archive_is_strong_delete_evidence(self):
        refs = {"main": "a" * 40, "archive/cold": "c" * 40, "tmp/fh06-user-artifacts": "b" * 40}
        plan = self.build(refs, cold={"tmp/fh06-user-artifacts": "cold-archive:" + "c" * 40})
        entry = next(item for item in plan["entries"] if item["branch"] == "tmp/fh06-user-artifacts")
        self.assertEqual(entry["action"], "delete-candidate")
        self.assertTrue(entry["autoDeleteEligible"])
        self.assertIn("cold-archive:" + "c" * 40, entry["evidence"])

    def test_protection_wins_over_cold_archive_evidence(self):
        refs = {"main": "a" * 40, "archive/cold": "c" * 40, "tmp/fh06-user-artifacts": "b" * 40}
        plan = self.build(
            refs,
            cold={"tmp/fh06-user-artifacts": "cold-archive:" + "c" * 40},
            protected=["tmp/fh06-user-artifacts"],
        )
        entry = next(item for item in plan["entries"] if item["branch"] == "tmp/fh06-user-artifacts")
        self.assertEqual(entry["action"], "keep")
        self.assertIn("project-state-protected", entry["protections"])

    def test_observer_requires_exact_source_head_and_reachability(self):
        refs = {"main": "a" * 40, "archive/cold": "c" * 40, "tmp/fh06-user-artifacts": "b" * 40}
        payload = json.dumps(self.index())

        def git_ok(*args):
            if args[0] == "show":
                return True, payload
            if args[:2] == ("merge-base", "--is-ancestor"):
                return True, ""
            return False, "unexpected"

        with mock.patch.object(prune, "run_git", side_effect=git_ok):
            evidence = prune.observe_cold_archive(
                refs, "EAKerber/MobiliPresenter", control_branch="main",
            )
        self.assertEqual(evidence, {"tmp/fh06-user-artifacts": "cold-archive:" + "c" * 40})

        stale_refs = dict(refs)
        stale_refs["tmp/fh06-user-artifacts"] = "d" * 40
        with mock.patch.object(prune, "run_git", side_effect=git_ok):
            self.assertEqual(
                prune.observe_cold_archive(stale_refs, "EAKerber/MobiliPresenter", control_branch="main"),
                {},
            )

        def unreachable(*args):
            if args[0] == "show":
                return True, payload
            return False, "not ancestor"

        with mock.patch.object(prune, "run_git", side_effect=unreachable):
            self.assertEqual(
                prune.observe_cold_archive(refs, "EAKerber/MobiliPresenter", control_branch="main"),
                {},
            )

    def test_non_historical_or_malformed_archive_fails_closed(self):
        refs = {"main": "a" * 40, "archive/cold": "c" * 40, "tmp/fh06-user-artifacts": "b" * 40}
        active = json.dumps(self.index(classification="SALVAGE_REQUIRED"))
        malformed = "{not-json"
        for payload in (active, malformed):
            with self.subTest(payload=payload):
                with mock.patch.object(prune, "run_git", return_value=(True, payload)):
                    evidence = prune.observe_cold_archive(
                        refs, "EAKerber/MobiliPresenter", control_branch="main",
                    )
                self.assertEqual(evidence, {})

    def test_live_plan_passes_observed_archive_evidence_without_new_authority(self):
        state = self.state()
        manifest = {
            "schemaVersion": "SourceBuild 1.1", "sourceBranch": "main", "sourceCommit": "a" * 40,
            "sourceArtifact": "viewer-next", "sourceArtifactSha256": "b" * 64,
            "buildCommand": "x", "publishDirectory": "x", "nodeVersion": "22",
        }
        refs = {"main": "a" * 40, "archive/cold": "c" * 40, "tmp/fh06-user-artifacts": "b" * 40}
        ancestry = {branch: "diverged" for branch in refs}
        ancestry["main"] = "identical-to-control"
        archive_proof = {"tmp/fh06-user-artifacts": "cold-archive:" + "c" * 40}
        with mock.patch.object(prune, "load_state", return_value=state), \
             mock.patch.object(prune.publication, "load_manifest", return_value=manifest), \
             mock.patch.object(prune.publication, "publication_view", return_value={"sourceBranch": "main"}), \
             mock.patch.object(prune, "branch_refs_with_source", return_value=(refs, "remote-git-refs")), \
             mock.patch.object(prune, "observe_pull_requests", return_value=(True, [], None)), \
             mock.patch.object(prune, "observe_ancestry", return_value=(ancestry, True)), \
             mock.patch.object(prune, "observe_work", return_value=(True, [], "f" * 40, None)), \
             mock.patch.object(prune, "observe_cold_archive", return_value=archive_proof):
            plan = prune.build_live_plan()
        entry = next(item for item in plan["entries"] if item["branch"] == "tmp/fh06-user-artifacts")
        self.assertEqual(entry["action"], "delete-candidate")
        self.assertIn("cold-archive:" + "c" * 40, entry["evidence"])


if __name__ == "__main__":
    unittest.main()
