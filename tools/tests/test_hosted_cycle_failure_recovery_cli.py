from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CARRIER = ROOT / "tools" / "hosted_cycle_failure_recovery.py"


class HostedCycleFailureRecoveryCliTests(unittest.TestCase):
    def test_direct_script_bootstraps_repository_package(self):
        completed = subprocess.run(
            [sys.executable, str(CARRIER), "--help"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("parse-event", completed.stdout)
        self.assertIn("recover", completed.stdout)
        self.assertIn("publish", completed.stdout)


if __name__ == "__main__":
    unittest.main()
