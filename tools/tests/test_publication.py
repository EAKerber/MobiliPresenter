import copy
import unittest

from tools import project_state, publication


class PublicationContractTests(unittest.TestCase):
    def test_live_manifest_is_valid_and_derives_current_publication(self):
        state = project_state.load_state()
        view = project_state.operational_view(state)
        manifest = publication.load_manifest(view["published"]["artifactManifest"])
        self.assertEqual(publication.validate_manifest(manifest), [])
        derived = publication.publication_view(view, manifest)
        self.assertEqual(derived["release"], manifest["release"])
        self.assertEqual(derived["sourceBranch"], manifest["sourceBranch"])
        self.assertEqual(derived["sourceBuildFingerprint"], manifest["sha256"])
        self.assertEqual(derived["fingerprintKind"], publication.FINGERPRINT_KIND)
        self.assertNotIn("release", state["published"])
        self.assertNotIn("artifactSha256", state["published"])
        self.assertNotIn("publishedBranch", state["git"])

    def test_live_fingerprint_is_reproducible(self):
        state = project_state.load_state()
        view = project_state.operational_view(state)
        manifest = publication.load_manifest(view["published"]["artifactManifest"])
        self.assertEqual(publication.compute_fingerprint(manifest), manifest["sha256"])
        self.assertEqual(
            publication.fingerprint_payload(manifest)["schemaVersion"],
            publication.FINGERPRINT_PAYLOAD_VERSION,
        )

    def test_fingerprint_tampering_fails_closed(self):
        state = project_state.load_state()
        view = project_state.operational_view(state)
        manifest = publication.load_manifest(view["published"]["artifactManifest"])
        mutations = (
            ("sourceBase", "0" * 40),
            ("sourcePaths", [*manifest["sourcePaths"], "extra-source"]),
            ("buildCommand", manifest["buildCommand"] + " --changed"),
            ("publishPath", manifest["publishPath"] + "-changed"),
        )
        for field, replacement in mutations:
            with self.subTest(field=field):
                broken = copy.deepcopy(manifest)
                broken[field] = replacement
                errors = publication.validate_manifest(broken)
                self.assertTrue(
                    any(item["code"] == "SOURCE_BUILD_FINGERPRINT_MISMATCH" for item in errors),
                    errors,
                )

    def test_invalid_fingerprint_fails_closed(self):
        state = project_state.load_state()
        view = project_state.operational_view(state)
        manifest = publication.load_manifest(view["published"]["artifactManifest"])
        broken = copy.deepcopy(manifest)
        broken["sha256"] = "bad"
        errors = publication.validate_manifest(broken)
        self.assertTrue(any(item["code"] == "SOURCE_BUILD_FINGERPRINT_INVALID" for item in errors))

    def test_invalid_fingerprint_kind_fails_closed(self):
        state = project_state.load_state()
        view = project_state.operational_view(state)
        manifest = publication.load_manifest(view["published"]["artifactManifest"])
        broken = copy.deepcopy(manifest)
        broken["fingerprintKind"] = "sha256(bytes)"
        errors = publication.validate_manifest(broken)
        self.assertTrue(any(item["code"] == "SOURCE_BUILD_FINGERPRINT_KIND_INVALID" for item in errors))


if __name__ == "__main__":
    unittest.main()
