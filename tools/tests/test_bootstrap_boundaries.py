import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLE_DIR = ROOT / "docs" / "kickstarts" / "roles"
CURRENT_TARGET_RE = re.compile(
    r"\]\(\./([A-Za-z0-9._-]+-v[A-Za-z0-9._-]+\.md)\)"
)


def resolve_current_target(current_path):
    current = current_path.read_text(encoding="utf-8")
    targets = CURRENT_TARGET_RE.findall(current)
    if len(targets) != 1:
        raise AssertionError(
            f"{current_path.name} must point to exactly one versioned role document; got {targets}"
        )
    return current, current_path.parent / targets[0]


class BootstrapBoundaryTests(unittest.TestCase):
    def test_current_role_pointers_resolve_existing_versioned_docs(self):
        current_paths = sorted(ROLE_DIR.glob("*-current.md"))
        self.assertTrue(current_paths, "at least one current role pointer must exist")
        for current_path in current_paths:
            with self.subTest(current=current_path.name):
                _, target = resolve_current_target(current_path)
                self.assertTrue(target.is_file(), f"missing current target: {target.name}")
                self.assertNotEqual(current_path, target)

    def test_current_bootstrap_has_no_retired_operational_surfaces_or_delta_chain(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        current_path = ROLE_DIR / "manager-gitops-current.md"
        current, target = resolve_current_target(current_path)
        versioned = target.read_text(encoding="utf-8")
        combined = agents + "\n" + current + "\n" + versioned
        for retired in (
            "maintenance_live.py",
            "scheduler_plan.py --live",
            "maintenance_inspect.py --remote",
        ):
            self.assertNotIn(retired, combined)

        self.assertTrue(target.name.startswith("manager-gitops-v"))
        older_or_other_versions = sorted(
            path.name
            for path in ROLE_DIR.glob("manager-gitops-v*.md")
            if path.name != target.name
        )
        for version_name in older_or_other_versions:
            self.assertNotIn(version_name, current)
            self.assertNotIn(version_name, versioned)

    def test_current_bootstrap_discovers_capability_before_declaring_provider_failure_global(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        current_path = ROLE_DIR / "manager-gitops-current.md"
        _, target = resolve_current_target(current_path)
        versioned = target.read_text(encoding="utf-8")
        runtime_tool = ROOT / "tools" / "runtime_capabilities.py"
        self.assertTrue(runtime_tool.is_file())
        self.assertIn("RuntimeCapabilityInspection", versioned)
        self.assertIn("GH_NOT_FOUND != GITHUB_TRANSPORT_UNAVAILABLE", versioned)
        self.assertIn("provider concreto não prova ausência da capability lógica", agents)
        self.assertIn("--runtime-providers", versioned)


if __name__ == "__main__":
    unittest.main()
