from __future__ import annotations

import inspect
import unittest

from tools import hosted_agent_cycle_trace


class HostedAgentCycleWaitingSingleObservationTests(unittest.TestCase):
    def test_productive_stabilization_default_is_exactly_one_observation(self):
        self.assertEqual(hosted_agent_cycle_trace.TRACE_STABILIZATION_ATTEMPTS, 1)
        parameters = inspect.signature(
            hosted_agent_cycle_trace.prepare_close_stabilized
        ).parameters
        self.assertEqual(parameters["attempts"].default, 1)

    def test_explicit_characterization_can_still_request_multiple_observations(self):
        parameters = inspect.signature(
            hosted_agent_cycle_trace.prepare_close_stabilized
        ).parameters
        self.assertIn("attempts", parameters)
        self.assertIn("sleep", parameters)
        self.assertIn("delay_seconds", parameters)


if __name__ == "__main__":
    unittest.main()
