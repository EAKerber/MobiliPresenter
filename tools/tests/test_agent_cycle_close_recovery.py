import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools import agent_cycle_close_recovery as recovery


BEFORE = "b" * 40
AFTER = "a" * 40
HEAD = "c" * 40


class FakeTransport:
    def __init__(self, pulls=None, parent=BEFORE, main=AFTER):
        self.pulls = pulls if pulls is not None else [
            {
                "number": 289,
                "state": "closed",
                "merged_at": "2026-09-11T09:51:48Z",
                "merge_commit_sha": AFTER,
                "base": {"ref": "main", "sha": BEFORE},
                "head": {"sha": HEAD},
            }
        ]
        self.parent = parent
        self.main = main

    def request(self, method, endpoint):
        self.last = (method, endpoint)
        if endpoint.endswith("git/ref/heads/main"):
            value = {"object": {"sha": self.main}}
        elif f"git/commits/{AFTER}" in endpoint:
            value = {"sha": AFTER, "parents": [{"sha": self.parent}]}
        elif f"commits/{AFTER}/pulls" in endpoint:
            value = self.pulls
        else:
            raise AssertionError(endpoint)
        return SimpleNamespace(body=json.dumps(value))


def closure(*, blockers=None, changes=None, uncovered=None, status="UNKNOWN"):
    changes = changes if changes is not None else [{
        "kind": "source-head",
        "name": "control",
        "branch": "main",
        "before": BEFORE,
        "after": AFTER,
    }]
    return {
        "status": status,
        "receipt": {
            "blockers": blockers if blockers is not None else ["UNATTRIBUTED_DURABLE_DELTA"],
            "delta": {"durableChanges": changes},
            "aggregateReadback": {
                "uncoveredDurableChanges": uncovered if uncovered is not None else ["source-head:control:0"]
            },
        },
    }


class AgentCycleCloseMergeRecoveryTests(unittest.TestCase):
    def test_exact_main_delta_is_recoverable(self):
        self.assertEqual(recovery.recoverable_main_delta(closure()), (BEFORE, AFTER))

    def test_extra_blocker_is_not_recoverable(self):
        value = closure(blockers=["AFTER_CONTEXT_UNKNOWN", "UNATTRIBUTED_DURABLE_DELTA"])
        self.assertIsNone(recovery.recoverable_main_delta(value))

    def test_merge_evidence_requires_exact_parent_main_and_pr(self):
        evidence = recovery.merge_readback_evidence(BEFORE, AFTER, transport=FakeTransport())
        self.assertEqual(evidence["kind"], "git-mutation-plan-readback")
        self.assertEqual(evidence["plan"]["operation"], "merge-pr")
        self.assertEqual(evidence["plan"]["target"], {"prNumber": 289})
        self.assertEqual(evidence["observed"]["mergeCommitSha"], AFTER)
        self.assertFalse(evidence["plan"]["authorizesMutation"])

    def test_main_mismatch_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "MAIN_MISMATCH"):
            recovery.merge_readback_evidence(BEFORE, AFTER, transport=FakeTransport(main=BEFORE))

    def test_parent_mismatch_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "PARENT_MISMATCH"):
            recovery.merge_readback_evidence(BEFORE, AFTER, transport=FakeTransport(parent="d" * 40))

    def test_ambiguous_pr_fails_closed(self):
        base = FakeTransport().pulls[0]
        with self.assertRaisesRegex(RuntimeError, "PR_AMBIGUOUS"):
            recovery.merge_readback_evidence(
                BEFORE,
                AFTER,
                transport=FakeTransport(pulls=[base, dict(base)]),
            )


    def test_hosted_workflow_admits_exact_unattributed_signature(self):
        workflow = (
            Path(__file__).resolve().parents[2]
            / ".github"
            / "workflows"
            / "hosted-agent-cycle.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("'code': 'UNATTRIBUTED_DURABLE_DELTA'", workflow)
        self.assertIn("'code': 'HOSTED_AGENT_CLOSE_NOT_PASS'", workflow)

    def test_recovery_keeps_original_unknown_when_observation_fails(self):
        original = closure()
        with mock.patch.object(recovery, "merge_readback_evidence", side_effect=RuntimeError("NOPE")):
            self.assertIs(
                recovery.recover_closure(
                    original,
                    context_path="context.json",
                    machine_scope="live",
                    observations_path=None,
                    runtime_providers=None,
                    evidence_paths=[],
                ),
                original,
            )


if __name__ == "__main__":
    unittest.main()
