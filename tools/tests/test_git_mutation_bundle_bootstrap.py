import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLE_DIR = ROOT / "docs" / "kickstarts" / "roles"


class GitMutationBundleBootstrapTests(unittest.TestCase):
    def test_current_manager_bootstrap_exposes_atomic_multi_path_contract(self):
        current = (ROLE_DIR / "manager-gitops-current.md").read_text(encoding="utf-8")
        match = re.search(r"\]\(\./(manager-gitops-v[^)]+\.md)\)", current)
        self.assertIsNotNone(match)
        versioned_path = ROLE_DIR / match.group(1)
        self.assertTrue(versioned_path.is_file())
        versioned = versioned_path.read_text(encoding="utf-8")
        self.assertTrue((ROOT / "tools" / "git_mutation_bundle.py").is_file())
        for required in (
            "GitMutationBundle 0.1",
            "git.direct-mutation",
            "verify-tree",
            "verify-readback",
            "force=false",
            "não faça fallback silencioso para Contents API sequencial",
        ):
            self.assertIn(required, versioned)


if __name__ == "__main__":
    unittest.main()
