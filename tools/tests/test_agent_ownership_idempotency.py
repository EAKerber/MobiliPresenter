from __future__ import annotations

import json
import unittest

from tools import agent_ownership, hosted_handle_requests


class AgentOwnershipIdempotencyTests(unittest.TestCase):
    def test_exact_write_lease_request_is_reused(self) -> None:
        request = {"requestId": "same"}
        body = (
            hosted_handle_requests.WRITE_LEASE_MARKER_V02
            + "\n"
            + json.dumps(request, separators=(",", ":"))
        )
        comments = [{"id": 17, "body": body}]
        self.assertEqual(
            agent_ownership._find_write_lease_request(comments, request),
            17,
        )

    def test_duplicate_exact_write_lease_requests_fail_closed(self) -> None:
        request = {"requestId": "same"}
        body = (
            hosted_handle_requests.WRITE_LEASE_MARKER_V02
            + "\n"
            + json.dumps(request, separators=(",", ":"))
        )
        comments = [{"id": 17, "body": body}, {"id": 18, "body": body}]
        with self.assertRaisesRegex(
            agent_ownership.AgentOwnershipError,
            "AGENT_OWNERSHIP_REQUEST_DUPLICATE",
        ):
            agent_ownership._find_write_lease_request(comments, request)


if __name__ == "__main__":
    unittest.main()
