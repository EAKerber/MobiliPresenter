from __future__ import annotations

import copy
import unittest

from tools import (
    agent_cycle,
    agent_cycle_close,
    agent_cycle_close_review,
    agent_cycle_identity,
    agent_cycle_obligations,
    agent_cycle_resources,
    hosted_agent_cycle as hosted,
    project_machine,
    runtime_capabilities,
)
from tools.canonical import stable_hash

WORK_ID = "m13-r1c-test"
BRANCH = "work/operations/m13-r1c-test"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "m13-r1c-test",
}


def _context(work: bool = True) -> dict:
    machine = project_machine.inspect_local()
    runtime = runtime_capabilities.build_inspection(
        runtime_capabilities.local_provider_observations()
    )
    profile = agent_cycle.entry_profile("manager-gitops", "inspect-and-plan")
    return agent_cycle.build_context(
        role="manager-gitops",
        declared_intent="inspect-and-plan",
        lifecycle_phase=profile["lifecyclePhase"],
        objects=profile["objects"],
        operations=profile["operations"],
        scopes=profile["scope"],
        machine=machine,
        runtime_inspection=runtime,
        work_ref={"workId": WORK_ID} if work else None,
    )


def _manifest(context: dict) -> dict:
    source = {
        "workflow": "hosted-agent-cycle",
        "sourceSha": "a" * 40,
        "runId": 123,
        "issueNumber": 145,
        "commentId": 100,
    }
    cycle_instance_id = agent_cycle_identity.hosted_cycle_instance_id(
        source, ACTOR, context["contextHash"]
    )
    core = {
        "schemaVersion": hosted.BEGIN_MANIFEST_SCHEMA,
        "requestId": "m13-r1c-begin",
        "commandHash": "b" * 64,
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": "inspect-and-plan",
        "machineScope": "live",
        "source": source,
        "artifactName": "agent-cycle-begin-123",
        "cycleId": context["cycleId"],
        "cycleInstanceId": cycle_instance_id,
        "contextHash": context["contextHash"],
        "carrierFeatures": copy.deepcopy(hosted.CURRENT_FEATURES),
        "status": "READY",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "manifestHash": stable_hash(core)}


def _closure(context: dict) -> dict:
    after = copy.deepcopy(context)
    receipt = agent_cycle_close.build_receipt(context, after, evidence=[])
    body = {
        "schemaVersion": agent_cycle_close.CLOSURE_SCHEMA,
        "cycleId": context["cycleId"],
        "beforeContextHash": context["contextHash"],
        "afterContext": after,
        "receipt": receipt,
        "status": receipt["status"],
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "closureHash": stable_hash(body)}


def _origin(label: str) -> dict:
    return agent_cycle_resources.origin(
        label, stable_hash({"label": label}), "observe"
    )


def _resource_set(
    manifest: dict,
    *,
    branch: bool = False,
    lifecycle: bool = False,
) -> dict:
    resources = []
    if branch:
        resources.append(
            agent_cycle_resources.resource(
                "git-branch",
                {"repository": hosted.REPOSITORY, "branch": BRANCH},
                _origin("branch"),
            )
        )
    if lifecycle:
        resources.append(
            agent_cycle_resources.resource(
                "lease-scope",
                {
                    "repository": hosted.REPOSITORY,
                    "branch": BRANCH,
                    "role": ACTOR["role"],
                    "sessionId": ACTOR["sessionId"],
                },
                _origin("lease"),
            )
        )
    return agent_cycle_resources.build_resource_set(
        repository=hosted.REPOSITORY,
        cycle_instance_id=manifest["cycleInstanceId"],
        resources=resources,
    )


