import unittest

from tools import project_coherence, project_sensors


def project(active=None, pr=None):
    return {
        "controlBranch": "main",
        "preserveBranches": ["architecture/tpc", "planning/scope"],
        "phase": "between-increments",
        "checkpoint": "C",
        "nextTransition": "next",
        "activeDevelopmentBranch": active,
        "developmentPrNumber": pr,
        "blockers": [],
    }


def sensors(prs=None, leases=None, continuations=None, *, pr_available=True):
    return {
        "pullRequests": project_sensors.sensor(
            "PASS" if pr_available else "UNKNOWN",
            code=None if pr_available else "REMOTE_PR_INVENTORY_UNAVAILABLE",
            data={"available": pr_available, "items": prs or []},
            authority={"kind": "github", "resource": "pull-requests"},
        ),
        "coordination": project_sensors.sensor(
            "PASS",
            data={"available": True, "leases": leases or [], "intents": []},
            authority={"kind": "git-authority", "branch": "coordination/leases"},
        ),
        "continuations": project_sensors.sensor(
            "PASS",
            data={"available": True, "items": continuations or []},
            authority={"kind": "git-authority", "branch": "coordination/continuations"},
        ),
    }


def check(result, check_id):
    return next(item for item in result["checks"] if item["id"] == check_id)


class ProjectCoherenceTests(unittest.TestCase):
    def test_no_active_development_is_coherent(self):
        result = project_coherence.evaluate_coherence(project(), sensors(), scope="live")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(check(result, "development.identity.complete")["code"], "NO_ACTIVE_DEVELOPMENT")

    def test_incomplete_development_identity_fails(self):
        result = project_coherence.evaluate_coherence(project("ops/work", None), sensors(), scope="live")
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(check(result, "development.identity.complete")["code"], "DEVELOPMENT_IDENTITY_INCOMPLETE")

    def test_active_pr_missing_fails(self):
        result = project_coherence.evaluate_coherence(project("ops/work", 7), sensors(), scope="live")
        self.assertEqual(check(result, "development.pr.open")["status"], "FAIL")
        self.assertEqual(check(result, "development.pr.open")["code"], "ACTIVE_PR_NOT_OPEN")

    def test_active_pr_head_and_base_must_match(self):
        prs = [{"number": 7, "headRef": "wrong", "baseRef": "other"}]
        result = project_coherence.evaluate_coherence(project("ops/work", 7), sensors(prs=prs), scope="live")
        self.assertEqual(check(result, "development.pr.head")["code"], "ACTIVE_PR_HEAD_MISMATCH")
        self.assertEqual(check(result, "development.pr.base")["code"], "ACTIVE_PR_BASE_MISMATCH")

    def test_preserved_and_operations_prs_are_classified(self):
        prs = [
            {"number": 1, "headRef": "architecture/tpc", "baseRef": "main"},
            {"number": 2, "headRef": "ops/tooling", "baseRef": "main"},
        ]
        result = project_coherence.evaluate_coherence(project(), sensors(prs=prs), scope="live")
        classification = check(result, "pull-requests.classification")
        self.assertEqual(classification["status"], "PASS")
        self.assertEqual([item["classification"] for item in classification["detail"]["items"]], ["preserved", "operations"])

    def test_unclassified_open_pr_fails(self):
        result = project_coherence.evaluate_coherence(
            project(), sensors(prs=[{"number": 9, "headRef": "feature/mystery", "baseRef": "main"}]), scope="live"
        )
        classification = check(result, "pull-requests.classification")
        self.assertEqual(classification["status"], "FAIL")
        self.assertEqual(classification["code"], "UNCLASSIFIED_OPEN_PR")

    def test_lease_without_pr_is_allowed(self):
        lease = {"leaseId": "L1", "owner": {"branch": "ops/work", "pr": None}}
        result = project_coherence.evaluate_coherence(project(), sensors(leases=[lease]), scope="live")
        self.assertEqual(check(result, "coordination.lease.pr")["status"], "PASS")

    def test_lease_missing_pr_fails(self):
        lease = {"leaseId": "L1", "owner": {"branch": "ops/work", "pr": 7}}
        result = project_coherence.evaluate_coherence(project(), sensors(leases=[lease]), scope="live")
        lease_check = check(result, "coordination.lease.pr")
        self.assertEqual(lease_check["status"], "FAIL")
        self.assertEqual(lease_check["code"], "LEASE_OWNER_PR_NOT_OPEN")

    def test_lease_branch_mismatch_fails(self):
        lease = {"leaseId": "L1", "owner": {"branch": "ops/work", "pr": 7}}
        prs = [{"number": 7, "headRef": "ops/other", "baseRef": "main"}]
        result = project_coherence.evaluate_coherence(project(), sensors(prs=prs, leases=[lease]), scope="live")
        self.assertEqual(check(result, "coordination.lease.pr")["code"], "LEASE_OWNER_BRANCH_MISMATCH")

    def test_active_continuation_missing_pr_fails(self):
        task = {"id": "work", "status": "READY", "branch": "ops/work", "prNumber": 7}
        result = project_coherence.evaluate_coherence(project(), sensors(continuations=[task]), scope="live")
        continuation_check = check(result, "continuations.pr")
        self.assertEqual(continuation_check["status"], "FAIL")
        self.assertEqual(continuation_check["code"], "CONTINUATION_PR_NOT_OPEN")

    def test_done_continuation_does_not_require_open_pr(self):
        task = {"id": "probe", "status": "DONE", "branch": "ops/old", "prNumber": 7}
        result = project_coherence.evaluate_coherence(project(), sensors(continuations=[task]), scope="live")
        self.assertEqual(check(result, "continuations.pr")["status"], "PASS")

    def test_missing_remote_inventory_is_unknown_not_fail(self):
        result = project_coherence.evaluate_coherence(project("ops/work", 7), sensors(pr_available=False), scope="live")
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(check(result, "development.pr.open")["status"], "UNKNOWN")

    def test_base_does_not_require_live_continuation_relation(self):
        broken = sensors()
        broken["continuations"] = project_sensors.sensor(
            "UNKNOWN", code="CONTINUATION_AUTHORITY_UNAVAILABLE", data={"available": False, "items": []}
        )
        result = project_coherence.evaluate_coherence(project(), broken, scope="base")
        self.assertFalse(check(result, "continuations.pr")["required"])
        self.assertEqual(result["status"], "PASS")

    def test_authority_projection_is_derived_and_deduplicated(self):
        current = sensors()
        current["otherPrView"] = project_sensors.sensor(
            "PASS", data={}, authority={"kind": "github", "resource": "pull-requests"}
        )
        authorities = project_coherence.derive_authorities(current)
        github = next(item for item in authorities if item["id"] == "github-pull-requests")
        self.assertEqual(github["observedBy"], ["otherPrView", "pullRequests"])


if __name__ == "__main__":
    unittest.main()
