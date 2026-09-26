import copy
import unittest
from pathlib import Path

from tools import agent, agent_cycle_close
from tools.canonical import stable_hash


MAIN_BEFORE = "1" * 40
MAIN_AFTER = "2" * 40
CONT_BEFORE = "3" * 40
CONT_AFTER = "4" * 40
COORD_BEFORE = "7" * 40
COORD_AFTER = "8" * 40
CYCLE_ID = "cycle-" + "a" * 20
WORK_ID = "r6-black-box-paved-path-canary"
WORK_BRANCH = "work/operations/r6-black-box-live-canary"


def work():
    return {
        "schemaVersion": "ContinuationState 0.2",
        "id": WORK_ID,
        "workerId": "manager-gitops-chat",
        "status": "IN_PROGRESS",
        "branch": WORK_BRANCH,
        "prNumber": None,
        "dependsOn": [],
        "completed": ["run-full-journey-canary"],
        "remaining": ["qualify-r6-promotion-gate"],
        "nextAction": "continue",
        "lastKnownGood": {"sha": MAIN_BEFORE, "checkpoint": "negative-pass"},
        "blockers": [],
        "handoffToWorkerId": None,
    }


def context(work_value=None, *, cycle_id=CYCLE_ID, work_ref=None):
    item = copy.deepcopy(work_value or work())
    return {
        "cycleId": cycle_id,
        "workRef": copy.deepcopy(work_ref or {"workId": WORK_ID}),
        "projectMachine": {
            "sensors": {
                "continuations": {
                    "data": {"items": [item]}
                }
            }
        },
    }


def source_change(name, branch, before, after):
    return {
        "kind": "source-head",
        "name": name,
        "branch": branch,
        "before": before,
        "after": after,
    }


def evidence(*, include_coordination=False):
    changes = [
        source_change(
            "continuation",
            "coordination/continuations",
            CONT_BEFORE,
            CONT_AFTER,
        ),
        source_change("control", "main", MAIN_BEFORE, MAIN_AFTER),
        source_change("inspection", "main", MAIN_BEFORE, MAIN_AFTER),
    ]
    coordination_readback = None
    if include_coordination:
        changes.insert(
            2,
            source_change(
                "coordination",
                "coordination/leases",
                COORD_BEFORE,
                COORD_AFTER,
            ),
        )
        binding_hash = stable_hash({"intents": [], "leases": []})
        coordination_readback = {
            "branch": "coordination/leases",
            "before": COORD_BEFORE,
            "after": COORD_AFTER,
            "workBranch": WORK_BRANCH,
            "states": [
                {"sha": COORD_BEFORE, "bindingHash": binding_hash},
                {"sha": COORD_AFTER, "bindingHash": binding_hash},
            ],
        }

    body = {
        "kind": "agent-cycle-noninterference-readback",
        "schemaVersion": agent_cycle_close.NONINTERFERENCE_SCHEMA,
        "cycleId": CYCLE_ID,
        "workId": WORK_ID,
        "workBranch": WORK_BRANCH,
        "workPrNumber": None,
        "workStateHash": stable_hash(work()),
        "coveredChanges": changes,
        "continuationReadback": {
            "branch": "coordination/continuations",
            "before": CONT_BEFORE,
            "after": CONT_AFTER,
            "workPath": f"ops/continuations/{WORK_ID}.json",
            "changedPaths": [
                "ops/continuations/unrelated-work.json",
            ],
        },
        "coordinationReadback": coordination_readback,
        "controlReadback": {
            "branch": "main",
            "before": MAIN_BEFORE,
            "after": MAIN_AFTER,
            "mergedPullRequests": [
                {
                    "commitSha": MAIN_AFTER,
                    "prNumber": 322,
                    "headBranch": "work/operations/unrelated-change",
                    "baseSha": MAIN_BEFORE,
                }
            ],
        },
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "evidenceHash": stable_hash(body)}


class AgentCycleNonInterferenceVerifierTests(unittest.TestCase):
    def test_current_schema_verifies_without_recovery_generator(self):
        value = evidence()
        self.assertEqual(agent_cycle_close.verify_evidence(value), value)

    def test_coordination_readback_verifies(self):
        value = evidence(include_coordination=True)
        self.assertEqual(agent_cycle_close.verify_evidence(value), value)

    def test_legacy_schema_remains_verifiable(self):
        value = evidence()
        value["schemaVersion"] = agent_cycle_close.LEGACY_NONINTERFERENCE_SCHEMA
        del value["coordinationReadback"]
        body = {key: item for key, item in value.items() if key != "evidenceHash"}
        value["evidenceHash"] = stable_hash(body)
        self.assertEqual(agent_cycle_close.verify_evidence(value), value)

    def test_evidence_hash_mismatch_fails_closed(self):
        value = evidence()
        value["evidenceHash"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "HASH_MISMATCH"):
            agent_cycle_close.verify_evidence(value)

    def test_bound_work_path_fails_closed(self):
        value = evidence()
        value["continuationReadback"]["changedPaths"] = [
            f"ops/continuations/{WORK_ID}.json"
        ]
        body = {key: item for key, item in value.items() if key != "evidenceHash"}
        value["evidenceHash"] = stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "EVIDENCE_INVALID"):
            agent_cycle_close.verify_evidence(value)

    def test_bound_work_merge_fails_closed(self):
        value = evidence()
        value["controlReadback"]["mergedPullRequests"][0]["headBranch"] = WORK_BRANCH
        body = {key: item for key, item in value.items() if key != "evidenceHash"}
        value["evidenceHash"] = stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "EVIDENCE_INVALID"):
            agent_cycle_close.verify_evidence(value)

    def test_context_binding_allows_rebuilt_after_cycle_id(self):
        value = evidence()
        agent_cycle_close._validate_noninterference_binding(
            value,
            context(),
            context(cycle_id="cycle-" + "b" * 20),
        )

    def test_context_binding_rejects_evidence_cycle_mismatch(self):
        value = evidence()
        value["cycleId"] = "cycle-" + "c" * 20
        with self.assertRaisesRegex(RuntimeError, "BINDING_MISMATCH"):
            agent_cycle_close._validate_noninterference_binding(
                value,
                context(),
                context(cycle_id="cycle-" + "b" * 20),
            )

    def test_context_binding_rejects_work_ref_change(self):
        value = evidence()
        with self.assertRaisesRegex(RuntimeError, "BINDING_MISMATCH"):
            agent_cycle_close._validate_noninterference_binding(
                value,
                context(),
                context(work_ref={"workId": "other-work"}),
            )

    def test_context_binding_rejects_changed_work(self):
        value = evidence()
        changed = work()
        changed["nextAction"] = "changed"
        with self.assertRaisesRegex(RuntimeError, "WORK_CHANGED"):
            agent_cycle_close._validate_noninterference_binding(
                value,
                context(),
                context(changed),
            )

    def test_public_close_facade_points_to_canonical_owner(self):
        self.assertIs(agent.agent_cycle_close, agent_cycle_close)

    def test_recovery_generator_package_is_retired(self):
        root = Path(__file__).resolve().parents[2]
        self.assertFalse(
            (root / "tools" / "agent_cycle_close_recovery" / "__init__.py").exists()
        )


if __name__ == "__main__":
    unittest.main()