def _artifacts(
    context: dict,
    manifest: dict,
    *,
    branch: bool = False,
    lifecycle: bool = False,
    work_status: str = "DONE",
    branch_exists: bool = False,
    branch_bindings: list[dict] | None = None,
    lifecycle_state: str = "RELEASED",
):
    resources = _resource_set(manifest, branch=branch, lifecycle=lifecycle)
    inventory = agent_cycle_obligations.build_inventory(
        resources,
        work_ref=(
            context.get("workRef")
            if context.get("schemaVersion") == agent_cycle.SCHEMA_VERSION
            else None
        ),
    )
    dispositions = []
    for obligation in inventory["obligations"]:
        kind = obligation["kind"]
        if kind == "work-disposition":
            dispositions.append(
                agent_cycle_obligations.disposition(
                    obligation,
                    observation_status="PASS",
                    reason_codes=[],
                    domain_state={
                        "authorityHead": "1" * 40,
                        "exists": True,
                        "status": work_status,
                    },
                )
            )
        elif kind == "git-branch-disposition":
            dispositions.append(
                agent_cycle_obligations.disposition(
                    obligation,
                    observation_status="PASS",
                    reason_codes=[],
                    domain_state={
                        "exists": branch_exists,
                        "headSha": "2" * 40 if branch_exists else None,
                        "workAuthorityHead": "1" * 40,
                        "activeWorkBindings": [] if branch_bindings is None else branch_bindings,
                    },
                )
            )
        elif kind == "write-lifecycle-disposition":
            dispositions.append(
                agent_cycle_obligations.disposition(
                    obligation,
                    observation_status="PASS",
                    reason_codes=[],
                    domain_state={
                        "state": lifecycle_state,
                        "reportHash": "3" * 64,
                    },
                )
            )
    return (
        resources,
        inventory,
        agent_cycle_obligations.build_disposition_set(inventory, dispositions),
    )


def _review(context: dict, manifest: dict, artifacts) -> dict:
    resources, inventory, dispositions = artifacts
    return agent_cycle_close_review.build_review(
        context=context,
        manifest=manifest,
        closure=_closure(context),
        resource_set=resources,
        inventory=inventory,
        disposition_set=dispositions,
        evidence=[],
    )


