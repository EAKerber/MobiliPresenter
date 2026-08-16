import unittest

from tools.semantics.actions import OperationalAction


class OperationalActionTests(unittest.TestCase):
    def test_vocabulary_is_exact(self):
        self.assertEqual(
            {item.value for item in OperationalAction},
            {"CONTINUE", "RECONCILE", "HANDOFF", "PAUSE", "NEEDS_HUMAN"},
        )

    def test_parse_rejects_unknown_value(self):
        with self.assertRaisesRegex(RuntimeError, "OPERATIONAL_ACTION_INVALID"):
            OperationalAction.parse("RETRY")


if __name__ == "__main__":
    unittest.main()
