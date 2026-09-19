import base64
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools import agent_cycle_close
from tools import agent_cycle_close_recovery
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


class FakeTransport:
    def __init__(
        self,
        *,
        continuation_paths=None,
        main_head_branch="work/operations/r6h-blocked-close-compatibility-recovery",
        main_pr_number=322,
        main_has_pr=True,
        main_second_parent=None,
        coordination_touches_work=False,
    ):
        self.continuation_paths = continuation_paths or [
            "ops/continuations/r6h-blocked-close-compatibility-recovery.json"
        ]
        self.main_head_branch = main_head_branch
        self.main_pr_number = main_pr_number
        self.main_has_pr = main_has_pr
        self.main_second_parent = main_second_parent
        self.coordination_touches_work = coordination_touches_work

    def request(self, method, endpoint):
        self.assert_get(method)
        if endpoint.endswith("git/ref/heads/main"):
            return self.response({"object": {"sha": MAIN_AFTER}})
        if endpoint.endswith("git/ref/heads/coordination/continuations"):
            return self.response({"object": {"sha": CONT_AFTER}})
        if endpoint.endswith("git/ref/heads/coordination/leases"):
            return self.response({"object": {"sha": COORD_AFTER}})
        if endpoint.endswith(f"compare/{CONT_BEFORE}...{CONT_AFTER}"):
            return self.response({
                "status": "ahead",
                "ahead_by": 1,
                "merge_base_commit": {"sha": CONT_BEFORE},
                "commits": [{"sha": CONT_AFTER}],
                "files": [{"filename": path} for path in self.continuation_paths],
            })
        if endpoint.endswith(f"compare/{COORD_BEFORE}...{COORD_AFTER}"):
            return self.response({
                "status": "ahead",
                "ahead_by": 1,
                "merge_base_commit": {"sha": COORD_BEFORE},
                "commits": [{"sha": COORD_AFTER}],
                "files": [{"filename": "ops/coordination/leases.json"}],
            })
        if f"contents/ops/coordination/leases.json?ref=" in endpoint:
            ref = endpoint.rsplit("=", 1)[-1]
            leases = []
            if self.coordination_touches_work and ref == COORD_AFTER:
                leases = [{"resource": f"branch:{WORK_BRANCH}", "owner": {"branch": WORK_BRANCH}}]
            payload = {"intents": [], "leases": leases, "revision": ref, "schemaVersion": "CoordinationState 0.1"}
            encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
            return self.response({"encoding": "base64", "content": encoded})
        if endpoint.endswith(f"git/commits/{MAIN_AFTER}"):
            parents = [{"sha": MAIN_BEFORE}]
            if self.main_second_parent is not None:
                parents.append({"sha": self.main_second_parent})
            return self.response({"sha": MAIN_AFTER, "parents": parents})
        if endpoint.endswith(f"commits/{MAIN_AFTER}/pulls"):
            if not self.main_has_pr:
                return self.response([])
            return self.response([{
                "number": self.main_pr_number,
                "state": "closed",
                "merged_at": "2026-09-19T14:41:17Z",
                "merge_commit_sha": MAIN_AFTER,
                "base": {"ref": "main", "sha": MAIN_BEFORE},
                "head": {"ref": self.main_head_branch, "sha": "5" * 40},
            }])
        raise AssertionError(endpoint)

    @staticmethod
    def response(value):
        return SimpleNamespace(body=json.dumps(value))

    @staticmethod
    def assert_get(method):
        if method != "GET":
            raise AssertionError(method)


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


def context(work_value=None):
    item = copy.deepcopy(work_value or work())
    return {
        "cycleId": CYCLE_ID,
        "workRef": {"workId": WORK_ID},
        "projectMachine": {
            "sensors": {
                "continuations": {
                    "data": {"items": [item]}
                }
            }
        },
    }


def closure(after_context=None, *, include_coordination=False):
    changes = [
        {
            "kind": "source-head",
            "name": "continuation",
            "branch": "coordination/continuations",
            "before": CONT_BEFORE,
            "after": CONT_AFTER,
        },
        {
            "kind": "source-head",
            "name": "control",
            "branch": "main",
            "before": MAIN_BEFORE,
            "after": MAIN_AFTER,
        },
        {
            "kind": "source-head",
            "name": "inspection",
            "branch": "main",
            "before": MAIN_BEFORE,
            "after": MAIN_AFTER,
        },
    ]
    if include_coordination:
        changes.insert(2, {
            "kind": "source-head",
            "name": "coordination",
            "branch": "coordination/leases",
            "before": COORD_BEFORE,
            "after": COORD_AFTER,
        })
    return {
        "cycleId": CYCLE_ID,
        "status": "UNKNOWN",
        "afterContext": after_context or context(),
        "receipt": {
            "blockers": ["UNATTRIBUTED_DURABLE_DELTA"],
            "delta": {"durableChanges": changes},
            "aggregateReadback": {
                "coveredDurableChanges": [],
                "uncoveredDurableChanges": (
                    [
                        "source-head:continuation:0",
                        "source-head:control:1",
                        "source-head:coordination:2",
                        "source-head:inspection:3",
                    ] if include_coordination else [
                        "source-head:continuation:0",
                        "source-head:control:1",
                        "source-head:inspection:2",
                    ]
                ),
            },
        },
    }


