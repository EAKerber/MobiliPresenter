from __future__ import annotations

import copy
import unittest

from tools import project_ci_observation, project_coherence, project_sensors
from tools.canonical import stable_hash


def pr(number=7, *, ci="green", observed=True):
    return {
        "number": number,
        "draft": False,
        "headRef": "work/operations/ci-observation-test",
        "headSha": f"{number % 10}" * 40,
        "baseRef": "main",
        "ci": ci,
        "ciObserved": observed,
        "workflows": [],
    }


def pr_sensor(items=None, *, available=True):
    return project_sensors.sensor(
        "PASS" if available else "UNKNOWN",
        code=None if available else "REMOTE_PR_INVENTORY_UNAVAILABLE",
        data={"available": available, "items": items or []},
        authority={"kind": "github", "resource": "pull-requests"},
    )


def project():
    return {
        "controlBranch": "main",
        "protectedBranches": [],
        "phase": "between-increments",
        "checkpoint": "C",
        "nextTransition": "next",
    }


def coherence_sensors(items):
    return {
        "pullRequests": pr_sensor(items),
        "coordination": project_sensors.sensor(
            "PASS",
            data={"available": True, "leases": [], "intents": []},
            authority={"kind": "git-authority", "branch": "coordination/leases"},
        ),
        "continuations": project_sensors.sensor(
            "PASS",
            data={"available": True, "items": []},
            authority={"kind": "git-authority", "branch": "coordination/continuations"},
        ),
    }


def coherence_check(result):
    return next(
        item for item in result["checks"]
        if item["id"] == "pull-requests.ci-observation"
    )


class ProjectCIObservationS2Tests(unittest.TestCase):
    def test_no_open_prs_is_not_applicable(self):
        result = project_ci_observation.build(pr_sensor([]))
        self.assertEqual("NOT_APPLICABLE", result["state"])
        self.assertEqual(["NO_OPEN_PRS"], result["reasonCodes"])
        self.assertEqual([], result["items"])

    def test_green_ci_is_explicit(self):
        result = project_ci_observation.build(pr_sensor([pr(ci="green")]))
        self.assertEqual("GREEN", result["state"])
        self.assertEqual("GREEN", result["items"][0]["state"])
        self.assertEqual("PR_CI_GREEN", result["items"][0]["reasonCode"])

    def test_pending_is_known_nonterminal_not_failure(self):
        result = project_ci_observation.build(pr_sensor([pr(ci="pending")]))
        self.assertEqual("PENDING", result["state"])
        self.assertEqual(["PR_CI_PENDING"], result["reasonCodes"])

    def test_observed_failure_is_distinct_from_unknown(self):
        result = project_ci_observation.build(pr_sensor([pr(ci="failed")]))
        self.assertEqual("FAILED", result["state"])
        self.assertEqual(["PR_CI_FAILED"], result["reasonCodes"])

    def test_unobserved_ci_is_unknown_even_if_payload_claims_green(self):
        result = project_ci_observation.build(
            pr_sensor([pr(ci="green", observed=False)])
        )
        self.assertEqual("UNKNOWN", result["state"])
        self.assertEqual(
            "PR_CI_OBSERVATION_UNAVAILABLE",
            result["items"][0]["reasonCode"],
        )

    def test_observed_but_unclassifiable_ci_has_separate_reason(self):
        result = project_ci_observation.build(pr_sensor([pr(ci="unknown")]))
        self.assertEqual("UNKNOWN", result["state"])
        self.assertEqual("PR_CI_STATE_UNKNOWN", result["items"][0]["reasonCode"])

    def test_failed_dominates_mixed_summary_without_erasing_other_evidence(self):
        result = project_ci_observation.build(
            pr_sensor([pr(7, ci="pending"), pr(8, ci="failed")])
        )
        self.assertEqual("FAILED", result["state"])
        self.assertEqual(
            ["PR_CI_FAILED", "PR_CI_PENDING"], result["reasonCodes"]
        )
        self.assertEqual([7, 8], [item["number"] for item in result["items"]])

    def test_inventory_unavailable_is_unknown_without_inventing_prs(self):
        result = project_ci_observation.build(pr_sensor(available=False))
        self.assertEqual("UNKNOWN", result["state"])
        self.assertEqual(["PR_INVENTORY_UNAVAILABLE"], result["reasonCodes"])
        self.assertEqual([], result["items"])

    def test_rehash_cannot_legitimize_false_item_semantics(self):
        result = project_ci_observation.build(pr_sensor([pr(ci="pending")]))
        tampered = copy.deepcopy(result)
        tampered["items"][0]["state"] = "GREEN"
        core = {
            key: copy.deepcopy(value)
            for key, value in tampered.items()
            if key != "observationHash"
        }
        tampered["observationHash"] = stable_hash(core)
        with self.assertRaisesRegex(RuntimeError, "ITEM_MISMATCH"):
            project_ci_observation.validate(tampered)

    def test_pending_is_visible_but_does_not_self_gate_project_machine(self):
        result = project_coherence.evaluate_coherence(
            project(), coherence_sensors([pr(ci="pending")]), scope="live"
        )
        ci = coherence_check(result)
        self.assertEqual("UNKNOWN", ci["status"])
        self.assertEqual("PR_CI_PENDING", ci["code"])
        self.assertFalse(ci["required"])
        self.assertEqual("PASS", result["status"])

    def test_failed_is_visible_but_policy_remains_outside_sensor_layer(self):
        result = project_coherence.evaluate_coherence(
            project(), coherence_sensors([pr(ci="failed")]), scope="live"
        )
        ci = coherence_check(result)
        self.assertEqual("FAIL", ci["status"])
        self.assertEqual("PR_CI_FAILED", ci["code"])
        self.assertFalse(ci["required"])
        self.assertEqual("PASS", result["status"])


if __name__ == "__main__":
    unittest.main()
