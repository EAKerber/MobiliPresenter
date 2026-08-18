import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT / "tools"
WORKFLOWS_ROOT = ROOT / ".github" / "workflows"

RETIRED_PROJECTSTATE_KEYS = {
    "activeDevelopmentBranch",
    "developmentPrNumber",
    "productInvariants",
    "publishedBranch",
    "preserveBranches",
    "artifactSha256",
    "constraints",
    "toolboxPhase",
    "canonicalState",
}
DEVELOPMENT_EXECUTION_KEYS = {"prNumber", "blockers"}
COMPATIBILITY_SYMBOLS = {
    "validate_v1",
    "validate_v2",
    "validate_v20",
    "validate_v21",
    "validate_compatible",
    "migrate_v1_to_v2",
    "migrate_v20_to_v21",
    "MIGRATION_MAP_PATH",
    "CANDIDATE_V2_SCHEMA_PATH",
    "validate_state_shape",
}
WORKFLOW_FORBIDDEN = RETIRED_PROJECTSTATE_KEYS | {
    "project_state_migration",
    "development.prNumber",
    "development.blockers",
} | COMPATIBILITY_SYMBOLS


def runtime_python_paths():
    return sorted(
        path
        for path in TOOLS_ROOT.rglob("*.py")
        if "tests" not in path.relative_to(TOOLS_ROOT).parts
    )


def workflow_paths():
    return sorted(
        set(WORKFLOWS_ROOT.glob("*.yml")) | set(WORKFLOWS_ROOT.glob("*.yaml"))
    )


def _access_key(node):
    if isinstance(node, ast.Subscript):
        key = node.slice
        return key.value if isinstance(key, ast.Constant) and isinstance(key.value, str) else None
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return node.args[0].value
    return None


def _access_container(node):
    if isinstance(node, ast.Subscript):
        return node.value
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.value
    return None


def _development_aliases(tree):
    aliases = set()
    for node in ast.walk(tree):
        value = None
        targets = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            targets = [node.target]
        if value is not None and _access_key(value) == "development":
            aliases.update(target.id for target in targets if isinstance(target, ast.Name))
    return aliases


def _python_violations(source, label):
    tree = ast.parse(source, filename=label)
    aliases = _development_aliases(tree)
    violations = []
    for node in ast.walk(tree):
        key = _access_key(node)
        if key in RETIRED_PROJECTSTATE_KEYS:
            violations.append(f"{label}:{getattr(node, 'lineno', '?')}:retired-key:{key}")
        if key in DEVELOPMENT_EXECUTION_KEYS:
            container = _access_container(node)
            is_development = _access_key(container) == "development" or (
                isinstance(container, ast.Name) and container.id in aliases
            )
            if is_development:
                violations.append(
                    f"{label}:{getattr(node, 'lineno', '?')}:development-execution:{key}"
                )
        if isinstance(node, ast.Name) and node.id in COMPATIBILITY_SYMBOLS:
            violations.append(
                f"{label}:{getattr(node, 'lineno', '?')}:compatibility-symbol:{node.id}"
            )
        if isinstance(node, ast.Attribute) and node.attr in COMPATIBILITY_SYMBOLS:
            violations.append(
                f"{label}:{getattr(node, 'lineno', '?')}:compatibility-symbol:{node.attr}"
            )
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "project_state_migration" in alias.name:
                    violations.append(
                        f"{label}:{getattr(node, 'lineno', '?')}:migration-import:{alias.name}"
                    )
        if isinstance(node, ast.ImportFrom):
            if "project_state_migration" in str(node.module or ""):
                violations.append(
                    f"{label}:{getattr(node, 'lineno', '?')}:migration-import:{node.module}"
                )
            for alias in node.names:
                if alias.name in COMPATIBILITY_SYMBOLS:
                    violations.append(
                        f"{label}:{getattr(node, 'lineno', '?')}:compatibility-import:{alias.name}"
                    )
    return violations


class ProjectStateConsumerBoundaryTests(unittest.TestCase):
    def test_runtime_discovery_is_dynamic_and_excludes_tests(self):
        relatives = {
            path.relative_to(ROOT).as_posix()
            for path in runtime_python_paths()
        }
        self.assertIn("tools/agent.py", relatives)
        self.assertIn("tools/project_state.py", relatives)
        self.assertIn("tools/git_mutation_plan.py", relatives)
        self.assertTrue(all("/tests/" not in f"/{relative}/" for relative in relatives))

    def test_ast_detector_distinguishes_projectstate_execution_from_work(self):
        legacy = 'development = state["development"]\nvalue = development.get("prNumber")\n'
        work = 'value = work_item.get("prNumber")\nblockers = work_item.get("blockers")\n'
        self.assertTrue(_python_violations(legacy, "legacy.py"))
        self.assertEqual(_python_violations(work, "work.py"), [])

    def test_operational_python_surface_is_closed_against_projectstate_execution_reintroduction(self):
        violations = []
        for path in runtime_python_paths():
            relative = path.relative_to(ROOT).as_posix()
            violations.extend(_python_violations(path.read_text(encoding="utf-8"), relative))
        self.assertEqual(violations, [])

    def test_operational_workflows_do_not_reintroduce_retired_projectstate_contract(self):
        violations = []
        for path in workflow_paths():
            relative = path.relative_to(ROOT).as_posix()
            text = path.read_text(encoding="utf-8")
            for token in sorted(WORKFLOW_FORBIDDEN):
                if token in text:
                    violations.append(f"{relative}:{token}")
        self.assertEqual(violations, [])

    def test_prune_execution_protection_is_work_backed(self):
        text = (ROOT / "tools/prune_plan.py").read_text(encoding="utf-8")
        self.assertIn('reasons.append("active-work")', text)
        self.assertIn("GitHubContinuationAuthority", text)
        self.assertIn("work_graph.active_execution_bindings", text)
        self.assertNotIn("active-development", text)

    def test_live_authority_and_canonical_schema_are_21_only(self):
        state = (ROOT / "ops/state/project.json").read_text(encoding="utf-8")
        schema = (ROOT / "ops/schemas/project-state.schema.json").read_text(encoding="utf-8")
        self.assertIn('"schemaVersion": "ProjectState 2.1"', state)
        self.assertIn('"ProjectState 2.1"', schema)
        self.assertNotIn('"schemaVersion": "ProjectState 2.0"', state)
        for token in ("activeDevelopmentBranch", '"prNumber"', '"blockers"'):
            self.assertNotIn(token, state)
            self.assertNotIn(token, schema)
        self.assertFalse((ROOT / "ops/schemas/project-state-2.0.schema.json").exists())
        self.assertFalse((ROOT / "ops/schemas/project-state-2.1.schema.json").exists())
        self.assertFalse((ROOT / "ops/migrations/project-state-2.0.json").exists())

    def test_migration_machinery_is_retired_after_cutover(self):
        self.assertFalse((ROOT / "tools/project_state_migration.py").exists())
        self.assertFalse((ROOT / "tools/tests/test_project_state_migration.py").exists())


if __name__ == "__main__":
    unittest.main()
