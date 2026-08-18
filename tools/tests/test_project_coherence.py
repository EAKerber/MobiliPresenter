import unittest

from tools import project_coherence, project_sensors


def project():
    return {
        "controlBranch": "main",
        "protectedBranches": ["architecture/tpc", "planning/scope"],
        "phase": "between-increments",
        "checkpoint": "C",
        "nextTransition": "next",
        "activeDevelopmentBranch": None,
        "developmentPrNumber": None,
        "blockers": [],
    }


def work(work_id="work", status="IN_PROGRESS", branch="work/ui/task", pr=7):
    return {"id": work_id, "workerId": "developer-ui", "status": status, "branch": branch, "prNumber": pr, "dependsOn": []}


def sensors(prs=None, leases=None, continuations=None, *, pr_available=True, work_available=True):
    return {
        "pullRequests": project_sensors.sensor("PASS" if pr_available else "UNKNOWN", code=None if pr_available else "REMOTE_PR_INVENTORY_UNAVAILABLE", data={"available": pr_available, "items": prs or []}, authority={"kind": "github", "resource": "pull-requests"}),
        "coordination": project_sensors.sensor("PASS", data={"available": True, "leases": leases or [], "intents": []}, authority={"kind": "git-authority", "branch": "coordination/leases"}),
        "continuations": project_sensors.sensor("PASS" if work_available else "UNKNOWN", code=None if work_available else "CONTINUATION_AUTHORITY_UNAVAILABLE", data={"available": work_available, "items": continuations or []}, authority={"kind": "git-authority", "branch": "coordination/continuations"}),
    }


def check(result, check_id):
    return next(item for item in result["checks"] if item["id"] == check_id)


class ProjectCoherenceTests(unittest.TestCase):
    def test_no_active_work_is_coherent(self):
        result = project_coherence.evaluate_coherence(project(), sensors(), scope="live")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(check(result, "work.pr.open")["code"], "NO_ACTIVE_PR_LINKED_WORK")
        self.assertNotIn("development.identity.complete", {item["id"] for item in result["checks"]})

    def test_active_work_missing_pr_fails(self):
        result = project_coherence.evaluate_coherence(project(), sensors(continuations=[work()]), scope="live")
        self.assertEqual(check(result, "work.pr.open")["status"], "FAIL")
        self.assertEqual(check(result, "work.pr.open")["code"], "WORK_PR_NOT_OPEN")

    def test_active_work_pr_head_and_base_must_match(self):
        prs = [{"number": 7, "headRef": "wrong", "baseRef": "other"}]
        result = project_coherence.evaluate_coherence(project(), sensors(prs=prs, continuations=[work()]), scope="live")
        self.assertEqual(check(result, "work.pr.head")["code"], "WORK_PR_BRANCH_MISMATCH")
        self.assertEqual(check(result, "work.pr.base")["code"], "WORK_PR_BASE_MISMATCH")

    def test_work_bound_pr_is_classified_from_work_authority(self):
        prs = [{"number": 7, "headRef": "feature/noncanonical", "baseRef": "main"}]
        result = project_coherence.evaluate_coherence(project(), sensors(prs=prs, continuations=[work(branch="feature/noncanonical")]), scope="live")
        classification = check(result, "pull-requests.classification")
        self.assertEqual(classification["status"], "PASS")
        self.assertEqual(classification["detail"]["items"][0]["classification"], "work-bound")

    def test_protected_and_operations_prs_are_classified(self):
        prs = [{"number": 1, "headRef": "architecture/tpc", "baseRef": "main"}, {"number": 2, "headRef": "work/operations/tooling", "baseRef": "main"}]
        result = project_coherence.evaluate_coherence(project(), sensors(prs=prs), scope="live")
        classification = check(result, "pull-requests.classification")
        self.assertEqual(classification["status"], "PASS")
        self.assertEqual([item["classification"] for item in classification["detail"]["items"]], ["protected", "operations"])

    def test_unclassified_open_pr_fails_when_work_was_observed(self):
        result = project_coherence.evaluate_coherence(project(), sensors(prs=[{"number": 9, "headRef": "feature/mystery", "baseRef": "main"}]), scope="live")
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

    def test_done_work_does_not_require_open_pr(self):
        task = work(status="DONE", branch="ops/old", pr=7)
        result = project_coherence.evaluate_coherence(project(), sensors(continuations=[task]), scope="live")
        self.assertEqual(check(result, "work.pr.open")["status"], "PASS")

    def test_missing_remote_inventory_is_unknown_not_fail(self):
        result = project_coherence.evaluate_coherence(project(), sensors(pr_available=False, continuations=[work()]), scope="live")
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(check(result, "work.pr.open")["status"], "UNKNOWN")

    def test_base_does_not_require_live_work_relation(self):
        result = project_coherence.evaluate_coherence(project(), sensors(work_available=False), scope="base")
        self.assertFalse(check(result, "work.pr.open")["required"])
        self.assertEqual(result["status"], "PASS")

    def test_live_unobserved_work_fails_closed(self):
        result = project_coherence.evaluate_coherence(project(), sensors(work_available=False), scope="live")
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(check(result, "work.pr.open")["code"], "WORK_AUTHORITY_UNAVAILABLE")

    def test_authority_projection_is_derived_and_deduplicated(self):
        current = sensors()
        current["otherPrView"] = project_sensors.sensor("PASS", data={}, authority={"kind": "github", "resource": "pull-requests"})
        authorities = project_coherence.derive_authorities(current)
        github = next(item for item in authorities if item["id"] == "github-pull-requests")
        self.assertEqual(github["observedBy"], ["otherPrView", "pullRequests"])


if __name__ == "__main__":
    unittest.main()
