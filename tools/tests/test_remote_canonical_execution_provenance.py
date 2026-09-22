from __future__ import annotations

import unittest

from tools import remote_canonical_execution as bridge


class RemoteCanonicalProvenanceTests(unittest.TestCase):
    def test_hosted_source_is_canonical_and_round_trips_binding(self):
        source = bridge.build_hosted_comment_source(
            host="agent-tool-mutation-dispatch",
            source_sha="a" * 40,
            invocation_id="123",
            issue_number=145,
            comment_id=321,
        )
        self.assertEqual(
            source,
            {
                "kind": "hosted-comment",
                "host": "agent-tool-mutation-dispatch",
                "sourceSha": "a" * 40,
                "invocationId": "123",
                "ref": {"kind": "issue-comment", "value": "145:321"},
            },
        )
        self.assertEqual(
            bridge.hosted_comment_source_binding(source),
            {
                "host": "agent-tool-mutation-dispatch",
                "sourceSha": "a" * 40,
                "invocationId": "123",
                "issueNumber": 145,
                "commentId": 321,
            },
        )

    def test_legacy_hosted_source_still_normalizes(self):
        source = {
            "workflow": "remote-canonical-execution",
            "sourceSha": "a" * 40,
            "runId": "456",
            "issueNumber": 145,
            "commentId": 20,
        }
        self.assertEqual(
            bridge.hosted_comment_source_binding(source),
            {
                "host": "remote-canonical-execution",
                "sourceSha": "a" * 40,
                "invocationId": "456",
                "issueNumber": 145,
                "commentId": 20,
            },
        )

    def test_direct_host_source_is_portable_and_not_hosted_binding(self):
        source = bridge.build_execution_source(
            kind="agent-tool-host",
            host="agent-tool-mutation-host",
            source_sha="b" * 40,
            invocation_id="direct-1",
            ref={"kind": "agent-tool-request", "value": "c" * 64},
        )
        self.assertIsNone(bridge.hosted_comment_source_binding(source))
        self.assertNotIn("issueNumber", source)
        self.assertNotIn("commentId", source)

    def test_unknown_kind_and_malformed_refs_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, "SOURCE_KIND_INVALID"):
            bridge.build_execution_source(
                kind="other",
                host="host",
                source_sha="a" * 40,
                invocation_id="1",
                ref={"kind": "x", "value": "y"},
            )
        with self.assertRaisesRegex(RuntimeError, "SOURCE_REF_INVALID"):
            bridge.build_execution_source(
                kind="hosted-comment",
                host="host",
                source_sha="a" * 40,
                invocation_id="1",
                ref={"kind": "issue-comment", "value": "145:not-a-comment"},
            )
        with self.assertRaisesRegex(RuntimeError, "SOURCE_REF_INVALID"):
            bridge.build_execution_source(
                kind="agent-tool-host",
                host="host",
                source_sha="a" * 40,
                invocation_id="1",
                ref={"kind": "agent-tool-request", "value": "short"},
            )


if __name__ == "__main__":
    unittest.main()
