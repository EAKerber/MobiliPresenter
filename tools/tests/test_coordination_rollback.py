import hashlib
import json
import subprocess
import unittest
from pathlib import Path

from tools import coordination_rollback_probe

ROOT = Path(__file__).resolve().parents[2]


class CoordinationRollbackTests(unittest.TestCase):
    def test_canonical_gitops_survives_coordination_removal(self):
        tracked = [ROOT / "AGENTS.md", ROOT / "ops" / "state" / "project.json"]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked}

        evidence = coordination_rollback_probe.canonical_without_coordination()

        after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked}
        self.assertTrue(evidence["ok"])
        self.assertTrue(evidence["doctor"]["ok"])
        self.assertTrue(evidence["verify"]["ok"])
        self.assertEqual(before, after)

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(status.returncode, 0)
        self.assertEqual(status.stdout.strip(), "")

    def test_cli_surface_decision_points_to_existing_dedicated_tool(self):
        decision_path = ROOT / "ops" / "evidence" / "git-ops-1.3-cli-surface-decision-2026-08-13.json"
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        self.assertEqual(decision["capability"], "coordination-leases")
        self.assertEqual(decision["officialExperimentalEntrypoint"], "tools/lock.py")
        self.assertFalse(decision["agentPyWrapperRequired"])
        self.assertTrue((ROOT / decision["officialExperimentalEntrypoint"]).is_file())


if __name__ == "__main__":
    unittest.main()
