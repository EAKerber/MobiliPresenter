import unittest

from tools.agent_tools import journey_shadow


def _status(next_action, *, blockers=None, reentry=None):
    return {
        "journeyProjection": {
            "schemaVersion": "JourneyProjection 0.1",
            "nextSafeAction": next_action,
            "blockers": list(blockers or []),
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
        },
        **({"reentry": reentry} if reentry is not None else {}),
    }


def _manual(
    action,
    *,
    target_cycle_instance_id=None,
    guard_contract,
):
    return {
        "action": action,
        "targetCycleInstanceId": target_cycle_instance_id,
        "guardContract": guard_contract,
        "authorityWriter": None,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


class JourneyShadowEquivalenceTests(unittest.TestCase):
    def test_entry_projects_begin_without_executing(self):
        projected = journey_shadow.project(_status("BEGIN_AGENT_CYCLE"))
        self.assertEqual(projected["projectedAction"], _manual(
            "BEGIN_AGENT_CYCLE",
            guard_contract="tools.hosted_agent_cycle",
        ))
        self.assertFalse(projected["executesProjectedAction"])
        self.assertTrue(projected["readOnly"])
        self.assertFalse(projected["semanticAuthority"])
        self.assertFalse(projected["authorizesMutation"])

    def test_begin_new_cycle_normalizes_to_public_entry_action(self):
        projected = journey_shadow.project(_status("BEGIN_NEW_CYCLE"))
        comparison = journey_shadow.compare(
            projected,
            _manual(
                "BEGIN_AGENT_CYCLE",
                guard_contract="tools.hosted_agent_cycle",
            ),
        )
        self.assertEqual(comparison["status"], "EQUIVALENT")
        self.assertEqual(comparison["differences"], [])
        self.assertFalse(comparison["projectedActionExecuted"])

    def test_resume_exact_cycle_preserves_observed_cycle_identity(self):
        target = "cycle-instance-shadow-123"
        projected = journey_shadow.project(_status(
            "RESUME_EXACT_CYCLE",
            reentry={
                "targetCycle": {
                    "cycleInstanceId": target,
                    "handle": {"opaque": "not-consumed-by-shadow"},
                }
            },
        ))
        comparison = journey_shadow.compare(
            projected,
            _manual(
                "RESUME_EXACT_CYCLE",
                target_cycle_instance_id=target,
                guard_contract="tools.hosted_cycle_reentry",
            ),
        )
        self.assertEqual(comparison["status"], "EQUIVALENT")
        self.assertEqual(
            projected["projectedAction"]["targetCycleInstanceId"],
            target,
        )

    def test_guard_or_writer_boundary_divergence_fails_closed(self):
        projected = journey_shadow.project(_status("BEGIN_AGENT_CYCLE"))
        observed = _manual(
            "BEGIN_AGENT_CYCLE",
            guard_contract="tools.hosted_cycle_reentry",
        )
        comparison = journey_shadow.compare(projected, observed)
        metrics = journey_shadow.summarize([comparison])
        self.assertEqual(comparison["status"], "DIVERGED")
        self.assertEqual(comparison["differences"], ["guardContract"])
        self.assertEqual(metrics["gateDisposition"], "BLOCKED")

    def test_unknown_reentry_remains_not_comparable_and_never_projects_action(self):
        projected = journey_shadow.project(_status(
            "OBSERVE",
            blockers=["AGENT_REENTRY_PROVIDER_UNAVAILABLE"],
        ))
        comparison = journey_shadow.compare(projected, None)
        metrics = journey_shadow.summarize([comparison])
        self.assertIsNone(projected["projectedAction"])
        self.assertIn("JOURNEY_BLOCKED", projected["reasonCodes"])
        self.assertIn(
            "AGENT_REENTRY_PROVIDER_UNAVAILABLE",
            projected["reasonCodes"],
        )
        self.assertEqual(comparison["status"], "NOT_COMPARABLE")
        self.assertEqual(metrics["gateDisposition"], "UNKNOWN")
        self.assertEqual(metrics["projectedActionsExecuted"], 0)

    def test_equivalent_canaries_report_pass_without_hiding_uncomparable_cases(self):
        entry = journey_shadow.compare(
            journey_shadow.project(_status("BEGIN_AGENT_CYCLE")),
            _manual(
                "BEGIN_AGENT_CYCLE",
                guard_contract="tools.hosted_agent_cycle",
            ),
        )
        resume_status = _status(
            "RESUME_EXACT_CYCLE",
            reentry={"targetCycle": {"cycleInstanceId": "cycle-instance-a"}},
        )
        resume = journey_shadow.compare(
            journey_shadow.project(resume_status),
            _manual(
                "RESUME_EXACT_CYCLE",
                target_cycle_instance_id="cycle-instance-a",
                guard_contract="tools.hosted_cycle_reentry",
            ),
        )
        out_of_scope = journey_shadow.compare(
            journey_shadow.project(_status("WAIT")),
            None,
        )
        metrics = journey_shadow.summarize([entry, resume, out_of_scope])
        self.assertEqual(metrics["gateDisposition"], "PASS")
        self.assertEqual(metrics["equivalent"], 2)
        self.assertEqual(metrics["diverged"], 0)
        self.assertEqual(metrics["notComparable"], 1)
        self.assertEqual(metrics["equivalenceRate"], 1.0)
        self.assertEqual(metrics["projectedActionsExecuted"], 0)


if __name__ == "__main__":
    unittest.main()
