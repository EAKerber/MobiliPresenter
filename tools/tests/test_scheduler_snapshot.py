import copy
import unittest

from tools import scheduler_snapshot as snapshot
from tools.canonical import stable_hash


CONTROL = "1" * 40
COORDINATION = "2" * 40
CONTINUATION = "3" * 40


def fixture():
    inspection_body = {
        "schemaVersion": "MaintenanceInspection 0.3",
        "repository": "EAKerber/MobiliPresenter",
        "observedGit": {"head": CONTROL},
        "coordination": {"available": True, "authorityHead": COORDINATION},
        "continuationAuthority": {"available": True, "authorityHead": CONTINUATION},
        "recommendation": {
            "action": "CONTINUE",
            "reasonCode": "TEST",
            "focus": "development",
            "decisionScope": "operational-only",
            "semanticAuthority": False,
        },
        "readOnly": True,
    }
    inspection = {**inspection_body, "inspectionHash": stable_hash(inspection_body)}
    plan_body = {
        "schemaVersion": "SchedulerPlan 0.2",
        "inspectionHash": inspection["inspectionHash"],
        "action": "CONTINUE",
        "reasonCode": "TEST",
        "focus": "development",
        "dispatch": {
            "shouldWake": True,
            "channelClass": "supervisor",
            "target": "gitops-supervisor",
            "workId": None,
        },
        "decisionScope": "operational-only",
        "semanticAuthority": False,
        "transportSideEffects": False,
        "readOnly": True,
    }
    plan = {**plan_body, "planHash": stable_hash(plan_body)}
    body = {
        "schemaVersion": "SchedulerSnapshot 0.1",
        "repository": "EAKerber/MobiliPresenter",
        "sourceHeads": {
            "control": CONTROL,
            "coordination": COORDINATION,
            "continuation": CONTINUATION,
        },
        "inspection": inspection,
        "plan": plan,
        "readOnly": True,
    }
    return {**body, "snapshotHash": stable_hash(body)}


def validate(value):
    return snapshot.validate_snapshot(
        value,
        expected_control_head=CONTROL,
        expected_coordination_head=COORDINATION,
        expected_continuation_head=CONTINUATION,
    )


class SchedulerSnapshotTests(unittest.TestCase):
    def test_valid_snapshot_returns_embedded_plan_without_replanning(self):
        result = validate(fixture())
        self.assertTrue(result["ok"])
        self.assertEqual(result["dispatch"]["target"], "gitops-supervisor")
        self.assertEqual(result["plan"]["planHash"], result["planHash"])

    def test_tampered_snapshot_is_rejected(self):
        value = fixture()
        value["plan"]["dispatch"]["target"] = "developer-ui"
        with self.assertRaisesRegex(RuntimeError, "SNAPSHOT_HASH_MISMATCH"):
            validate(value)

    def test_stale_heads_fail_closed(self):
        value = fixture()
        with self.assertRaisesRegex(RuntimeError, "STALE_CONTROL"):
            snapshot.validate_snapshot(value,expected_control_head="4"*40,expected_coordination_head=COORDINATION,expected_continuation_head=CONTINUATION)
        with self.assertRaisesRegex(RuntimeError, "STALE_COORDINATION"):
            snapshot.validate_snapshot(value,expected_control_head=CONTROL,expected_coordination_head="4"*40,expected_continuation_head=CONTINUATION)
        with self.assertRaisesRegex(RuntimeError, "STALE_CONTINUATION"):
            snapshot.validate_snapshot(value,expected_control_head=CONTROL,expected_coordination_head=COORDINATION,expected_continuation_head="4"*40)

    def test_internal_source_head_mismatch_is_rejected(self):
        value = fixture(); value["sourceHeads"]["coordination"] = "4" * 40
        body = {k: v for k, v in value.items() if k != "snapshotHash"}; value["snapshotHash"] = stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "COORDINATION_INTERNAL_MISMATCH"): validate(value)

    def test_plan_boundary_and_hash_are_revalidated(self):
        value = fixture(); value["plan"]["transportSideEffects"] = True
        plan_body = {k: v for k, v in value["plan"].items() if k != "planHash"}; value["plan"]["planHash"] = stable_hash(plan_body)
        body = {k: v for k, v in value.items() if k != "snapshotHash"}; value["snapshotHash"] = stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "PLAN_BOUNDARY_INVALID"): validate(value)


if __name__ == "__main__":
    unittest.main()
