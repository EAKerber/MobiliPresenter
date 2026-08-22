from __future__ import annotations

import copy
import unittest

from tools.semantics import maxims


class EcosystemMaximTests(unittest.TestCase):
    def test_initial_catalog_is_valid_bounded_and_non_authoritative(self):
        catalog = maxims.load_catalog()
        self.assertEqual([], maxims.validate_catalog(catalog))
        self.assertEqual(
            {
                "birth-requires-death-condition",
                "creation-requires-justification",
                "discovery-does-not-authorize",
                "negative-knowledge-is-knowledge",
                "persistence-requires-justification",
                "proposal-does-not-authorize",
                "readback-proves-change",
                "residue-needs-owner-and-destination",
            },
            set(catalog["items"]),
        )
        self.assertTrue(catalog["readOnly"])
        self.assertFalse(catalog["semanticAuthority"])
        self.assertFalse(catalog["authorizesMutation"])
        self.assertFalse(catalog["overridesContract"])
        for item in catalog["items"].values():
            self.assertFalse(item["semanticAuthority"])
            self.assertFalse(item["authorizesMutation"])
            self.assertFalse(item["overridesContract"])
            self.assertTrue(item["deathCondition"])

    def test_maxim_cannot_claim_authority_even_when_catalog_is_read_only(self):
        catalog = copy.deepcopy(maxims.load_catalog())
        catalog["items"]["proposal-does-not-authorize"]["authorizesMutation"] = True
        self.assertIn(
            "ECOSYSTEM_MAXIM_AUTHORIZESMUTATION_INVALID:proposal-does-not-authorize",
            maxims.validate_catalog(catalog),
        )

    def test_related_contract_must_exist(self):
        catalog = copy.deepcopy(maxims.load_catalog())
        catalog["items"]["creation-requires-justification"][
            "relatedContracts"
        ].append("unknown-contract")
        catalog["items"]["creation-requires-justification"][
            "relatedContracts"
        ].sort()
        self.assertIn(
            "ECOSYSTEM_MAXIM_CONTRACT_UNKNOWN:creation-requires-justification:unknown-contract",
            maxims.validate_catalog(catalog),
        )


if __name__ == "__main__":
    unittest.main()
