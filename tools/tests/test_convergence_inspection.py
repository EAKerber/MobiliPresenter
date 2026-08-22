from __future__ import annotations

import copy
import unittest

from tools.canonical import stable_hash
from tools.semantics import convergence
from tools.semantics.registry import load_registry


def complete_prune_plan(*, entries=None, open_heads=None, open_bases=None):
    body = {
        "schemaVersion": "GitPrunePlan 0.4",
        "repository": "EAKerber/MobiliPresenter",
        "controlBranch": "main",
        "controlSha": "1" * 40,
        "branchCount": len(entries or []),
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
        "openPrHeads": list(open_heads or []),
        "openPrBases": list(open_bases or []),
        "entries": list(entries or []),
        "note": "test fixture",
    }
    return {**body, "planHash": stable_hash(body)}


def without_alias(registry, semantic_id, term, scope):
    value = copy.deepcopy(registry)
    aliases = value["concepts"][semantic_id].get("aliases", [])
    value["concepts"][semantic_id]["aliases"] = [
        item for item in aliases
        if not (item.get("term") == term and item.get("scope") == scope)
    ]
    return value


def without_lock_surface(registry):
    value = copy.deepcopy(registry)
    value["components"].pop("coordination-lock-cli", None)
    for surface in value.get("toolSurfaces", {}).values():
        bindings = surface.get("bindings") if isinstance(surface, dict) else None
        if isinstance(bindings, list):
            surface["bindings"] = [
                item for item in bindings
                if not (
                    isinstance(item, dict)
                    and item.get("targetKind") == "component"
                    and item.get("target") == "coordination-lock-cli"
                )
            ]
    return value


def with_lock_surface(registry):
    """Build an explicit pre-retirement fixture independent of the live registry."""
    value = copy.deepcopy(registry)
    value["concepts"]["coordination.lease"]["aliases"] = [
        {"term": "lock", "scope": "cli-name", "status": "legacy", "retireBy": "M11"}
    ]
    value["components"]["coordination-lock-cli"] = {
        "module": "tools.lock",
        "owner": "coordination",
        "kind": "cli-adapter",
        "sideEffects": True,
        "readsAuthorities": ["coordination-leases"],
        "writesAuthorities": [],
        "readsResources": [],
        "writesResources": [],
        "produces": [],
        "canonicalWriterFor": [],
        "delegatesTo": ["coordination-cli"],
    }
    value["components"] = {
        key: value["components"][key] for key in sorted(value["components"])
    }
    bindings = value["toolSurfaces"]["python-module-cli"]["bindings"]
    if not any(item.get("target") == "coordination-lock-cli" for item in bindings):
        binding = {
            "targetKind": "component",
            "target": "coordination-lock-cli",
            "capabilities": ["coordination.mutate"],
        }
        insert_at = next(
            (index + 1 for index, item in enumerate(bindings) if item.get("target") == "coordination-cli"),
            len(bindings),
        )
        bindings.insert(insert_at, binding)
    return value


