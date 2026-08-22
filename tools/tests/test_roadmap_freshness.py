from __future__ import annotations

import copy
import hashlib
import unittest

from tools import project_state, roadmap_freshness
from tools.canonical import stable_hash


class RoadmapFreshnessTests(unittest.TestCase):
    def state(self, checkpoint="BEFORE", next_transition="next-before"):
        return {
            "schemaVersion": "ProjectState 2.1",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
            "git": {"controlBranch": "main", "protectedBranches": []},
            "published": {"url": "https://example.invalid/", "artifactManifest": "ops/published/viewer-next-current.json"},
            "development": {
                "initiative": "Test",
                "phase": "between-increments",
                "checkpoint": checkpoint,
                "nextTransition": next_transition,
            },
        }

    def coverage(self, base, head, before, after, disposition="UPDATED"):
        return {
            "schemaVersion": "RoadmapFreshnessCoverage 0.1",
            "projectState": {
                "baseHash": stable_hash(base),
                "currentHash": stable_hash(head),
                "changedFields": ["development.checkpoint", "development.nextTransition"],
            },
            "consumers": [{
                "path": "docs/consumer.md",
                "disposition": disposition,
                "contentHash": hashlib.sha256(after).hexdigest(),
            }],
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }

    def inspect(self, coverage=None, before=b"before", after=b"after"):
        base = self.state()
        head = self.state("AFTER", "next-after")
        value = coverage or self.coverage(base, head, before, after)
        return roadmap_freshness.inspect_transition(
            base,
            head,
            {"docs/consumer.md": before},
            {"docs/consumer.md": after},
            value,
            ["docs/consumer.md"],
        )

    def test_live_coverage_is_valid(self):
        self.assertEqual([], roadmap_freshness.validate_coverage())

    def test_complete_transition_coverage_passes(self):
        inspection = self.inspect()
        self.assertEqual("PASS", inspection["status"])
        self.assertEqual("COVERAGE_COMPLETE", inspection["code"])
        self.assertFalse(inspection["authorizesMutation"])

    def test_silent_consumer_omission_fails(self):
        base = self.state()
        head = self.state("AFTER", "next-after")
        coverage = self.coverage(base, head, b"before", b"after")
        coverage["consumers"] = []
        inspection = self.inspect(coverage)
        self.assertEqual("FAIL", inspection["status"])
        self.assertIn("ROADMAP_FRESHNESS_CONSUMERS_INVALID", inspection["errors"])

    def test_unchanged_consumer_requires_explicit_no_change(self):
        base = self.state()
        head = self.state("AFTER", "next-after")
        coverage = self.coverage(base, head, b"same", b"same", disposition="UPDATED")
        inspection = self.inspect(coverage, before=b"same", after=b"same")
        self.assertIn("ROADMAP_FRESHNESS_DISPOSITION_MISMATCH", inspection["errors"])
        coverage["consumers"][0]["disposition"] = "NO_CHANGE"
        self.assertEqual("PASS", self.inspect(coverage, before=b"same", after=b"same")["status"])

    def test_state_hash_drift_fails(self):
        base = self.state()
        head = self.state("AFTER", "next-after")
        coverage = self.coverage(base, head, b"before", b"after")
        coverage["projectState"]["currentHash"] = "0" * 64
        self.assertIn("ROADMAP_FRESHNESS_CURRENT_STATE_HASH_MISMATCH", self.inspect(coverage)["errors"])

    def test_false_authority_claims_are_rejected(self):
        base = self.state()
        head = self.state("AFTER", "next-after")
        coverage = self.coverage(base, head, b"before", b"after")
        coverage["authorizesMutation"] = True
        self.assertIn("ROADMAP_FRESHNESS_MUTATION_AUTHORITY_FORBIDDEN", self.inspect(coverage)["errors"])

    def test_no_transition_is_healthy_noop(self):
        state = self.state()
        coverage = self.coverage(state, state, b"same", b"same", disposition="NO_CHANGE")
        coverage["projectState"]["changedFields"] = []
        inspection = roadmap_freshness.inspect_transition(
            state,
            copy.deepcopy(state),
            {},
            {},
            coverage,
            [],
        )
        self.assertEqual("PASS", inspection["status"])
        self.assertEqual("NO_TRANSITION", inspection["code"])


if __name__ == "__main__":
    unittest.main()
