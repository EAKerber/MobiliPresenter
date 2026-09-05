import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLE_DIR = ROOT / "docs" / "kickstarts" / "roles"


class BootstrapBoundaryTests(unittest.TestCase):
    def _role_contracts(self):
        return sorted(ROLE_DIR.glob("*.md"))

    def test_role_contracts_are_direct_without_pointer_or_version_copies(self):
        contracts = self._role_contracts()
        self.assertTrue(contracts, "at least one direct role contract must exist")
        self.assertEqual(list(ROLE_DIR.glob("*-current.md")), [])
        self.assertEqual(list(ROLE_DIR.glob("*-v*.md")), [])
        self.assertTrue((ROLE_DIR / "manager-gitops.md").is_file())
        self.assertTrue((ROLE_DIR / "ui-ux.md").is_file())

    def test_role_contracts_do_not_copy_mutable_project_direction(self):
        state = json.loads((ROOT / "ops" / "state" / "project.json").read_text(encoding="utf-8"))
        needles = {
            state["development"]["checkpoint"],
            state["development"]["nextTransition"],
        }
        for contract in self._role_contracts():
            text = contract.read_text(encoding="utf-8")
            for needle in needles:
                with self.subTest(contract=contract.name, needle=needle):
                    self.assertNotIn(
                        needle,
                        text,
                        f"{contract.name} must define role semantics, not copy mutable ProjectState direction",
                    )

    def test_manager_bootstrap_uses_agent_cycle_without_copying_runtime_versions(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        manager = (ROLE_DIR / "manager-gitops.md").read_text(encoding="utf-8")
        self.assertTrue((ROOT / "tools" / "agent_cycle.py").is_file())
        self.assertTrue((ROOT / "tools" / "semantics" / "brief.py").is_file())
        self.assertIn("python3 tools/agent.py begin", manager)
        self.assertIn("docs/kickstarts/roles/<role>.md", agents)
        for copied_runtime_contract in (
            "AgentCycleContext 0.1",
            "AgentCycleContext 0.2",
            "AgentCycleContext 0.3",
            "RuntimeObservationBundle 0.1",
            "GitMutationBundle 0.1",
        ):
            self.assertNotIn(copied_runtime_contract, manager)

    def test_readme_is_a_cold_start_router_not_a_mutable_authority_copy(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        state = json.loads((ROOT / "ops" / "state" / "project.json").read_text(encoding="utf-8"))
        manifest = json.loads(
            (ROOT / state["published"]["artifactManifest"]).read_text(encoding="utf-8")
        )
        self.assertIn("python3 tools/agent.py status", readme)
        self.assertIn("python3 tools/agent.py begin --role <role> --intent <intent> --json", readme)
        self.assertIn("readiness.nextSafeAction", readme)
        self.assertIn("docs/kickstarts/roles/<role>.md", readme)
        self.assertNotIn("docs/kickstarts/roles/*-current.md", readme)
        for mutable in (
            state["development"]["checkpoint"],
            state["development"]["nextTransition"],
            manifest["release"],
            manifest["sourceBranch"],
            manifest["sourceBase"],
        ):
            self.assertNotIn(mutable, readme)

    def test_bootstrap_discovers_capabilities_without_provider_authority_leak(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        manager = (ROLE_DIR / "manager-gitops.md").read_text(encoding="utf-8")
        self.assertTrue((ROOT / "tools" / "runtime_capabilities.py").is_file())
        self.assertIn("provider concreto não prova ausência da capability lógica", agents)
        self.assertIn("Provider alternativo não pode enfraquecer", agents)
        self.assertIn("capabilities/surfaces", manager)
        self.assertIn("providers/fallbacks reconhecidos", manager)

    def test_bootstrap_has_no_retired_operational_surfaces(self):
        combined = "\n".join(
            [
                (ROOT / "AGENTS.md").read_text(encoding="utf-8"),
                *(path.read_text(encoding="utf-8") for path in self._role_contracts()),
            ]
        )
        for retired in (
            "maintenance_live.py",
            "scheduler_plan.py --live",
            "maintenance_inspect.py --remote",
        ):
            self.assertNotIn(retired, combined)

    def test_multi_path_contract_lives_in_tooling_not_role_markdown(self):
        manager = (ROLE_DIR / "manager-gitops.md").read_text(encoding="utf-8")
        self.assertTrue((ROOT / "tools" / "git_mutation_bundle.py").is_file())
        self.assertNotIn("GitMutationBundle 0.1", manager)
        self.assertNotIn("verify-tree", manager)
        self.assertNotIn("verify-readback", manager)
        self.assertIn("paved path corrente", manager)


if __name__ == "__main__":
    unittest.main()
