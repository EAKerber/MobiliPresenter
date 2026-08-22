import unittest

from tools import runtime_capabilities as rc


def observed(**providers):
    return {"providers": providers}


def provider(status, features=None, reason=None):
    return {"status": status, "features": list(features or []), "reason": reason}


class RuntimeCapabilityCoreTests(unittest.TestCase):
    def test_one_provider_missing_does_not_make_logical_capability_missing(self):
        value = rc._evaluate_capability(
            observed(
                **{
                    "provider-a": provider("FAIL", reason="NOT_PRESENT"),
                    "provider-b": provider("UNKNOWN", reason="NOT_PROBED"),
                }
            ),
            "capability.read",
            {
                "providerRequirements": {
                    "provider-a": ["read"],
                    "provider-b": ["read"],
                }
            },
        )
        self.assertEqual(value["status"], "UNKNOWN")

    def test_any_complete_provider_satisfies_capability(self):
        value = rc._evaluate_capability(
            observed(
                **{
                    "provider-a": provider("PASS", ["read"]),
                    "provider-b": provider("PASS", ["read", "write"]),
                }
            ),
            "capability.read",
            {
                "providerRequirements": {
                    "provider-a": ["read"],
                    "provider-b": ["read"],
                }
            },
        )
        self.assertEqual(value["status"], "PASS")
        self.assertEqual(value["satisfiedProviders"], ["provider-a", "provider-b"])

    def test_observed_providers_missing_requirements_fail(self):
        value = rc._evaluate_capability(
            observed(
                **{
                    "provider-a": provider("PASS", ["read"]),
                    "provider-b": provider("PASS", ["write"]),
                }
            ),
            "capability.transaction",
            {
                "providerRequirements": {
                    "provider-a": ["read", "write"],
                    "provider-b": ["read", "write"],
                }
            },
        )
        self.assertEqual(value["status"], "FAIL")
        self.assertEqual(value["reasonCode"], "NO_SUPPORTED_PROVIDER_SATISFIES_REQUIREMENTS")

    def test_core_is_provider_name_agnostic(self):
        value = rc._evaluate_capability(
            observed(**{"anything": provider("PASS", ["feature-x"])}),
            "capability.synthetic",
            {"providerRequirements": {"anything": ["feature-x"]}},
        )
        self.assertEqual(value["status"], "PASS")
        self.assertEqual(value["satisfiedProviders"], ["anything"])

    def test_provider_specific_requirements_do_not_weaken_other_provider(self):
        value = rc._evaluate_capability(
            observed(
                **{
                    "provider-a": provider("PASS", ["read"]),
                    "provider-b": provider("PASS", ["read"]),
                }
            ),
            "capability.synthetic",
            {
                "providerRequirements": {
                    "provider-a": ["read"],
                    "provider-b": ["read", "readback"],
                }
            },
        )
        self.assertEqual(value["status"], "PASS")
        self.assertEqual(value["satisfiedProviders"], ["provider-a"])


if __name__ == "__main__":
    unittest.main()
