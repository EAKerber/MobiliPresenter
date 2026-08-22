from __future__ import annotations

import copy
import unittest

from tools.semantics import foundations


class SemanticFoundationsTests(unittest.TestCase):
    def setUp(self):
        self.value = foundations.load_foundations()

    def test_live_contract_is_valid(self):
        self.assertEqual([], foundations.validate_foundations(self.value))

    def test_dictionary_closes_required_terms(self):
        self.assertEqual(
            foundations.DICTIONARY_TERMS,
            set(self.value["technicalDictionary"]),
        )

    def test_every_field_has_exactly_one_determinism_class(self):
        for contract in self.value["artifactContracts"].values():
            classified = [
                field
                for fields in contract["fieldClassifications"].values()
                for field in fields
            ]
            self.assertEqual(set(contract["fieldInventory"]), set(classified))
            self.assertEqual(len(classified), len(set(classified)))

    def test_semantic_authority_claim_is_rejected(self):
        broken = copy.deepcopy(self.value)
        broken["artifactContracts"]["agent-semantic-brief"]["invariants"]["semanticAuthority"] = True
        self.assertIn(
            "SEMANTIC_FOUNDATIONS_SEMANTIC_AUTHORITY_FORBIDDEN",
            foundations.validate_foundations(broken),
        )

    def test_mutation_authority_claim_is_rejected(self):
        broken = copy.deepcopy(self.value)
        broken["artifactContracts"]["agent-semantic-brief"]["invariants"]["authorizesMutation"] = True
        self.assertIn(
            "SEMANTIC_FOUNDATIONS_MUTATION_AUTHORITY_FORBIDDEN",
            foundations.validate_foundations(broken),
        )

    def test_maxim_cannot_override_contract(self):
        broken = copy.deepcopy(self.value)
        broken["artifactContracts"]["ecosystem-maxim"]["invariants"]["overridesContract"] = True
        self.assertIn(
            "SEMANTIC_FOUNDATIONS_MAXIM_OVERRIDE_FORBIDDEN",
            foundations.validate_foundations(broken),
        )

    def test_brief_maxim_selection_remains_bounded(self):
        broken = copy.deepcopy(self.value)
        broken["artifactContracts"]["agent-semantic-brief"]["invariants"]["maximsMaximum"] = 4
        self.assertIn(
            "SEMANTIC_FOUNDATIONS_MAXIM_SELECTION_LIMIT_INVALID",
            foundations.validate_foundations(broken),
        )

    def test_required_capability_bucket_cannot_disappear(self):
        broken = copy.deepcopy(self.value)
        broken["artifactContracts"]["capability-relevance-projection"]["invariants"]["requiredBuckets"].remove("requiredUnavailable")
        self.assertIn(
            "SEMANTIC_FOUNDATIONS_CAPABILITY_BUCKETS_INVALID",
            foundations.validate_foundations(broken),
        )

    def test_heuristic_cannot_change_authorization_facts(self):
        broken = copy.deepcopy(self.value)
        broken["determinismPolicy"]["heuristicMustNotInfluence"].remove("authority")
        self.assertIn(
            "SEMANTIC_FOUNDATIONS_HEURISTIC_BOUNDARY_INVALID",
            foundations.validate_foundations(broken),
        )


if __name__ == "__main__":
    unittest.main()
