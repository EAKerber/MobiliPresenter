from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "ops" / "semantics" / "registry.json"
TEST = ROOT / "tools" / "tests" / "test_agent_semantic_brief.py"


def patch_registry() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    start_marker = '    "routine.inspect": {'
    end_marker = '    "runtime.capabilities.inspect": {'
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    block = text[start:end]
    old = '        "roles": [\n          "manager-gitops"\n        ],'
    new = '        "roles": [\n          "manager-gitops",\n          "ui-ux"\n        ],'
    if new in block and old not in block:
        return
    if block.count(old) != 1:
        raise RuntimeError("ROUTINE_INSPECT_ROLE_FACET_PRECONDITION_FAILED")
    REGISTRY.write_text(text[:start] + block.replace(old, new, 1) + text[end:], encoding="utf-8")


def patch_test() -> None:
    text = TEST.read_text(encoding="utf-8")
    method_name = "    def test_ui_inspect_and_plan_has_closed_required_capability_projection(self):\n"
    if method_name in text:
        return
    anchor = "    def test_required_capability_remains_visible_when_scope_is_missing(self):\n"
    if text.count(anchor) != 1:
        raise RuntimeError("SEMANTIC_BRIEF_TEST_ANCHOR_PRECONDITION_FAILED")
    method = '''    def test_ui_inspect_and_plan_has_closed_required_capability_projection(self):\n        profile = agent_cycle.entry_profile("ui-ux", "inspect-and-plan")\n        context = brief.normalize_context(\n            role="ui-ux",\n            declared_intent="inspect-and-plan",\n            lifecycle_phase=profile["lifecyclePhase"],\n            objects=profile["objects"],\n            operations=profile["operations"],\n            scopes=profile["scope"],\n        )\n        projection = brief.build_projection(context, unknown_runtime())\n        self.assertEqual(projection["missingCoverage"], [])\n        self.assertIn("routine.inspect", projection["required"])\n\n'''
    TEST.write_text(text.replace(anchor, method + anchor, 1), encoding="utf-8")


def main() -> int:
    patch_registry()
    patch_test()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
