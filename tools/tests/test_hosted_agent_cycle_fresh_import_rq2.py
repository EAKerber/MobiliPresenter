from __future__ import annotations

import subprocess
import sys
import unittest


class HostedAgentCycleFreshImportRQ2Tests(unittest.TestCase):
    def test_waiting_operational_guard_imports_in_fresh_process(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from tools import hosted_agent_cycle_waiting; "
                    "assert callable(hosted_agent_cycle_waiting.require_operational_result)"
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            0,
            completed.returncode,
            msg=f"stdout={completed.stdout}\nstderr={completed.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
