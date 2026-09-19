import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools import agent_cycle_close_recovery as recovery

BEFORE = "b" * 40
MERGE = "8" * 40
MID = "9" * 40
AFTER = "a" * 40
HEAD = "c" * 40


class FakeTransport:
    def __init__(self, pulls=None, main=AFTER, parents=None):
        self.pulls = pulls if pulls is not None else [{
            "number": 289,
            "state": "closed",
            "merged_at": "2026-09-11T09:51:48Z",
            "merge_commit_sha": MERGE,
            "base": {"ref": "main", "sha": BEFORE},
            "head": {"sha": HEAD},
        }]
        self.main = main
        self.parents = parents if parents is not None else {
            AFTER: [MID],
            MID: [MERGE],
            MERGE: [BEFORE],
        }

    def request(self, method, endpoint):
        if endpoint.endswith("git/ref/heads/main"):
            value = {"object": {"sha": self.main}}
        elif "/git/commits/" in endpoint:
            sha = endpoint.rsplit("/", 1)[-1]
            value = {"sha": sha, "parents": [{"sha": item} for item in self.parents.get(sha, [])]}
        elif endpoint.endswith(f"commits/{MERGE}/pulls"):
            value = self.pulls
        else:
            raise AssertionError(endpoint)
        return SimpleNamespace(body=json.dumps(value))


def source_change(name, branch, before, after):
    return {"kind": "source-head", "name": name, "branch": branch, "before": before, "after": after}


def main_change(name):
    return source_change(name, "main", BEFORE, AFTER)


def closure(*, blockers=None, changes=None, covered=None, uncovered=None, status="UNKNOWN"):
    changes = changes if changes is not None else [main_change("control"), main_change("inspection")]
    covered = covered if covered is not None else []
    uncovered = uncovered if uncovered is not None else ["source-head:control:0", "source-head:inspection:1"]
    return {
        "status": status,
        "receipt": {
            "blockers": blockers if blockers is not None else ["UNATTRIBUTED_DURABLE_DELTA"],
            "delta": {"durableChanges": changes},
            "aggregateReadback": {"coveredDurableChanges": covered, "uncoveredDurableChanges": uncovered},
        },
    }


def live_closure():
    return closure(
        changes=[
            source_change("continuation", "coordination/continuations", "1" * 40, "2" * 40),
            main_change("control"),
            source_change("coordination", "coordination/leases", "3" * 40, "4" * 40),
            main_change("inspection"),
        ],
        covered=["source-head:continuation:0", "source-head:coordination:2"],
        uncovered=["source-head:control:1", "source-head:inspection:3"],
    )


