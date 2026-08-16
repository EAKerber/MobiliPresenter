import unittest

from tools.semantics.work import WorkStatus


class WorkStatusTests(unittest.TestCase):
    def test_vocabulary_is_stable(self):
        self.assertEqual(
            [item.value for item in WorkStatus],
            ["READY", "IN_PROGRESS", "WAITING", "HANDOFF", "DONE"],
        )
        self.assertTrue(WorkStatus.DONE.terminal)
        self.assertFalse(WorkStatus.READY.terminal)

    def test_unknown_status_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "WORK_STATUS_INVALID"):
            WorkStatus.parse("UNKNOWN")


if __name__ == "__main__":
    unittest.main()