class AgentCycleCloseReviewR1CTests(unittest.TestCase):
    def test_incomplete_provider_coverage_prevents_false_clean_termination(self):
        context = _context()
        manifest = _manifest(context)
        review = _review(context, manifest, _artifacts(context, manifest))

        self.assertEqual("INSUFFICIENT_OBSERVATION", review["status"])
        self.assertFalse(review["cleanTerminationProven"])
        self.assertEqual(1, review["summary"]["dischargedCount"])
        self.assertIn(
            "AGENT_CYCLE_PROVIDER_COVERAGE_INCOMPLETE", review["reasonCodes"]
        )
        agent_cycle_close_review.validate_review(review)

    def test_work_handoff_is_explicit_continuity_not_clean_termination(self):
        context = _context()
        manifest = _manifest(context)
        review = _review(
            context,
            manifest,
            _artifacts(context, manifest, work_status="HANDOFF"),
        )

        work = review["obligations"][0]
        self.assertEqual("CARRIED_FORWARD", work["outcome"])
        self.assertEqual(["WORK_HANDOFF"], work["reasonCodes"])
        self.assertEqual(1, review["summary"]["handoffCount"])
        self.assertEqual(1, review["summary"]["carriedForwardCount"])
        self.assertEqual("INSUFFICIENT_OBSERVATION", review["status"])

    def test_existing_branch_without_active_work_is_known_outstanding(self):
        context = _context(work=False)
        manifest = _manifest(context)
        review = _review(
            context,
            manifest,
            _artifacts(
                context,
                manifest,
                branch=True,
                branch_exists=True,
                branch_bindings=[],
            ),
        )

        self.assertEqual("OUTSTANDING_OBLIGATIONS", review["status"])
        self.assertEqual(1, review["summary"]["outstandingCount"])
        self.assertIn("GIT_BRANCH_UNBOUND_AT_CLOSE", review["reasonCodes"])

    def test_existing_branch_bound_to_active_work_is_carried_forward(self):
        context = _context()
        manifest = _manifest(context)
        binding = {
            "workId": WORK_ID,
            "workerId": "manager-gitops-a",
            "status": "IN_PROGRESS",
            "branch": BRANCH,
            "prNumber": None,
        }
        review = _review(
            context,
            manifest,
            _artifacts(
                context,
                manifest,
                branch=True,
                work_status="IN_PROGRESS",
                branch_exists=True,
                branch_bindings=[binding],
            ),
        )

        self.assertEqual(2, review["summary"]["carriedForwardCount"])
        self.assertEqual(0, review["summary"]["outstandingCount"])
        self.assertIn("GIT_BRANCH_BOUND_TO_ACTIVE_WORK", review["reasonCodes"])

    def test_active_write_lifecycle_is_known_outstanding(self):
        context = _context(work=False)
        manifest = _manifest(context)
        review = _review(
            context,
            manifest,
            _artifacts(
                context,
                manifest,
                lifecycle=True,
                lifecycle_state="ACTIVE",
            ),
        )

        self.assertEqual("OUTSTANDING_OBLIGATIONS", review["status"])
        self.assertIn("AGENT_WRITE_LIFECYCLE_ACTIVE_AT_CLOSE", review["reasonCodes"])

    def test_unknown_native_disposition_stays_unknown(self):
        context = _context()
        manifest = _manifest(context)
        resources, inventory, _ = _artifacts(context, manifest)
        obligation = inventory["obligations"][0]
        unknown = agent_cycle_obligations.disposition(
            obligation,
            observation_status="UNKNOWN",
            reason_codes=["AGENT_CYCLE_DISPOSITION_WORK_AUTHORITY_UNAVAILABLE"],
            domain_state={"authorityHead": None, "exists": None, "status": None},
        )
        dispositions = agent_cycle_obligations.build_disposition_set(
            inventory, [unknown]
        )
        review = _review(context, manifest, (resources, inventory, dispositions))

        self.assertEqual("UNKNOWN", review["obligations"][0]["outcome"])
        self.assertEqual(1, review["summary"]["unknownCount"])
        self.assertIn(
            "AGENT_CYCLE_DISPOSITION_WORK_AUTHORITY_UNAVAILABLE",
            review["reasonCodes"],
        )

    def test_cycle_instance_substitution_is_rejected(self):
        context = _context()
        manifest = _manifest(context)
        other_resources = agent_cycle_resources.build_resource_set(
            repository=hosted.REPOSITORY,
            cycle_instance_id="cycle-instance-" + "f" * 24,
            resources=[],
        )
        inventory = agent_cycle_obligations.build_inventory(
            other_resources, work_ref={"workId": WORK_ID}
        )
        obligation = inventory["obligations"][0]
        disposition = agent_cycle_obligations.disposition(
            obligation,
            observation_status="PASS",
            reason_codes=[],
            domain_state={
                "authorityHead": "1" * 40,
                "exists": True,
                "status": "DONE",
            },
        )
        dispositions = agent_cycle_obligations.build_disposition_set(
            inventory, [disposition]
        )

        with self.assertRaisesRegex(
            RuntimeError, "AGENT_CYCLE_CLOSE_REVIEW_BINDING_MISMATCH"
        ):
            agent_cycle_close_review.build_review(
                context=context,
                manifest=manifest,
                closure=_closure(context),
                resource_set=other_resources,
                inventory=inventory,
                disposition_set=dispositions,
                evidence=[],
            )

    def test_rehashed_authority_tamper_is_rejected(self):
        context = _context()
        manifest = _manifest(context)
        review = _review(context, manifest, _artifacts(context, manifest))
        tampered = copy.deepcopy(review)
        tampered["authorizesMutation"] = True
        body = {
            key: copy.deepcopy(value)
            for key, value in tampered.items()
            if key != "reviewHash"
        }
        tampered["reviewHash"] = stable_hash(body)

        with self.assertRaisesRegex(
            RuntimeError, "AGENT_CYCLE_CLOSE_REVIEW_AUTHORITY_INVALID"
        ):
            agent_cycle_close_review.validate_review(tampered)


if __name__ == "__main__":
    unittest.main()
