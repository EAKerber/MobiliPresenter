from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from tools import hosted_agent_cycle_trace
from tools import hosted_agent_cycle_waiting


class HostedAgentCycleWaitingSingleObservationTests(unittest.TestCase):
    def test_policy_forces_bound_default_and_restores_both_surfaces(self):
        original_attempts = hosted_agent_cycle_trace.TRACE_STABILIZATION_ATTEMPTS
        original_prepare = hosted_agent_cycle_trace.prepare_close_stabilized
        probe = Mock(return_value=({}, {"traceStatus": "PASS"}))

        with patch.object(hosted_agent_cycle_trace, "prepare_close_stabilized", probe):
            patched_entry = hosted_agent_cycle_trace.prepare_close_stabilized
            with hosted_agent_cycle_waiting._single_observation_policy():
                self.assertEqual(hosted_agent_cycle_trace.TRACE_STABILIZATION_ATTEMPTS, 1)
                self.assertIsNot(hosted_agent_cycle_trace.prepare_close_stabilized, patched_entry)
                hosted_agent_cycle_trace.prepare_close_stabilized(
                    {}, {}, {}, {},
                    repository="EAKerber/MobiliPresenter",
                    attempts=99,
                    delay_seconds=99,
                )
            self.assertIs(hosted_agent_cycle_trace.prepare_close_stabilized, patched_entry)

        self.assertEqual(hosted_agent_cycle_trace.TRACE_STABILIZATION_ATTEMPTS, original_attempts)
        self.assertIs(hosted_agent_cycle_trace.prepare_close_stabilized, original_prepare)
        self.assertEqual(probe.call_count, 1)
        self.assertEqual(probe.call_args.kwargs["attempts"], 1)
        self.assertEqual(probe.call_args.kwargs["delay_seconds"], 0.0)


if __name__ == "__main__":
    unittest.main()
