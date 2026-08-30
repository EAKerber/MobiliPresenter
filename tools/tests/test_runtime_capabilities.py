import copy
import unittest
from unittest import mock

from tools import runtime_capabilities as rc


def payload(**providers):
    return {"schemaVersion": rc.PROVIDER_OBSERVATIONS_SCHEMA, "providers": providers}


def provider(status, features=None, reason=None):
    return {"status": status, "features": features or [], "reason": reason}


CONNECTOR_GIT_DATA = [
    "artifact-read",
    "blob-create",
    "ci-read",
    "commit-create-with-parent",
    "content-read",
    "content-readback",
    "non-force-ref-update",
    "pr-read",
    "ref-read",
    "repository-read",
    "tree-create",
]


class RuntimeCapabilityTests(unittest.TestCase):
    def test_missing_gh_does_not_make_github_capability_fail_when_connector_unobserved(self):
        observed = payload(
            **{"gh-api": provider("FAIL", reason="PROVIDER_NOT_PRESENT")}
        )
        inspection = rc.build_inspection(observed)
        self.assertEqual(
            inspection["capabilities"]["github.repository.read"]["status"], "UNKNOWN"
        )
        self.assertEqual(
            inspection["capabilities"]["git.direct-mutation"]["status"], "UNKNOWN"
        )

    def test_connector_read_only_can_satisfy_read_without_satisfying_mutation(self):
        observed = payload(
            **{
                "gh-api": provider("FAIL", reason="PROVIDER_NOT_PRESENT"),
                "github-connector": provider(
                    "PASS", ["repository-read", "ref-read", "pr-read"]
                ),
            }
        )
        inspection = rc.build_inspection(observed)
        self.assertEqual(
            inspection["capabilities"]["github.repository.read"]["status"], "PASS"
        )
        self.assertEqual(
            inspection["capabilities"]["git.direct-mutation"]["status"], "FAIL"
        )

    def test_complete_connector_git_data_path_satisfies_direct_mutation(self):
        observed = payload(
            **{
                "gh-api": provider("FAIL", reason="PROVIDER_NOT_PRESENT"),
                "github-connector": provider("PASS", CONNECTOR_GIT_DATA),
            }
        )
        inspection = rc.build_inspection(observed)
        direct = inspection["capabilities"]["git.direct-mutation"]
        self.assertEqual(direct["status"], "PASS")
        self.assertEqual(direct["satisfiedProviders"], ["github-connector"])

    def test_missing_create_tree_prevents_direct_mutation_pass(self):
        features = [item for item in CONNECTOR_GIT_DATA if item != "tree-create"]
        observed = payload(
            **{
                "gh-api": provider("FAIL", reason="PROVIDER_NOT_PRESENT"),
                "github-connector": provider("PASS", features),
            }
        )
        inspection = rc.build_inspection(observed)
        self.assertEqual(
            inspection["capabilities"]["git.direct-mutation"]["status"], "FAIL"
        )

    def test_missing_independent_readback_prevents_direct_mutation_pass(self):
        features = [item for item in CONNECTOR_GIT_DATA if item != "content-readback"]
        observed = payload(
            **{
                "gh-api": provider("FAIL", reason="PROVIDER_NOT_PRESENT"),
                "github-connector": provider("PASS", features),
            }
        )
        inspection = rc.build_inspection(observed)
        self.assertEqual(
            inspection["capabilities"]["git.direct-mutation"]["status"], "FAIL"
        )

    def test_force_only_provider_is_not_equivalent_to_expected_head_write(self):
        value = rc._evaluate_capability(
            {
                "providers": {
                    "synthetic-provider": provider("PASS", ["force-ref-update"])
                }
            },
            "github.expected-head-write",
            {
                "providerRequirements": {
                    "synthetic-provider": ["non-force-ref-update"]
                }
            },
        )
        self.assertEqual(value["status"], "FAIL")
        self.assertEqual(
            value["reasonCode"], "NO_SUPPORTED_PROVIDER_SATISFIES_REQUIREMENTS"
        )

    def test_connector_git_data_without_remote_time_keeps_coordination_mutation_blocked(self):
        observed = payload(
            **{
                "gh-api": provider("FAIL", reason="PROVIDER_NOT_PRESENT"),
                "github-connector": provider("PASS", CONNECTOR_GIT_DATA),
            }
        )
        inspection = rc.build_inspection(observed)
        self.assertEqual(
            inspection["capabilities"]["git.direct-mutation"]["status"], "PASS"
        )
        self.assertEqual(
            inspection["capabilities"]["github.remote-time"]["status"], "FAIL"
        )
        self.assertEqual(
            inspection["capabilities"]["coordination.mutate"]["status"], "FAIL"
        )

    def test_unobserved_remote_time_provider_keeps_coordination_unknown(self):
        observed = payload(
            **{
                "gh-api": provider("UNKNOWN", reason="PROVIDER_PRESENT_NOT_PROBED"),
            }
        )
        inspection = rc.build_inspection(observed)
        self.assertEqual(
            inspection["capabilities"]["coordination.mutate"]["status"], "UNKNOWN"
        )

    def test_validated_artifact_provider_satisfies_artifact_read_only(self):
        observed = payload(
            **{
                "gh-api": provider("FAIL", reason="PROVIDER_NOT_PRESENT"),
                "github-connector": provider("FAIL", reason="PROVIDER_NOT_PRESENT"),
                "validated-workflow-artifact": provider("PASS", ["artifact-read"]),
            }
        )
        inspection = rc.build_inspection(observed)
        self.assertEqual(
            inspection["capabilities"]["github.artifact.read"]["status"], "PASS"
        )
        self.assertEqual(
            inspection["capabilities"]["supervisor.snapshot-consume"]["status"],
            "FAIL",
        )

    def test_unverified_provider_cannot_claim_features(self):
        with self.assertRaisesRegex(RuntimeError, "RUNTIME_PROVIDER_UNVERIFIED_FEATURES"):
            rc.validate_provider_observations(
                payload(
                    **{
                        "github-connector": provider(
                            "UNKNOWN", ["repository-read"], "NOT_PROBED"
                        )
                    }
                )
            )

    def test_provider_cannot_claim_feature_outside_registry_vocabulary(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "RUNTIME_PROVIDER_FEATURE_UNKNOWN:github-connector:force-ref-update",
        ):
            rc.validate_provider_observations(
                payload(
                    **{
                        "github-connector": provider(
                            "PASS", ["force-ref-update"]
                        )
                    }
                )
            )

    def test_inspection_is_deterministic_and_read_only(self):
        observed = payload(
            **{
                "github-connector": provider("PASS", CONNECTOR_GIT_DATA),
                "gh-api": provider("FAIL", reason="PROVIDER_NOT_PRESENT"),
            }
        )
        first = rc.build_inspection(observed)
        second = rc.build_inspection(copy.deepcopy(observed))
        self.assertEqual(first, second)
        self.assertFalse(first["authorizesMutation"])
        self.assertEqual(rc.validate_inspection(first), first)

    def test_local_absent_gh_is_provider_failure_not_global_github_failure(self):
        with mock.patch("tools.runtime_capabilities.shutil.which") as which:
            which.side_effect = lambda name: "/usr/bin/git" if name == "git" else None
            inspection = rc.build_inspection(rc.local_provider_observations())
        self.assertEqual(inspection["providers"]["gh-api"]["status"], "FAIL")
        self.assertEqual(
            inspection["providers"]["github-connector"]["status"], "UNKNOWN"
        )
        self.assertEqual(
            inspection["capabilities"]["github.repository.read"]["status"], "UNKNOWN"
        )


if __name__ == "__main__":
    unittest.main()
