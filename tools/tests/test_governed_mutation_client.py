from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools import governed_mutation_client as client
from tools import governed_mutation_service as service


WORK_ID = "e5-governed-mutation-request-client"
BRANCH = "work/operations/e5-governed-mutation-request-client"


class GovernedMutationClientTests(unittest.TestCase):
    def test_four_semantic_inputs_render_existing_service_contract(self):
        request = client.build_request(
            work_id=WORK_ID,
            branch=BRANCH,
            changes=[
                {"path": "tools/z.py", "content": "z\n"},
                {"path": "tools/a.py", "content": "a\n"},
            ],
            message="E5 client test",
        )
        self.assertEqual(request["schemaVersion"], service.REQUEST_SCHEMA)
        self.assertEqual(
            [item["path"] for item in request["changes"]],
            ["tools/a.py", "tools/z.py"],
        )
        self.assertFalse(request["semanticAuthority"])
        self.assertFalse(request["authorizesMutation"])
        self.assertEqual(request, service.validate_request(request))

    def test_comment_is_exact_existing_e4_marker_plus_canonical_json(self):
        request = client.build_request(
            work_id=WORK_ID,
            branch=BRANCH,
            changes=[{"path": "tools/a.py", "content": "a\n"}],
            message="E5 client test",
        )
        body = client.render_comment(request)
        marker, raw = body.split("\n", 1)
        self.assertEqual(marker, service.REQUEST_MARKER)
        self.assertEqual(json.loads(raw), request)
        self.assertNotIn("cycleInstanceId", raw)
        self.assertNotIn("leaseId", raw)
        self.assertNotIn("proofSet", raw)

    def test_duplicate_paths_fail_through_existing_service_validation(self):
        with self.assertRaisesRegex(RuntimeError, "CHANGES_NOT_CANONICAL"):
            client.build_request(
                work_id=WORK_ID,
                branch=BRANCH,
                changes=[
                    {"path": "tools/a.py", "content": "a\n"},
                    {"path": "tools/a.py", "content": "b\n"},
                ],
                message="duplicate",
            )

    def test_cli_reads_changes_file_and_outputs_only_comment_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "changes.json"
            path.write_text(
                json.dumps([{"path": "tools/a.py", "content": "a\n"}]),
                encoding="utf-8",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = client.main([
                    "--work-id", WORK_ID,
                    "--branch", BRANCH,
                    "--changes-file", str(path),
                    "--message", "E5 client test",
                ])
        self.assertEqual(code, 0)
        self.assertTrue(output.getvalue().startswith(service.REQUEST_MARKER + "\n"))

    def test_client_has_no_transport_or_authority_writer(self):
        source = Path(client.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "GhApiTransport",
            "post_comment(",
            "GitHubContinuationAuthority",
            "GitHubCoordinationAuthority",
            "mutation_host.execute_plan",
            "create_commit(",
            "update_ref(",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
