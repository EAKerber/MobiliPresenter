import copy
import hashlib
import unittest

from tools import cold_archive_plan as cold


class ColdArchivePlan02Tests(unittest.TestCase):
    def entry(self, branch: str, sha: str, classification: str = "HISTORICAL_EVIDENCE"):
        return {
            "branch": branch,
            "headSha": sha,
            "classification": classification,
            "evidencePath": "ops/evidence/m6-k-knowledge-salvage-2026-08-18.json",
        }

    def test_initial_append_is_deterministic_independent_of_source_order(self):
        sources = [
            self.entry("tmp/fh06-user-artifacts", "b" * 40, "ARTIFACT_HISTORY"),
            self.entry("renderer/fixed-view-realistic-v1", "a" * 40, "DUPLICATE_HISTORY"),
        ]
        first = cold.build_plan(control_sha="f" * 40, sources=sources)
        second = cold.build_plan(control_sha="f" * 40, sources=list(reversed(sources)))
        self.assertEqual(first, second)
        self.assertEqual(first["schemaVersion"], "ColdArchivePlan 0.2")
        self.assertEqual(
            [item["branch"] for item in first["sources"]],
            ["renderer/fixed-view-realistic-v1", "tmp/fh06-user-artifacts"],
        )
        self.assertFalse(first["authorizesMutation"])

    def test_initial_anchor_uses_exact_source_heads_as_parents(self):
        plan = cold.build_plan(
            control_sha="f" * 40,
            sources=[
                self.entry("renderer/fixed-view-realistic-v1", "a" * 40),
                self.entry("tmp/fh06-user-artifacts", "b" * 40),
            ],
        )
        self.assertEqual(plan["parentShas"], ["a" * 40, "b" * 40])
        self.assertEqual(plan["readback"]["expectedParents"], plan["parentShas"])

    def test_append_preserves_existing_entries_and_only_adds_new_heads_as_parents(self):
        existing = [self.entry("work/old", "a" * 40)]
        plan = cold.build_plan(
            control_sha="f" * 40,
            previous_archive_head="c" * 40,
            existing_entries=existing,
            sources=[self.entry("work/new", "b" * 40)],
        )
        self.assertEqual(plan["parentShas"], ["c" * 40, "b" * 40])
        rendered = cold.render_index(plan)
        self.assertIn('"branch":"work/old"', rendered)
        self.assertIn('"branch":"work/new"', rendered)
        self.assertEqual(plan["readback"]["expectedEntryCount"], 2)

    def test_same_branch_different_heads_are_preserved(self):
        existing = [self.entry("work/reused", "a" * 40)]
        plan = cold.build_plan(
            control_sha="f" * 40,
            previous_archive_head="c" * 40,
            existing_entries=existing,
            sources=[self.entry("work/reused", "b" * 40)],
        )
        final = cold.merge_entries(plan["existingEntries"], plan["sources"])
        self.assertEqual(
            [(item["branch"], item["headSha"]) for item in final],
            [("work/reused", "a" * 40), ("work/reused", "b" * 40)],
        )

    def test_same_identity_same_metadata_is_idempotent_across_existing_and_source(self):
        item = self.entry("work/reused", "a" * 40)
        plan = cold.build_plan(
            control_sha="f" * 40,
            previous_archive_head="c" * 40,
            existing_entries=[item],
            sources=[item],
        )
        self.assertEqual(plan["readback"]["expectedEntryCount"], 1)
        self.assertEqual(plan["parentShas"], ["c" * 40, "a" * 40])

    def test_same_identity_conflicting_metadata_fails_closed(self):
        existing = [self.entry("work/reused", "a" * 40, "HISTORICAL_EVIDENCE")]
        changed = self.entry(
            "work/reused", "a" * 40, "CURRENT_KNOWLEDGE_ALREADY_PROMOTED"
        )
        with self.assertRaisesRegex(RuntimeError, "COLD_ARCHIVE_ENTRY_CONFLICT"):
            cold.build_plan(
                control_sha="f" * 40,
                previous_archive_head="c" * 40,
                existing_entries=existing,
                sources=[changed],
            )

    def test_duplicate_identity_inside_one_input_is_rejected(self):
        item = self.entry("work/reused", "a" * 40)
        with self.assertRaisesRegex(RuntimeError, "COLD_ARCHIVE_ENTRY_DUPLICATE"):
            cold.build_plan(
                control_sha="f" * 40,
                sources=[item, item],
            )

    def test_previous_archive_requires_existing_projection_on_append(self):
        with self.assertRaisesRegex(RuntimeError, "COLD_ARCHIVE_EXISTING_ENTRIES_REQUIRED"):
            cold.build_plan(
                control_sha="f" * 40,
                previous_archive_head="c" * 40,
                sources=[self.entry("work/new", "b" * 40)],
            )

    def test_initial_append_forbids_existing_entries(self):
        with self.assertRaisesRegex(
            RuntimeError, "COLD_ARCHIVE_INITIAL_EXISTING_ENTRIES_FORBIDDEN"
        ):
            cold.build_plan(
                control_sha="f" * 40,
                existing_entries=[self.entry("work/old", "a" * 40)],
                sources=[self.entry("work/new", "b" * 40)],
            )

    def test_reindex_is_linear_and_accepts_no_sources(self):
        existing = [
            self.entry("work/old-a", "a" * 40),
            self.entry("work/old-b", "b" * 40),
        ]
        plan = cold.build_plan(
            control_sha="f" * 40,
            previous_archive_head="c" * 40,
            existing_entries=existing,
            sources=[],
            operation="reindex",
        )
        self.assertEqual(plan["parentShas"], ["c" * 40])
        self.assertEqual(plan["readback"]["expectedEntryCount"], 2)

    def test_reindex_requires_previous_head_existing_entries_and_no_sources(self):
        existing = [self.entry("work/old", "a" * 40)]
        with self.assertRaisesRegex(RuntimeError, "COLD_ARCHIVE_REINDEX_PREVIOUS_HEAD_REQUIRED"):
            cold.build_plan(
                control_sha="f" * 40,
                existing_entries=existing,
                sources=[],
                operation="reindex",
            )
        with self.assertRaisesRegex(RuntimeError, "COLD_ARCHIVE_REINDEX_EXISTING_ENTRIES_REQUIRED"):
            cold.build_plan(
                control_sha="f" * 40,
                previous_archive_head="c" * 40,
                existing_entries=[],
                sources=[],
                operation="reindex",
            )
        with self.assertRaisesRegex(RuntimeError, "COLD_ARCHIVE_REINDEX_SOURCES_FORBIDDEN"):
            cold.build_plan(
                control_sha="f" * 40,
                previous_archive_head="c" * 40,
                existing_entries=existing,
                sources=[self.entry("work/new", "b" * 40)],
                operation="reindex",
            )

    def test_rendered_index_hash_is_bound_to_cumulative_projection(self):
        plan = cold.build_plan(
            control_sha="f" * 40,
            previous_archive_head="c" * 40,
            existing_entries=[self.entry("work/old", "a" * 40)],
            sources=[self.entry("work/new", "b" * 40)],
        )
        content = cold.render_index(plan)
        self.assertEqual(
            hashlib.sha256(content.encode("utf-8")).hexdigest(),
            plan["indexSha256"],
        )
        self.assertEqual(plan["existingEntriesHash"], cold.stable_hash(plan["existingEntries"]))

    def test_control_and_archive_branches_cannot_be_entries(self):
        for branch in ("main", "archive/cold"):
            with self.subTest(branch=branch):
                with self.assertRaisesRegex(RuntimeError, "COLD_ARCHIVE_ENTRY_FORBIDDEN"):
                    cold.build_plan(
                        control_sha="f" * 40,
                        sources=[self.entry(branch, "a" * 40)],
                    )

    def test_empty_initial_sources_and_invalid_sha_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, "COLD_ARCHIVE_SOURCES_REQUIRED"):
            cold.build_plan(control_sha="f" * 40, sources=[])
        with self.assertRaisesRegex(RuntimeError, "COLD_ARCHIVE_SOURCES_SHA_INVALID"):
            cold.build_plan(
                control_sha="f" * 40,
                sources=[self.entry("tmp/fh06-user-artifacts", "not-a-sha")],
            )

    def test_plan_tampering_existing_projection_is_rejected(self):
        plan = cold.build_plan(
            control_sha="f" * 40,
            previous_archive_head="c" * 40,
            existing_entries=[self.entry("work/old", "a" * 40)],
            sources=[self.entry("work/new", "b" * 40)],
        )
        tampered = copy.deepcopy(plan)
        tampered["existingEntries"][0]["classification"] = "ACTIVE"
        with self.assertRaisesRegex(RuntimeError, "COLD_ARCHIVE_PLAN_MISMATCH"):
            cold.validate_plan(tampered)

    def test_plan_hash_changes_with_existing_or_source_head(self):
        base = cold.build_plan(
            control_sha="f" * 40,
            previous_archive_head="c" * 40,
            existing_entries=[self.entry("work/old", "a" * 40)],
            sources=[self.entry("work/new", "b" * 40)],
        )
        existing_drift = cold.build_plan(
            control_sha="f" * 40,
            previous_archive_head="c" * 40,
            existing_entries=[self.entry("work/old", "d" * 40)],
            sources=[self.entry("work/new", "b" * 40)],
        )
        source_drift = cold.build_plan(
            control_sha="f" * 40,
            previous_archive_head="c" * 40,
            existing_entries=[self.entry("work/old", "a" * 40)],
            sources=[self.entry("work/new", "e" * 40)],
        )
        self.assertNotEqual(base["planHash"], existing_drift["planHash"])
        self.assertNotEqual(base["planHash"], source_drift["planHash"])


if __name__ == "__main__":
    unittest.main()
