import copy
import unittest

from tools import git_mutation_bundle as bundle
from tools.canonical import stable_hash

REPO = "EAKerber/MobiliPresenter"
BRANCH = "work/operations/git-mutation-bundle-0.1"
HEAD = "a" * 40
BASE_TREE = "b" * 40
CANDIDATE_TREE = "c" * 40
COMMIT = "d" * 40


def sample_changes():
    return [
        {"path": "tools/a.py", "content": "print('a')\n"},
        {"path": "docs/a.md", "content": "# A\n"},
    ]


def built(changes=None):
    return bundle.build_bundle(
        repository=REPO,
        branch=BRANCH,
        base_head=HEAD,
        base_tree_sha=BASE_TREE,
        changes=changes or sample_changes(),
        current_branch_head=HEAD,
    )


def tree_entries(value):
    return [{"path": path, "type": "blob", "sha": sha} for path, sha in value.items()]


class GitMutationBundleTests(unittest.TestCase):
    def test_build_is_deterministic_and_order_independent(self):
        first = built()
        second = built(list(reversed(sample_changes())))
        self.assertEqual(first, second)
        self.assertFalse(first["authorizesMutation"])
        self.assertFalse(first["force"])
        self.assertEqual(first["refPrecondition"], {"kind": "head", "sha": HEAD})
        self.assertEqual(bundle.validate_bundle(first), first)

    def test_empty_utf8_file_is_valid(self):
        value = built([{"path": "empty.txt", "content": ""}])
        self.assertEqual(value["entries"][0]["sizeBytes"], 0)
        bundle.verify_materialized_content(value, {"empty.txt": ""})

    def test_provider_profile_is_provider_name_agnostic(self):
        features = list(bundle.ATOMIC_PROFILE_REQUIRED_FEATURES)
        self.assertTrue(bundle.provider_satisfies_atomic_profile({"status": "PASS", "features": features}))
        self.assertTrue(bundle.provider_satisfies_atomic_profile({"status": "pass", "features": features + ["other"]}))
        self.assertFalse(bundle.provider_satisfies_atomic_profile({"status": "UNKNOWN", "features": features}))
        self.assertFalse(bundle.provider_satisfies_atomic_profile({"status": "PASS", "features": features[:-1]}))

    def test_swapped_content_fails_materialized_content_binding(self):
        value = built()
        content = {
            "tools/a.py": "# A\n",
            "docs/a.md": "print('a')\n",
        }
        with self.assertRaisesRegex(RuntimeError, "CONTENT_MISMATCH"):
            bundle.verify_materialized_content(value, content)

    def test_content_coverage_must_be_exact(self):
        value = built()
        with self.assertRaisesRegex(RuntimeError, "CONTENT_COVERAGE_MISMATCH"):
            bundle.verify_materialized_content(value, {"tools/a.py": "print('a')\n"})

    def test_duplicate_path_is_rejected(self):
        changes = [
            {"path": "x.txt", "content": "a"},
            {"path": "x.txt", "content": "b"},
        ]
        with self.assertRaisesRegex(RuntimeError, "DUPLICATE_PATH"):
            built(changes)

    def test_rehashed_semantic_drift_cannot_change_allowlist(self):
        value = built()
        value["expectedChangedPaths"] = ["elsewhere.txt"]
        core = {key: copy.deepcopy(item) for key, item in value.items() if key != "bundleHash"}
        value["bundleHash"] = stable_hash(core)
        with self.assertRaisesRegex(RuntimeError, "CHANGED_PATHS_MISMATCH"):
            bundle.validate_bundle(value)

    def test_force_and_authorization_claims_are_rejected_even_when_rehashed(self):
        for key, code in (("force", "FORCE_FORBIDDEN"), ("authorizesMutation", "MUST_NOT_AUTHORIZE")):
            value = built()
            value[key] = True
            core = {name: copy.deepcopy(item) for name, item in value.items() if name != "bundleHash"}
            value["bundleHash"] = stable_hash(core)
            with self.assertRaisesRegex(RuntimeError, code):
                bundle.validate_bundle(value)

    def test_tree_proof_catches_wrong_blob_and_extra_path(self):
        value = built()
        expected = {item["path"]: item["gitBlobSha"] for item in value["entries"]}
        base = {path: "e" * 40 for path in expected}
        proof = bundle.verify_tree(
            value,
            base_tree_entries=tree_entries(base),
            candidate_tree_entries=tree_entries(expected),
            candidate_tree_sha=CANDIDATE_TREE,
        )
        self.assertEqual(proof["status"], "PASS")

        wrong = dict(expected)
        wrong["tools/a.py"] = "f" * 40
        with self.assertRaisesRegex(RuntimeError, "TREE_BLOB_MISMATCH"):
            bundle.verify_tree(
                value,
                base_tree_entries=tree_entries(base),
                candidate_tree_entries=tree_entries(wrong),
                candidate_tree_sha=CANDIDATE_TREE,
            )

        extra_base = dict(base)
        extra_base["extra.txt"] = "1" * 40
        extra_candidate = dict(expected)
        extra_candidate["extra.txt"] = "2" * 40
        with self.assertRaisesRegex(RuntimeError, "TREE_CHANGED_PATHS_MISMATCH"):
            bundle.verify_tree(
                value,
                base_tree_entries=tree_entries(extra_base),
                candidate_tree_entries=tree_entries(extra_candidate),
                candidate_tree_sha=CANDIDATE_TREE,
            )

    def test_delete_is_explicit_and_tree_proven(self):
        value = built([{"path": "old.txt", "delete": True}])
        self.assertEqual(value["entries"][0]["operation"], "delete")
        proof = bundle.verify_tree(
            value,
            base_tree_entries=tree_entries({"old.txt": "e" * 40}),
            candidate_tree_entries=[],
            candidate_tree_sha=CANDIDATE_TREE,
        )
        self.assertEqual(proof["changedPaths"], ["old.txt"])

    def test_readback_binds_ref_parent_changed_paths_and_content_hashes(self):
        value = built()
        expected_hashes = {
            item["path"]: item["contentSha256"]
            for item in value["entries"]
            if item["operation"] == "write"
        }
        base = {item["path"]: "e" * 40 for item in value["entries"]}
        candidate = {item["path"]: item["gitBlobSha"] for item in value["entries"]}
        tree_proof = bundle.verify_tree(
            value,
            base_tree_entries=tree_entries(base),
            candidate_tree_entries=tree_entries(candidate),
            candidate_tree_sha=CANDIDATE_TREE,
        )
        receipt = {
            "branchHead": COMMIT,
            "commitSha": COMMIT,
            "parentSha": HEAD,
            "treeSha": CANDIDATE_TREE,
            "changedPaths": value["expectedChangedPaths"],
            "contentSha256": expected_hashes,
            "treeProof": tree_proof,
        }
        result = bundle.verify_readback(value, receipt)
        self.assertEqual(result["status"], "PASS")
        bad = dict(receipt)
        bad["parentSha"] = "e" * 40
        with self.assertRaisesRegex(RuntimeError, "READBACK_PARENT_MISMATCH"):
            bundle.verify_readback(value, bad)


if __name__ == "__main__":
    unittest.main()
