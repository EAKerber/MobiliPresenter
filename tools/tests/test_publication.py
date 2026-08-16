import copy
import unittest

from tools import project_state, publication


class PublicationContractTests(unittest.TestCase):
    def test_live_manifest_is_valid_and_derives_current_duplicates(self):
        state = project_state.load_state()
        view = project_state.operational_view(state)
        manifest = publication.load_manifest(view["published"]["artifactManifest"])
        self.assertEqual(publication.validate_manifest(manifest), [])
        derived = publication.publication_view(view, manifest)
        self.assertEqual(derived["release"], state["published"]["release"])
        self.assertEqual(derived["sourceBranch"], state["git"]["publishedBranch"])
        self.assertEqual(derived["sourceBuildFingerprint"], state["published"]["artifactSha256"])
        self.assertEqual(derived["fingerprintKind"], publication.FINGERPRINT_KIND)

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
