import copy
import unittest

from tools import git_mutation_plan as plan


SHA_A = "a" * 40
SHA_B = "b" * 40
BLOB = "c" * 40
DIGEST = "d" * 64
BODY = "e" * 64
CONTROL = "main"
BRANCH = "work/operations/example"


class GitMutationPlanTests(unittest.TestCase):
    def test_create_branch_is_deterministic_read_only_intent(self):
        first = plan.create_branch(branch=BRANCH, base_sha=SHA_A, control_branch=CONTROL)
        second = plan.create_branch(branch=BRANCH, base_sha=SHA_A, control_branch=CONTROL)
        self.assertEqual(first, second)
        self.assertEqual(first["connectorAction"], "create_branch")
        self.assertEqual(first["preconditions"], {"branchMustBeAbsent": True, "baseSha": SHA_A})
        self.assertEqual(first["readback"]["expectedSha"], SHA_A)
        self.assertFalse(first["authorizesMutation"])
        self.assertEqual(plan.validate(first), first)

    def test_content_writes_bind_branch_head_and_file_state(self):
        created = plan.create_file(branch=BRANCH, path="tools/new.py", branch_head=SHA_A, content_sha256=DIGEST, control_branch=CONTROL)
        updated = plan.update_file(branch=BRANCH, path="tools/existing.py", branch_head=SHA_A, blob_sha=BLOB, content_sha256=DIGEST, control_branch=CONTROL)
        deleted = plan.delete_file(branch=BRANCH, path="tools/old.py", branch_head=SHA_A, blob_sha=BLOB, control_branch=CONTROL)
        self.assertEqual(created["preconditions"]["branchHead"], SHA_A)
        self.assertTrue(created["preconditions"]["pathMustBeAbsent"])
        self.assertEqual(updated["preconditions"], {"branchHead": SHA_A, "blobSha": BLOB})
        self.assertEqual(deleted["preconditions"], {"branchHead": SHA_A, "blobSha": BLOB})
        self.assertEqual(updated["readback"]["expectedParentHead"], SHA_A)
        self.assertEqual(deleted["readback"]["expectedParentHead"], SHA_A)

    def test_direct_control_branch_content_and_ref_writes_are_forbidden(self):
        with self.assertRaisesRegex(RuntimeError, "GIT_MUTATION_DIRECT_CONTROL_BRANCH_FORBIDDEN"):
            plan.create_file(branch=CONTROL, path="dummy", branch_head=SHA_A, content_sha256=DIGEST, control_branch=CONTROL)
        with self.assertRaisesRegex(RuntimeError, "GIT_MUTATION_DIRECT_CONTROL_BRANCH_FORBIDDEN"):
            plan.update_ref(branch=CONTROL, current_sha=SHA_A, new_sha=SHA_B, control_branch=CONTROL)

    def test_update_ref_requires_observed_current_sha_and_rejects_force(self):
        value = plan.update_ref(branch=BRANCH, current_sha=SHA_A, new_sha=SHA_B, control_branch=CONTROL)
        self.assertEqual(value["preconditions"]["currentSha"], SHA_A)
        self.assertEqual(value["mutation"], {"newSha": SHA_B, "force": False})
        with self.assertRaisesRegex(RuntimeError, "GIT_MUTATION_FORCE_FORBIDDEN"):
            plan.update_ref(branch=BRANCH, current_sha=SHA_A, new_sha=SHA_B, control_branch=CONTROL, force=True)

    def test_pr_creation_and_merge_bind_observed_head(self):
        created = plan.create_pr(head=BRANCH, base=CONTROL, head_sha=SHA_A, title="G0.1", body_sha256=BODY, control_branch=CONTROL)
        merged = plan.merge_pr(pr_number=95, head_sha=SHA_A, merge_method="squash")
        self.assertTrue(created["preconditions"]["openPrForHeadMustBeAbsent"])
        self.assertEqual(created["preconditions"]["headSha"], SHA_A)
        self.assertEqual(merged["connectorAction"], "merge_pull_request")
        self.assertEqual(merged["preconditions"]["expectedHeadSha"], SHA_A)
        self.assertTrue(merged["preconditions"]["requiredGatesMustBeGreen"])

    def test_plan_hash_detects_semantic_tampering(self):
        value = plan.create_branch(branch=BRANCH, base_sha=SHA_A, control_branch=CONTROL)
        tampered = copy.deepcopy(value)
        tampered["target"]["branch"] = "work/operations/other"
        with self.assertRaisesRegex(RuntimeError, "GIT_MUTATION_PLAN_HASH_MISMATCH"):
            plan.validate(tampered)

    def test_plan_cannot_claim_authorization(self):
        value = plan.create_branch(branch=BRANCH, base_sha=SHA_A, control_branch=CONTROL)
        value["authorizesMutation"] = True
        core = {key: copy.deepcopy(item) for key, item in value.items() if key != "planHash"}
        from tools.canonical import stable_hash
        value["planHash"] = stable_hash(core)
        with self.assertRaisesRegex(RuntimeError, "GIT_MUTATION_PLAN_MUST_NOT_AUTHORIZE"):
            plan.validate(value)


if __name__ == "__main__":
    unittest.main()
