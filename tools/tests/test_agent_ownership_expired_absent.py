import unittest

from tools import agent_ownership


ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-chat",
    "sessionId": "session-a",
}
BRANCH = "work/operations/e5"
LEASE_ID = "agent-write-test:0"


def binding():
    return {"leaseId": LEASE_ID}


def lease(*, lease_id=LEASE_ID, branch=BRANCH, session="session-a"):
    return {
        "leaseId": lease_id,
        "resource": f"branch:{branch}",
        "owner": {
            "role": "manager-gitops",
            "session": session,
            "branch": branch,
            "pr": None,
        },
    }


class ExpiredAbsentOwnershipTests(unittest.TestCase):
    def state(self, leases):
        return agent_ownership._expired_binding_authority_state(
            leases,
            binding=binding(),
            actor=ACTOR,
            branch=BRANCH,
        )

    def test_exact_materialized_lease_remains_expired(self):
        self.assertEqual("EXPIRED", self.state([lease()]))

    def test_canonically_absent_resource_is_released(self):
        self.assertEqual("RELEASED", self.state([]))

    def test_other_lease_on_same_resource_is_unknown(self):
        self.assertEqual(
            "UNKNOWN",
            self.state([lease(lease_id="other:0", session="session-b")]),
        )

    def test_unrelated_resource_does_not_block_absence(self):
        self.assertEqual(
            "RELEASED",
            self.state([lease(lease_id="other:0", branch="work/operations/other")]),
        )

    def test_duplicate_exact_materialization_is_unknown(self):
        self.assertEqual("UNKNOWN", self.state([lease(), lease()]))


if __name__ == "__main__":
    unittest.main()
