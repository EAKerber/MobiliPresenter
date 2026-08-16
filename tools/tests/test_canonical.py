import hashlib
import json
import unittest

from tools.canonical import canonical_json, stable_hash


class CanonicalTests(unittest.TestCase):
    def test_matches_existing_canonical_json_sha256_contract(self):
        value = {"z": [3, 2, 1], "a": "á", "nested": {"b": True, "a": None}}
        expected_json = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        expected_hash = hashlib.sha256(expected_json.encode("utf-8")).hexdigest()
        self.assertEqual(canonical_json(value), expected_json)
        self.assertEqual(stable_hash(value), expected_hash)


if __name__ == "__main__":
    unittest.main()
