import copy
import unittest
from tools import runtime_capabilities, runtime_provider_adapter, runtime_provider_scope
from tools.semantics.registry import load_registry

GITHUB_SURFACE = "github-connector-tools"
GIT_SCOPE = ["github.git-data.write", "github.expected-head-write"]
MUTATION_SCOPE = GIT_SCOPE + ["github.mutation-readback"]

class RuntimeProviderAdapterD3BTests(unittest.TestCase):
    def test_complete_connector_surface_materializes_registry_features(self):
        registry = load_registry()
        expected = registry["toolSurfaces"][GITHUB_SURFACE]["features"]
        observed = runtime_provider_adapter.observations_from_tool_surfaces(
            [GITHUB_SURFACE], inventory_complete=True
        )
        self.assertEqual(observed["providers"]["github-connector"]["features"], expected)
        self.assertEqual(observed["providers"]["github-connector"]["status"], "PASS")
        self.assertIsNone(observed["providers"]["github-connector"]["reason"])

    def test_complete_connector_surface_satisfies_d3a_git_scope(self):
        observed = runtime_provider_adapter.observations_from_tool_surfaces(
            [GITHUB_SURFACE], inventory_complete=True
        )
        inspection = runtime_capabilities.build_inspection(observed)
        scope = runtime_provider_scope.resolve_provider_scope(inspection, MUTATION_SCOPE)
        self.assertEqual(scope["status"], "PASS")
        self.assertEqual(scope["completeProviders"], ["github-connector"])
        self.assertFalse(scope["authorizesMutation"])

    def test_incomplete_inventory_preserves_unknown_and_no_features(self):
        observed = runtime_provider_adapter.observations_from_tool_surfaces(
            [GITHUB_SURFACE], inventory_complete=False
        )
        record = observed["providers"]["github-connector"]
        self.assertEqual(record["status"], "UNKNOWN")
        self.assertEqual(record["features"], [])
        self.assertEqual(record["reason"], "TOOL_SURFACE_INVENTORY_INCOMPLETE")
        inspection = runtime_capabilities.build_inspection(observed)
        scope = runtime_provider_scope.resolve_provider_scope(inspection, GIT_SCOPE)
        self.assertEqual(scope["status"], "UNKNOWN")
        self.assertEqual(scope["completeProviders"], [])
        self.assertEqual(scope["possibleProviders"], ["gh-api", "github-connector"])

    def test_unobserved_providers_are_not_invented(self):
        observed = runtime_provider_adapter.observations_from_tool_surfaces(
            [GITHUB_SURFACE], inventory_complete=True
        )
        self.assertEqual(set(observed["providers"]), {"github-connector"})
        inspection = runtime_capabilities.build_inspection(observed)
        self.assertEqual(inspection["providers"]["gh-api"]["status"], "UNKNOWN")
        self.assertEqual(inspection["providers"]["gh-api"]["reason"], "PROVIDER_NOT_OBSERVED")

    def test_surface_order_is_normalized_and_output_is_deterministic(self):
        registry = load_registry()
        same_provider = [
            surface_id for surface_id, item in registry["toolSurfaces"].items()
            if item["provider"] == "github-connector"
        ]
        self.assertTrue(same_provider)
        first = runtime_provider_adapter.observations_from_tool_surfaces(
            list(reversed(same_provider)), inventory_complete=True
        )
        second = runtime_provider_adapter.observations_from_tool_surfaces(
            list(same_provider), inventory_complete=True
        )
        self.assertEqual(first, second)

    def test_unknown_duplicate_and_invalid_completeness_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, "RUNTIME_PROVIDER_SURFACE_UNKNOWN:not-registered"):
            runtime_provider_adapter.observations_from_tool_surfaces(
                ["not-registered"], inventory_complete=True
            )
        with self.assertRaisesRegex(RuntimeError, "RUNTIME_PROVIDER_SURFACES_DUPLICATE"):
            runtime_provider_adapter.observations_from_tool_surfaces(
                [GITHUB_SURFACE, GITHUB_SURFACE], inventory_complete=True
            )
        with self.assertRaisesRegex(RuntimeError, "RUNTIME_PROVIDER_SURFACE_INVENTORY_COMPLETENESS_INVALID"):
            runtime_provider_adapter.observations_from_tool_surfaces(
                [GITHUB_SURFACE], inventory_complete="yes"  # type: ignore[arg-type]
            )

    def test_result_is_existing_provider_observation_not_new_authority(self):
        observed = runtime_provider_adapter.observations_from_tool_surfaces(
            [GITHUB_SURFACE], inventory_complete=True
        )
        self.assertEqual(observed["schemaVersion"], runtime_capabilities.PROVIDER_OBSERVATIONS_SCHEMA)
        self.assertNotIn("semanticAuthority", observed)
        self.assertNotIn("authorizesMutation", observed)
        tampered = copy.deepcopy(observed)
        tampered["providers"]["github-connector"]["features"].append("not-a-feature")
        with self.assertRaises(RuntimeError):
            runtime_capabilities.validate_provider_observations(tampered)

if __name__ == "__main__":
    unittest.main()
