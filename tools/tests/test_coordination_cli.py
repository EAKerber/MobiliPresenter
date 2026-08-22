from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from tools import coordination, coordination_cli, coordination_transition as transition
from tools.agent_cycle_close import verify_evidence
from tools.coordination_remote import AppliedTransition, AuthorityObservation

HEAD0 = "1" * 40
HEAD1 = "2" * 40
TREE0 = "3" * 40
NOW = datetime(2026, 8, 22, 22, 30, 0, tzinfo=timezone.utc)
OWNER_FLAGS = [
    "--role", "manager-gitops",
    "--session", "cv1b-cli",
    "--branch", "work/operations/cv1b-cli",
]
RESOURCE = "file:ops/coordination/cv1b-cli.shared"


class FakeAuthority:
    repository = transition.DEFAULT_REPOSITORY
    authority_branch = transition.DEFAULT_BRANCH
    state_path = transition.DEFAULT_PATH

    def __init__(self):
        self.state = coordination.empty_state(revision=HEAD0)
        self.head = HEAD0
        self.now = NOW
        self.mutate_calls = 0

    def observe(self):
        return AuthorityObservation(
            head_sha=self.head,
            tree_sha=TREE0,
            state=copy.deepcopy(self.state),
            authority_now=self.now,
        )

    def mutate(self, planner, *, message, expected_revision=None):
        self.mutate_calls += 1
        if expected_revision != self.head:
            raise AssertionError("expected_revision must bind canonical apply")
        candidate, event = planner(copy.deepcopy(self.state), self.now)
        before = self.head
        self.head = HEAD1
        self.state = copy.deepcopy(candidate)
        return AppliedTransition(
            before_sha=before,
            after_sha=HEAD1,
            authority_now=self.now,
            state=copy.deepcopy(candidate),
            event=copy.deepcopy(event),
        )


class CoordinationCliTests(unittest.TestCase):
    def run_cli(self, fake, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = coordination_cli.main(
                argv,
                authority_factory=lambda: fake,
                environ={},
            )
        return code, stdout.getvalue(), stderr.getvalue()

    def test_acquire_builds_plan_without_mutating(self):
        fake = FakeAuthority()
        code, stdout, _ = self.run_cli(
            fake,
            [
                "acquire",
                RESOURCE,
                *OWNER_FLAGS,
                "--reason", "canonical plan",
                "--transition-id", "cv1b-cli-acquire",
                "--json",
            ],
        )
        self.assertEqual(0, code)
        plan = json.loads(stdout)
        self.assertEqual("TransitionPlan 0.1", plan["schemaVersion"])
        self.assertEqual("coordination", plan["domain"])
        self.assertEqual("acquire", plan["action"])
        self.assertEqual(0, fake.mutate_calls)
        self.assertEqual([], fake.state["leases"])

    def test_canonical_transition_id_is_required(self):
        fake = FakeAuthority()
        with self.assertRaises(SystemExit):
            coordination_cli.main(
                [
                    "acquire",
                    RESOURCE,
                    *OWNER_FLAGS,
                    "--reason", "missing id",
                    "--json",
                ],
                authority_factory=lambda: fake,
                environ={},
            )

    def test_apply_emits_agent_close_transition_evidence(self):
        fake = FakeAuthority()
        plan = transition.plan_acquire(
            fake.state,
            authority_head=HEAD0,
            authority_now=NOW,
            owner={
                "role": "manager-gitops",
                "session": "cv1b-cli",
                "branch": "work/operations/cv1b-cli",
                "pr": None,
            },
            resources=[RESOURCE],
            reason="canonical apply",
            transition_id="cv1b-cli-apply",
        )
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            code, stdout, _ = self.run_cli(
                fake,
                [
                    "apply",
                    str(path),
                    "--expected-plan", plan["planHash"],
                    "--json",
                ],
            )
        self.assertEqual(0, code)
        evidence = json.loads(stdout)
        verified = verify_evidence(evidence)
        self.assertEqual("transition-receipt", verified["kind"])
        self.assertEqual("coordination", verified["domain"])
        self.assertEqual(plan["planHash"], verified["planHash"])
        self.assertEqual(1, fake.mutate_calls)

    def test_validate_is_read_only(self):
        fake = FakeAuthority()
        plan = transition.plan_acquire(
            fake.state,
            authority_head=HEAD0,
            authority_now=NOW,
            owner={
                "role": "manager-gitops",
                "session": "cv1b-cli",
                "branch": "work/operations/cv1b-cli",
                "pr": None,
            },
            resources=[RESOURCE],
            reason="canonical validate",
            transition_id="cv1b-cli-validate",
        )
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            code, stdout, _ = self.run_cli(
                fake, ["validate", str(path), "--json"]
            )
        self.assertEqual(0, code)
        payload = json.loads(stdout)
        self.assertEqual("PASS", payload["status"])
        self.assertFalse(payload["authorizesMutation"])
        self.assertEqual(0, fake.mutate_calls)


if __name__ == "__main__":
    unittest.main()