class AgentCycleCloseMergeRecoveryTests(unittest.TestCase):
    def test_exact_control_inspection_main_pair_is_recoverable(self):
        self.assertEqual(recovery.recoverable_main_delta(closure()), (BEFORE, AFTER))

    def test_live_shape_allows_covered_non_main_changes(self):
        self.assertEqual(recovery.recoverable_main_delta(live_closure()), (BEFORE, AFTER))

    def test_extra_uncovered_change_is_not_recoverable(self):
        value = live_closure()
        value["receipt"]["aggregateReadback"]["uncoveredDurableChanges"].append("source-head:coordination:2")
        value["receipt"]["aggregateReadback"]["coveredDurableChanges"].remove("source-head:coordination:2")
        self.assertIsNone(recovery.recoverable_main_delta(value))

    def test_unclassified_durable_change_is_not_recoverable(self):
        value = live_closure()
        value["receipt"]["aggregateReadback"]["coveredDurableChanges"].remove("source-head:coordination:2")
        self.assertIsNone(recovery.recoverable_main_delta(value))

    def test_overlap_between_covered_and_uncovered_is_not_recoverable(self):
        value = live_closure()
        value["receipt"]["aggregateReadback"]["coveredDurableChanges"].append("source-head:control:1")
        self.assertIsNone(recovery.recoverable_main_delta(value))

    def test_uncovered_index_mismatch_is_not_recoverable(self):
        value = live_closure()
        value["receipt"]["aggregateReadback"]["uncoveredDurableChanges"] = ["source-head:control:3", "source-head:inspection:1"]
        self.assertIsNone(recovery.recoverable_main_delta(value))

    def test_extra_blocker_is_not_recoverable(self):
        self.assertIsNone(recovery.recoverable_main_delta(closure(blockers=["AFTER_CONTEXT_UNKNOWN", "UNATTRIBUTED_DURABLE_DELTA"])))

    def test_inspection_after_mismatch_is_not_recoverable(self):
        inspection = main_change("inspection")
        inspection["after"] = "d" * 40
        self.assertIsNone(recovery.recoverable_main_delta(closure(changes=[main_change("control"), inspection])))

    def test_merge_evidence_walks_first_parent_to_original_transition(self):
        evidence = recovery.merge_readback_evidence(
            BEFORE,
            AFTER,
            transport=FakeTransport(),
            expected_pr_number=289,
            expected_merge_sha=MERGE,
        )
        self.assertEqual(evidence["plan"]["target"], {"prNumber": 289})
        self.assertEqual(evidence["observed"]["mergeCommitSha"], MERGE)
        self.assertFalse(evidence["plan"]["authorizesMutation"])

    def test_main_mismatch_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "MAIN_MISMATCH"):
            recovery.merge_readback_evidence(BEFORE, AFTER, transport=FakeTransport(main=MID))

    def test_before_not_in_bounded_first_parent_history_fails_closed(self):
        transport = FakeTransport(parents={AFTER: [MID], MID: ["d" * 40], "d" * 40: []})
        with self.assertRaisesRegex(RuntimeError, "ANCESTRY_MISMATCH"):
            recovery.merge_readback_evidence(BEFORE, AFTER, transport=transport)

    def test_non_linear_history_fails_closed(self):
        transport = FakeTransport(parents={AFTER: [MID, "d" * 40]})
        with self.assertRaisesRegex(RuntimeError, "NONLINEAR_HISTORY"):
            recovery.merge_readback_evidence(BEFORE, AFTER, transport=transport)

    def test_work_merge_sha_mismatch_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "WORK_SHA_MISMATCH"):
            recovery.merge_readback_evidence(BEFORE, AFTER, transport=FakeTransport(), expected_merge_sha="d" * 40)

    def test_work_pr_mismatch_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "WORK_PR_MISMATCH"):
            recovery.merge_readback_evidence(BEFORE, AFTER, transport=FakeTransport(), expected_pr_number=999)

    def test_ambiguous_pr_fails_closed(self):
        base = FakeTransport().pulls[0]
        with self.assertRaisesRegex(RuntimeError, "PR_AMBIGUOUS"):
            recovery.merge_readback_evidence(BEFORE, AFTER, transport=FakeTransport(pulls=[base, dict(base)]))

    def test_work_expectation_requires_done_bound_work(self):
        authority = mock.Mock()
        authority.observe.return_value = SimpleNamespace(items={
            "r0-2-governed-delivery": {"status": "DONE", "prNumber": 289, "lastKnownGood": {"sha": MERGE}}
        })
        with mock.patch.object(recovery.continuation_remote, "GitHubContinuationAuthority", return_value=authority):
            with mock.patch.object(Path, "read_text", return_value=json.dumps({"workRef": {"workId": "r0-2-governed-delivery"}})):
                self.assertEqual(recovery._work_expectation("context.json", transport=object()), (289, MERGE))

    def test_hosted_compatibility_uses_internal_recovery_carrier_only(self):
        root = Path(__file__).resolve().parents[2]
        workflow = (root / ".github" / "workflows" / "hosted-agent-cycle.yml").read_text(encoding="utf-8")
        marker = "- name: Run canonical close compatibility recovery"
        initial, compatibility = workflow.split(marker, 1)
        self.assertIn("python tools/hosted_agent_cycle.py close", initial)
        self.assertIn("python -m tools.agent_cycle_close_recovery.hosted close", compatibility)
        self.assertFalse((root / "tools" / "hosted_agent_cycle_close_recovery.py").exists())

    def test_hosted_compatibility_admits_exact_pre_r6g_lifecycle_signature(self):
        root = Path(__file__).resolve().parents[2]
        workflow = (root / ".github" / "workflows" / "hosted-agent-cycle.yml").read_text(encoding="utf-8")
        eligibility = workflow.split("- name: Qualify observational close compatibility recovery", 1)[1]
        eligibility = eligibility.split("- name: Restore current hosted-cycle carrier", 1)[0]
        self.assertIn("'code': 'AGENT_WRITE_LIFECYCLE_REQUEST_WITHOUT_TERMINAL'", eligibility)
        self.assertIn("'source': 'agent-write-lifecycle-guard'", eligibility)
        self.assertIn("'code': 'AGENT_WRITE_LIFECYCLE_UNKNOWN_AT_CLOSE'", eligibility)
        self.assertIn("'source': 'hosted-agent-cycle'", eligibility)
        self.assertIn("core.get('lossyProjection')", eligibility)
        self.assertIn("recovery.get('operationReplay') == 'NOT_APPLICABLE'", eligibility)

    def test_hosted_compatibility_does_not_admit_unknown_write_lease_failure(self):
        root = Path(__file__).resolve().parents[2]
        workflow = (root / ".github" / "workflows" / "hosted-agent-cycle.yml").read_text(encoding="utf-8")
        eligibility = workflow.split("- name: Qualify observational close compatibility recovery", 1)[1]
        eligibility = eligibility.split("- name: Restore current hosted-cycle carrier", 1)[0]
        self.assertNotIn("'code': 'AGENT_WRITE_LIFECYCLE_UNKNOWN_FAILURE_AT_CLOSE'", eligibility)


if __name__ == "__main__":
    unittest.main()