class ConcurrentCloseAttributionTests(unittest.TestCase):
    def evidence(self, *, transport=None, after_context=None, include_coordination=False):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "context.json"
            path.write_text(json.dumps(context()), encoding="utf-8")
            return agent_cycle_close_recovery.noninterference_evidence(
                closure(after_context, include_coordination=include_coordination),
                context_path=str(path),
                transport=transport or FakeTransport(),
            )

    def test_proves_unrelated_shared_authority_drift(self):
        evidence = self.evidence()
        self.assertEqual(evidence["kind"], "agent-cycle-noninterference-readback")
        self.assertEqual(evidence["workId"], WORK_ID)
        self.assertEqual(evidence["workStateHash"], stable_hash(work()))
        self.assertEqual(len(evidence["coveredChanges"]), 3)
        self.assertEqual(
            evidence["controlReadback"]["mergedPullRequests"][0]["headBranch"],
            "work/operations/r6h-blocked-close-compatibility-recovery",
        )
        self.assertEqual(agent_cycle_close.verify_evidence(evidence), evidence)

    def test_two_parent_merge_commit_follows_first_parent(self):
        evidence = self.evidence(
            transport=FakeTransport(main_second_parent="6" * 40)
        )
        pulls = evidence["controlReadback"]["mergedPullRequests"]
        self.assertEqual(len(pulls), 1)
        self.assertEqual(pulls[0]["commitSha"], MAIN_AFTER)
        self.assertEqual(pulls[0]["baseSha"], MAIN_BEFORE)

    def test_proves_coordination_drift_when_bound_work_never_appears(self):
        evidence = self.evidence(include_coordination=True)
        self.assertEqual(len(evidence["coveredChanges"]), 4)
        self.assertEqual(evidence["coordinationReadback"]["branch"], "coordination/leases")
        self.assertEqual(
            len({state["bindingHash"] for state in evidence["coordinationReadback"]["states"]}),
            1,
        )
        self.assertEqual(agent_cycle_close.verify_evidence(evidence), evidence)

    def test_coordination_bound_work_touch_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "BOUND_WORK_COORDINATION_TOUCHED"):
            self.evidence(
                transport=FakeTransport(coordination_touches_work=True),
                include_coordination=True,
            )

    def test_bound_work_file_touch_fails_closed(self):
        transport = FakeTransport(
            continuation_paths=[f"ops/continuations/{WORK_ID}.json"]
        )
        with self.assertRaisesRegex(RuntimeError, "WORK_TOUCHED"):
            self.evidence(transport=transport)

    def test_bound_work_merge_fails_closed(self):
        transport = FakeTransport(main_head_branch=WORK_BRANCH)
        with self.assertRaisesRegex(RuntimeError, "BOUND_WORK_MERGE"):
            self.evidence(transport=transport)

    def test_direct_main_commit_fails_closed(self):
        transport = FakeTransport(main_has_pr=False)
        with self.assertRaisesRegex(RuntimeError, "PR_AMBIGUOUS"):
            self.evidence(transport=transport)

    def test_changed_bound_work_fails_closed(self):
        changed = work()
        changed["nextAction"] = "changed"
        with self.assertRaisesRegex(RuntimeError, "WORK_CHANGED"):
            self.evidence(after_context=context(changed))

    def test_evidence_hash_and_exact_change_binding_are_enforced(self):
        evidence = self.evidence()
        bad_hash = copy.deepcopy(evidence)
        bad_hash["evidenceHash"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "HASH_MISMATCH"):
            agent_cycle_close.verify_evidence(bad_hash)

        inconsistent = copy.deepcopy(evidence)
        inconsistent["coveredChanges"][0]["after"] = "9" * 40
        body = {key: value for key, value in inconsistent.items() if key != "evidenceHash"}
        inconsistent["evidenceHash"] = stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "EVIDENCE_INVALID"):
            agent_cycle_close.verify_evidence(inconsistent)

    def test_context_binding_rejects_changed_work_even_with_valid_evidence(self):
        evidence = self.evidence()
        changed = work()
        changed["nextAction"] = "changed"
        with self.assertRaisesRegex(RuntimeError, "WORK_CHANGED"):
            agent_cycle_close._validate_noninterference_binding(
                evidence, context(), context(changed)
            )


if __name__ == "__main__":
    unittest.main()
