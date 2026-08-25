from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENT_TOOLS_ROOT = ROOT / "tools" / "agent_tools"


class AgentToolEffectiveModeCallerTests(unittest.TestCase):
    def test_all_production_effective_mode_callers_bind_declared_intent(self):
        missing: list[str] = []
        for path in sorted(AGENT_TOOLS_ROOT.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                is_effective_mode = (
                    isinstance(func, ast.Attribute) and func.attr == "effective_mode"
                ) or (
                    isinstance(func, ast.Name) and func.id == "effective_mode"
                )
                if not is_effective_mode:
                    continue
                has_intent = len(node.args) >= 3 or any(
                    keyword.arg == "declared_intent" for keyword in node.keywords
                )
                if not has_intent:
                    relative = path.relative_to(ROOT)
                    missing.append(f"{relative}:{node.lineno}")
        self.assertEqual(
            missing,
            [],
            "production effective_mode callers must bind declaredIntent explicitly: "
            + ", ".join(missing),
        )


if __name__ == "__main__":
    unittest.main()
