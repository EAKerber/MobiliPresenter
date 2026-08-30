import copy
import unittest

from tools import runtime_capabilities
from tools import runtime_provider_scope


GIT_DATA = [
    "blob-create",
    "commit-create-with-parent",
    "tree-create",
]
EXPECTED_HEAD = [
    "commit-create-with-parent",
    "non-force-ref-update",
    "ref-read",
]
COMPLETE_GIT_CARRIER = sorted(set(GIT_DATA + EXPECTED_HEAD))
SCOPE = ["github.git-data.write", "github.expected-head-write"]


def payload(**providers):
    return {
        "schemaVersion": runtime_capabilities.PROVIDER_OBSERVATIONS_SCHEMA,
        "providers": providers,
    }


def provider(status, features=None, reason=None):
    return {"status": status, "features": features or [], "reason": reason}


class RuntimeProviderScopeD3ATests(unittest.TestCase):
    def test_one_provider_must_satisfy_the_entire_scope(self):
        inspection = runtime_capabilities.build_inspection(
            payload(
                **{
                    "gh-api": provider("PASS", GIT_DATA),
                    "github-connector": provider("PASS", EXPECTED_HEAD),
                }
            )
        )
        self.assertEqual(
            inspection["capabilities"]["github.git-data.write"]["status"], "PASS"
        )
        self.assertEqual(
            inspection["capabilities"]["github.expected-head-write"]["status"], "PASS"
        )

        scope = runtime_provider_scope.resolve_provider_scope(inspection, SCOPE)

        self.assertEqual(scope["status"], "FAIL")
        self.assertEqual(scope["completeProviders"], [])
        self.assertEqual(scope["possibleProviders"], [])
        self.assertEqual(scope["reasonCode"], "NO_SINGLE_PROVIDER_SATISFIES_SCOPE")

    def test_incomplete_common_provider_keeps_scope_unknown(self):
        inspection = runtime_capabilities.build_inspection(
            payload(
                **{
                    "gh-api": provider("PASS", GIT_DATA),
                    "github-connector": provider(
                        "UNKNOWN", reason="PROVIDER_PRESENT_NOT_PROBED"
                    ),
                }
            )
        )

        scope = runtime_provider_scope.resolve_provider_scope(inspection, SCOPE)

        self.assertEqual(scope["status"], "UNKNOWN")
        self.assertEqual(scope["completeProviders"], [])
        self.assertEqual(scope["possibleProviders"], ["github-connector"])
        self.assertEqual(
            scope["reasonCode"], "PROVIDER_SCOPE_OBSERVATION_INCOMPLETE"
        )

    def test_known_complete_provider_makes_scope_pass_even_with_unknown_alternate(self):
        inspection = runtime_capabilities.build_inspection(
            payload(
                **{
                    "gh-api": provider("PASS", COMPLETE_GIT_CARRIER),
                    "github-connector": provider(
                        "UNKNOWN", reason="PROVIDER_PRESENT_NOT_PROBED"
                    ),
                }
            )
        )

        scope = runtime_provider_scope.resolve_provider_scope(inspection, SCOPE)

        self.assertEqual(scope["status"], "PASS")
        self.assertEqual(scope["completeProviders"], ["gh-api"])
        self.assertEqual(
            scope["possibleProviders"], ["gh-api", "github-connector"]
        )
        self.assertFalse(scope["authorizesMutation"])

    def test_multiple_complete_providers_remain_candidates_without_selection(self):
        inspection = runtime_capabilities.build_inspection(
            payload(
                **{
                    "gh-api": provider("PASS", COMPLETE_GIT_CARRIER),
                    "github-connector": provider("PASS", COMPLETE_GIT_CARRIER),
                }
            )
        )

        scope = runtime_provider_scope.resolve_provider_scope(
            inspection, list(reversed(SCOPE))
        )

        self.assertEqual(scope["status"], "PASS")
        self.assertEqual(scope["requiredCapabilities"], sorted(SCOPE))
        self.assertEqual(
            scope["completeProviders"], ["gh-api", "github-connector"]
        )
        self.assertEqual(
            scope["possibleProviders"], ["gh-api", "github-connector"]
        )

    def test_resolution_is_deterministic_and_bound_to_inspection(self):
        inspection = runtime_capabilities.build_inspection(
            payload(**{"gh-api": provider("PASS", COMPLETE_GIT_CARRIER)})
        )

        first = runtime_provider_scope.resolve_provider_scope(
            inspection, list(reversed(SCOPE))
        )
        second = runtime_provider_scope.resolve_provider_scope(
            copy.deepcopy(inspection), SCOPE
        )

        self.assertEqual(first, second)
        self.assertEqual(first["inspectionHash"], inspection["inspectionHash"])
        self.assertFalse(first["authorizesMutation"])

    def test_non_runtime_observed_capability_is_rejected(self):
        inspection = runtime_capabilities.build_inspection(payload())

        with self.assertRaisesRegex(
            RuntimeError,
            "RUNTIME_PROVIDER_SCOPE_CAPABILITY_NOT_RUNTIME_OBSERVED:agent.cycle.hosted",
        ):
            runtime_provider_scope.resolve_provider_scope(
                inspection, ["agent.cycle.hosted"]
            )

    def test_empty_or_duplicate_scope_is_rejected(self):
        inspection = runtime_capabilities.build_inspection(payload())

        with self.assertRaisesRegex(
            RuntimeError, "RUNTIME_PROVIDER_SCOPE_CAPABILITIES_REQUIRED"
        ):
            runtime_provider_scope.resolve_provider_scope(inspection, [])
        with self.assertRaisesRegex(
            RuntimeError, "RUNTIME_PROVIDER_SCOPE_CAPABILITIES_NOT_CANONICAL"
        ):
            runtime_provider_scope.resolve_provider_scope(
                inspection, ["github.ref.read", "github.ref.read"]
            )


if __name__ == "__main__":
    unittest.main()
