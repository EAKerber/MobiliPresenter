import unittest
from unittest.mock import patch

from tools import agent


class AgentPruneFacadeTests(unittest.TestCase):
    def test_agent_prune_delegates_to_canonical_generator(self):
        with patch.object(agent.git_prune_plan, "command_generate", return_value=17) as generate:
            self.assertEqual(17, agent.command_git_prune_plan(True))
        generate.assert_called_once_with(True)

    def test_removed_generic_prune_command_is_not_required(self):
        self.assertFalse(hasattr(agent.git_prune_plan, "command"))


if __name__ == "__main__":
    unittest.main()
