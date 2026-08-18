from __future__ import annotations

import importlib
import unittest
from pathlib import Path

from tools import test_lifecycle

TEST_ROOT = Path(__file__).resolve().parent


def transitional_targets():
    found = []
    for path in sorted(TEST_ROOT.glob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        module = importlib.import_module(f"tools.tests.{path.stem}")
        for name, value in vars(module).items():
            metadata = test_lifecycle.lifecycle_metadata(value)
            if metadata is not None:
                found.append((f"{path.name}:{name}", metadata))
            if isinstance(value, type) and issubclass(value, unittest.TestCase):
                for member_name, member in vars(value).items():
                    metadata = test_lifecycle.lifecycle_metadata(member)
                    if metadata is not None:
                        found.append((f"{path.name}:{name}.{member_name}", metadata))
    return found


class TestLifecycleTests(unittest.TestCase):
    def test_current_transitional_tests_are_declared_and_not_due(self):
        errors = []
        targets = transitional_targets()
        self.assertTrue(targets, "T0-A must exercise the lifecycle on real transitional tests")
        for label, metadata in targets:
            errors.extend(f"{label}:{error}" for error in test_lifecycle.validate_metadata(metadata))
            condition = metadata.get("retireWhen")
            if isinstance(condition, test_lifecycle.RetirementCondition) and condition.due():
                errors.append(
                    f"TRANSITIONAL_TEST_RETIREMENT_DUE:{label}:{condition.description}"
                )
        self.assertEqual(errors, [])

    def test_due_transitional_assertion_is_skipped_instead_of_restoring_legacy(self):
        condition = test_lifecycle.capability_record_absent("definitely-missing-test-capability")

        @test_lifecycle.transitional_test(
            owner="test-lifecycle",
            reason="prove retirement behavior",
            retire_when=condition,
        )
        def legacy_assertion():
            raise AssertionError("legacy assertion must not execute after retirement")

        self.assertTrue(getattr(legacy_assertion, "__unittest_skip__", False))
        metadata = test_lifecycle.lifecycle_metadata(legacy_assertion)
        self.assertIsNotNone(metadata)
        self.assertTrue(metadata["retireWhen"].due())

    def test_schema_field_predicate_follows_canonical_schema(self):
        present = test_lifecycle.schema_field_absent(
            "ops/schemas/project-state.schema.json", "git.controlBranch"
        )
        retired = test_lifecycle.schema_field_absent(
            "ops/schemas/project-state.schema.json", "git.activeDevelopmentBranch"
        )
        absent = test_lifecycle.schema_field_absent(
            "ops/schemas/project-state.schema.json", "git.field-that-does-not-exist"
        )
        self.assertFalse(present.due())
        self.assertTrue(retired.due())
        self.assertTrue(absent.due())


if __name__ == "__main__":
    unittest.main()