class ConvergenceInspectionTests(unittest.TestCase):
    def inputs(self):
        texts = {
            "tools/lock.py": "legacy implementation",
            "tools/tests/test_lock_cli.py": "from tools import lock\n",
            "tools/tests/test_semantic_branches.py": (
                'def test_legacy():\n'
                '    value = parse_branch_name("ops/example")\n'
                '    self.assertEqual("operations", value["semanticDomain"])\n'
            ),
            "tools/tests/test_integration_reconcile_ops_ci.py": (
                'def test_ops_ci(self):\n'
                '    result = planner.aggregate_ci([], "a" * 40, "ops/test")\n'
                '    self.assertEqual("green", result["status"])\n'
            ),
            "tools/tests/test_prune_plan.py": (
                'def test_fixture(self):\n'
                '    refs = {"ops/old": "b" * 40}\n'
                '    self.assertEqual("review", "review")\n'
            ),
            "tools/integration_reconcile.py": (
                "from tools.semantics.branches import parse_branch_name\n"
            ),
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
        return with_lock_surface(load_registry()), records, texts, complete_prune_plan()

    def build(self, registry=None, texts=None, prune=None):
        current_registry, records, current_texts, current_prune = self.inputs()
        return convergence.build_from_inputs(
            registry=registry or current_registry,
            tracked_records=records,
            texts=texts or current_texts,
            prune=prune or current_prune,
        )

    def test_complete_coverage_can_require_migration(self):
        inspection = self.build()
        self.assertTrue(inspection["coverageComplete"])
        self.assertEqual([], inspection["residues"])
        by_term = {item["alias"]["term"]: item for item in inspection["subjects"]}
        self.assertEqual("PRESENT", by_term["lock"]["aliasPresence"])
        self.assertEqual("PASS", by_term["lock"]["coverageStatus"])
        self.assertEqual("MIGRATION_REQUIRED", by_term["lock"]["retirementReadiness"])
        self.assertEqual("MIGRATION_REQUIRED", by_term["ops"]["retirementReadiness"])
        self.assertEqual(inspection, convergence.validate_inspection(inspection))

    def test_present_alias_without_blockers_is_ready(self):
        registry, _, texts, prune = self.inputs()
        registry = without_lock_surface(registry)
        texts = {
            path: text for path, text in texts.items()
            if path not in {
                "tools/lock.py",
                "tools/tests/test_lock_cli.py",
                "tools/tests/test_semantic_branches.py",
                "tools/tests/test_integration_reconcile_ops_ci.py",
                ".github/workflows/agent-ops.yml",
            }
        }
        inspection = self.build(registry=registry, texts=texts, prune=prune)
        by_term = {item["alias"]["term"]: item for item in inspection["subjects"]}
        self.assertEqual("READY", by_term["lock"]["retirementReadiness"])
        self.assertEqual("READY", by_term["ops"]["retirementReadiness"])

    def test_absent_alias_without_blockers_is_retired(self):
        registry, _, texts, prune = self.inputs()
        registry = without_lock_surface(registry)
        registry = without_alias(registry, "coordination.lease", "lock", "cli-name")
        texts.pop("tools/lock.py")
        texts.pop("tools/tests/test_lock_cli.py")
        inspection = self.build(registry=registry, texts=texts, prune=prune)
        lock = next(item for item in inspection["subjects"] if item["alias"]["term"] == "lock")
        self.assertEqual("ABSENT", lock["aliasPresence"])
        self.assertEqual("RETIRED", lock["retirementReadiness"])

    def test_absent_alias_with_consumer_is_invalid(self):
        registry, _, texts, prune = self.inputs()
        registry = without_alias(registry, "coordination.lease", "lock", "cli-name")
        inspection = self.build(registry=registry, texts=texts, prune=prune)
        lock = next(item for item in inspection["subjects"] if item["alias"]["term"] == "lock")
        self.assertEqual("ABSENT", lock["aliasPresence"])
        self.assertEqual("INVALID", lock["retirementReadiness"])

    def test_workflow_branch_detection_does_not_confuse_ops_path_filter(self):
        _, _, texts, _ = self.inputs()
        patterns = convergence.workflow_branch_patterns(texts[".github/workflows/agent-ops.yml"])
        self.assertEqual(
            ["architecture/**", "experiment/**", "ops/**", "renderer/**", "work/**"],
            patterns,
        )
        self.assertEqual(1, patterns.count("ops/**"))

    def test_legacy_trigger_retirement_requires_no_live_relations(self):
        _, _, texts, _ = self.inputs()
        triggers = convergence.trigger_inventory(texts, load_registry())
        ready = convergence.trigger_retirement_inventory(triggers, complete_prune_plan())
        by_pattern = {item["pattern"]: item for item in ready}
        self.assertEqual("RETIRE_READY", by_pattern["ops/**"]["retirementDisposition"])
        entry = {
            "branch": "renderer/live",
            "sha": "3" * 40,
            "branchIdentity": {},
            "action": "keep",
            "reason": "active work",
            "autoDeleteEligible": False,
            "protections": ["active-work"],
            "ancestryToControl": "diverged",
            "prProvenance": [],
            "evidence": [],
            "duplicateOf": [],
        }
        blocked = convergence.trigger_retirement_inventory(
            triggers,
            complete_prune_plan(entries=[entry]),
        )
        renderer = next(item for item in blocked if item["pattern"] == "renderer/**")
        self.assertEqual("RETAIN", renderer["retirementDisposition"])
        self.assertIn("active-work:renderer/live", renderer["blockingRelations"])

    def test_indirect_integration_reconcile_semantics_is_blocking(self):
        inspection = self.build()
        ops = next(item for item in inspection["subjects"] if item["alias"]["term"] == "ops")
        item = next(
            value for value in ops["consumers"]
            if value["path"] == "tools/tests/test_integration_reconcile_ops_ci.py"
        )
        self.assertEqual("LEGACY_BRANCH_BEHAVIOR_ASSERTION", item["class"])
        self.assertTrue(item["blocking"])

    def test_neutral_ops_fixture_is_visible_but_nonblocking(self):
        inspection = self.build()
        ops = next(item for item in inspection["subjects"] if item["alias"]["term"] == "ops")
        item = next(
            value for value in ops["consumers"]
            if value["path"] == "tools/tests/test_prune_plan.py"
        )
        self.assertEqual("LEGACY_BRANCH_REFERENCE", item["class"])
        self.assertFalse(item["blocking"])

    def test_runtime_branch_parser_consumer_is_visible_but_nonblocking(self):
        inspection = self.build()
        ops = next(item for item in inspection["subjects"] if item["alias"]["term"] == "ops")
        item = next(
            value for value in ops["consumers"]
            if value["path"] == "tools/integration_reconcile.py"
        )
        self.assertEqual("SEMANTIC_BRANCH_CONSUMER", item["class"])
        self.assertFalse(item["blocking"])

    def test_documentation_reference_is_visible_but_nonblocking(self):
        registry, records, texts, prune = self.inputs()
        texts["docs/adr/example.md"] = "Run `python tools/lock.py status --json` while migrating.\n"
        records.append({"path": "docs/adr/example.md", "contentHash": "0" * 64})
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
        inspection = self.build()
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
        inspection = self.build()
        tampered = copy.deepcopy(inspection)
        tampered["coverageComplete"] = False
        with self.assertRaisesRegex(RuntimeError, "CONVERGENCE_INSPECTION_COVERAGE_STATUS_MISMATCH"):
            convergence.validate_inspection(tampered)


if __name__ == "__main__":
    unittest.main()
