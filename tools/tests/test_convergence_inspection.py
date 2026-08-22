from __future__ import annotations

import copy
import unittest

from tools.canonical import stable_hash
from tools.semantics import convergence
from tools.semantics.registry import load_registry


def complete_prune_plan():
    body = {
        "schemaVersion": "GitPrunePlan 0.4",
        "repository": "EAKerber/MobiliPresenter",
        "controlBranch": "main",
        "controlSha": "1" * 40,
        "branchCount": 0,
        "observations": {
            "complete": True,
            "branchInventoryComplete": True,
            "branchInventorySource": "test",
            "prHistoryComplete": True,
            "prHistoryError": None,
            "ancestryComplete": True,
            "workAuthorityComplete": True,
            "workAuthorityHead": "2" * 40,
            "workAuthorityError": None,
        },
        "execution": {
            "executorAvailable": True,
            "requiresPlanFile": True,
            "requiresExpectedPlan": True,
            "requiresExplicitAuthorization": True,
        },
        "openPrHeads": [],
        "openPrBases": [],
        "entries": [],
        "note": "test fixture",
    }
    return {**body, "planHash": stable_hash(body)}


class ConvergenceInspectionTests(unittest.TestCase):
    def inputs(self):
        texts = {
            "tools/lock.py": "legacy implementation",
            "tools/tests/test_lock_cli.py": "from tools import lock\n",
            "tools/tests/test_semantic_branches.py": 'value = parse_branch_name("ops/example")\n',
            "tools/coordination_ci.py": 'payload["error"] = "LOCK_OWNERSHIP_VIOLATION"\n',
            ".github/workflows/agent-ops.yml": (
                "on:\n"
                "  push:\n"
                "    branches: ['renderer/**','architecture/**','ops/**','work/**','experiment/**']\n"
                "    paths: ['ops/**','tools/**']\n"
            ),
            "docs/kickstarts/roles/manager-gitops-current.md": "pointer only\n",
            "docs/kickstarts/roles/ui-ux-current.md": "pointer only\n",
        }
        records = [
            {"path": path, "contentHash": "0" * 64}
            for path in sorted(texts)
        ]
        return load_registry(), records, texts, complete_prune_plan()

    def test_complete_coverage_can_require_migration(self):
        registry, records, texts, prune = self.inputs()
        inspection = convergence.build_from_inputs(
            registry=registry,
            tracked_records=records,
            texts=texts,
            prune=prune,
        )
        self.assertTrue(inspection["coverageComplete"])
        self.assertEqual([], inspection["residues"])
        by_term = {item["alias"]["term"]: item for item in inspection["subjects"]}
        self.assertEqual("PASS", by_term["lock"]["coverageStatus"])
        self.assertEqual("MIGRATION_REQUIRED", by_term["lock"]["retirementReadiness"])
        self.assertEqual("MIGRATION_REQUIRED", by_term["ops"]["retirementReadiness"])
        self.assertEqual(inspection, convergence.validate_inspection(inspection))

    def test_workflow_branch_detection_does_not_confuse_ops_path_filter(self):
        _, _, texts, _ = self.inputs()
        patterns = convergence.workflow_branch_patterns(texts[".github/workflows/agent-ops.yml"])
        self.assertEqual(
            ["architecture/**", "experiment/**", "ops/**", "renderer/**", "work/**"],
            patterns,
        )
        self.assertEqual(1, patterns.count("ops/**"))

    def test_documentation_reference_is_visible_but_nonblocking(self):
        registry, records, texts, prune = self.inputs()
        texts["docs/adr/example.md"] = "Run `python tools/lock.py status --json` while migrating.\n"
        inspection = convergence.build_from_inputs(
            registry=registry,
            tracked_records=records,
            texts=texts,
            prune=prune,
        )
        lock = next(item for item in inspection["subjects"] if item["alias"]["term"] == "lock")
        ref = next(item for item in lock["consumers"] if item["path"] == "docs/adr/example.md")
        self.assertEqual("DOCUMENTATION_REFERENCE", ref["class"])
        self.assertFalse(ref["blocking"])

    def test_detector_literals_do_not_create_python_lock_consumers(self):
        self.assertFalse(convergence._python_imports_lock('LOCK_CLI_RE = re.compile(r"tools/lock.py")'))

    def test_lock_error_code_is_not_treated_as_cli_consumer(self):
        registry, records, texts, prune = self.inputs()
        inspection = convergence.build_from_inputs(
            registry=registry,
            tracked_records=records,
            texts=texts,
            prune=prune,
        )
        lock = next(item for item in inspection["subjects"] if item["alias"]["term"] == "lock")
        paths = {item["path"] for item in lock["consumers"]}
        self.assertNotIn("tools/coordination_ci.py", paths)

    def test_incomplete_runtime_observation_never_claims_ready(self):
        registry, records, texts, prune = self.inputs()
        prune["observations"]["workAuthorityComplete"] = False
        prune["observations"]["complete"] = False
        body = {key: value for key, value in prune.items() if key != "planHash"}
        prune["planHash"] = stable_hash(body)
        inspection = convergence.build_from_inputs(
            registry=registry,
            tracked_records=records,
            texts=texts,
            prune=prune,
        )
        self.assertFalse(inspection["coverageComplete"])
        self.assertTrue(all(item["coverageStatus"] == "UNKNOWN" for item in inspection["subjects"]))
        self.assertTrue(all(item["retirementReadiness"] == "UNKNOWN" for item in inspection["subjects"]))

    def test_current_pointer_mutable_direction_is_explicit_residue(self):
        registry, records, texts, prune = self.inputs()
        texts["docs/kickstarts/roles/ui-ux-current.md"] = (
            "checkpoint `M9-OLD`; next declared transition is `something`\n"
        )
        inspection = convergence.build_from_inputs(
            registry=registry,
            tracked_records=records,
            texts=texts,
            prune=prune,
        )
        self.assertEqual(
            "CURRENT_POINTER_MUTABLE_DIRECTION",
            inspection["residues"][0]["kind"],
        )

    def test_tampered_inspection_is_rejected(self):
        registry, records, texts, prune = self.inputs()
        inspection = convergence.build_from_inputs(
            registry=registry,
            tracked_records=records,
            texts=texts,
            prune=prune,
        )
        tampered = copy.deepcopy(inspection)
        tampered["coverageComplete"] = False
        with self.assertRaisesRegex(RuntimeError, "CONVERGENCE_INSPECTION_COVERAGE_STATUS_MISMATCH"):
            convergence.validate_inspection(tampered)


if __name__ == "__main__":
    unittest.main()
