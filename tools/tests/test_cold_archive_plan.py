import copy
import hashlib
import unittest

from tools import cold_archive_plan as cold


class ColdArchivePlan01Tests(unittest.TestCase):
    def source(self, branch: str, sha: str, classification: str = "HISTORICAL"):
        return {
            "branch": branch,
            "headSha": sha,
            "classification": classification,
            "evidencePath": "ops/evidence/m6-k-knowledge-salvage-2026-08-18.json",
        }

    def test_plan_is_deterministic_independent_of_source_input_order(self):
        sources = [
            self.source("tmp/fh06-user-artifacts", "b" * 40, "ARTIFACT_HISTORY"),
            self.source("renderer/fixed-view-realistic-v1", "a" * 40, "DUPLICATE_HISTORY"),
        ]
        first = cold.build_plan(control_sha="f" * 40, sources=sources)
        second = cold.build_plan(control_sha="f" * 40, sources=list(reversed(sources)))
        self.assertEqual(first, second)
        self.assertEqual(
            [item["branch"] for item in first["sources"]],
            ["renderer/fixed-view-realistic-v1", "tmp/fh06-user-artifacts"],
        )
        self.assertFalse(first["authorizesMutation"])

    def test_initial_anchor_uses_exact_source_heads_as_parents(self):
        plan = cold.build_plan(
            control_sha="f" * 40,
            sources=[
                self.source("renderer/fixed-view-realistic-v1", "a" * 40),
                self.source("tmp/fh06-user-artifacts", "b" * 40),
            ],
        )
        self.assertEqual(plan["parentShas"], ["a" * 40, "b" * 40])
        self.assertEqual(plan["readback"]["expectedParents"], plan["parentShas"])

    def test_existing_archive_head_is_first_parent_and_is_not_duplicated(self):
        plan = cold.build_plan(
            control_sha="f" * 40,
            previous_archive_head="a" * 40,
            sources=[
                self.source("renderer/fixed-view-realistic-v1", "a" * 40),
                self.source("tmp/fh06-user-artifacts", "b" * 40),
            ],
        )
        self.assertEqual(plan["parentShas"], ["a" * 40, "b" * 40])

    def test_rendered_index_hash_is_bound_to_plan(self):
        plan = cold.build_plan(
            control_sha="f" * 40,
            sources=[self.source("tmp/fh06-user-artifacts", "b" * 40)],
        )
        content = cold.render_index(plan)
        self.assertEqual(
            hashlib.sha256(content.encode("utf-8")).hexdigest(),
            plan["indexSha256"],
        )

    def test_control_and_archive_branches_cannot_be_sources(self):
        for branch in ("main", "archive/cold"):
            with self.subTest(branch=branch):
                with self.assertRaisesRegex(RuntimeError, "COLD_ARCHIVE_SOURCE_FORBIDDEN"):
                    cold.build_plan(
                        control_sha="f" * 40,
                        sources=[self.source(branch, "a" * 40)],
                    )

    def test_duplicate_source_branch_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "COLD_ARCHIVE_SOURCE_DUPLICATE"):
            cold.build_plan(
                control_sha="f" * 40,
                sources=[
                    self.source("tmp/fh06-user-artifacts", "a" * 40),
                    self.source("tmp/fh06-user-artifacts", "b" * 40),
                ],
            )

    def test_empty_sources_and_invalid_sha_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, "COLD_ARCHIVE_SOURCES_REQUIRED"):
            cold.build_plan(control_sha="f" * 40, sources=[])
        with self.assertRaisesRegex(RuntimeError, "COLD_ARCHIVE_SOURCE_SHA_INVALID"):
            cold.build_plan(
                control_sha="f" * 40,
                sources=[self.source("tmp/fh06-user-artifacts", "not-a-sha")],
            )

    def test_plan_tampering_is_rejected(self):
        plan = cold.build_plan(
            control_sha="f" * 40,
            sources=[self.source("tmp/fh06-user-artifacts", "b" * 40)],
        )
        tampered = copy.deepcopy(plan)
        tampered["sources"][0]["classification"] = "ACTIVE"
        with self.assertRaisesRegex(RuntimeError, "COLD_ARCHIVE_PLAN_MISMATCH"):
            cold.validate_plan(tampered)

    def test_plan_hash_changes_with_control_or_source_head(self):
        base = cold.build_plan(
            control_sha="f" * 40,
            sources=[self.source("tmp/fh06-user-artifacts", "a" * 40)],
        )
        control_drift = cold.build_plan(
            control_sha="e" * 40,
            sources=[self.source("tmp/fh06-user-artifacts", "a" * 40)],
        )
        source_drift = cold.build_plan(
            control_sha="f" * 40,
            sources=[self.source("tmp/fh06-user-artifacts", "b" * 40)],
        )
        self.assertNotEqual(base["planHash"], control_drift["planHash"])
        self.assertNotEqual(base["planHash"], source_drift["planHash"])


if __name__ == "__main__":
    unittest.main()
