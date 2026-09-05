from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class AgentImportR1BTests(unittest.TestCase):
    def test_clean_process_import_does_not_reenter_partial_hosted_cycle_graph(self):
        proc = subprocess.run(
            [sys.executable, "-c", "import tools.agent"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, proc.returncode, proc.stderr or proc.stdout)


if __name__ == "__main__":
    unittest.main()
