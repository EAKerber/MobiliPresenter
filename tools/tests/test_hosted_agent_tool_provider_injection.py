from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import hosted_agent_tool


class HostedAgentToolProviderInjectionTests(unittest.TestCase):
    def test_execute_cli_injects_explicit_github_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            begin = root / "begin"
            begin.mkdir()
            request_path = root / "request.json"
            meta_path = root / "meta.json"
            result_path = root / "result.json"
            plan_path = root / "plan.json"
            proof_path = root / "proof.json"
            dispatch_path = root / "dispatch.json"

            request_path.write_text(
                json.dumps({"schemaVersion": "test-request"}) + "\n",
                encoding="utf-8",
            )
            meta_path.write_text(
                json.dumps({"issueNumber": 145, "commentId": 123}) + "\n",
                encoding="utf-8",
            )
            (begin / "manifest.json").write_text(
                json.dumps({"schemaVersion": "test-manifest"}) + "\n",
                encoding="utf-8",
            )
            (begin / "context.json").write_text(
                json.dumps({"schemaVersion": "test-context"}) + "\n",
                encoding="utf-8",
            )

            carrier = object()
            expected = {
                "kind": "terminal",
                "plan": {"schemaVersion": "test-plan"},
                "result": {
                    "schemaVersion": "HostedAgentToolResult 0.1",
                    "status": "PASS",
                },
            }

            with (
                mock.patch.object(
                    hosted_agent_tool,
                    "GhApiTransport",
                    return_value=carrier,
                ) as transport_cls,
                mock.patch.object(
                    hosted_agent_tool,
                    "prepare_request",
                    return_value=expected,
                ) as prepare,
            ):
                rc = hosted_agent_tool.main(
                    [
                        "execute",
                        "--request",
                        str(request_path),
                        "--meta",
                        str(meta_path),
                        "--begin-dir",
                        str(begin),
                        "--result",
                        str(result_path),
                        "--plan",
                        str(plan_path),
                        "--proof-set",
                        str(proof_path),
                        "--dispatch",
                        str(dispatch_path),
                    ]
                )

            self.assertEqual(rc, 0)
            transport_cls.assert_called_once_with()
            self.assertIs(prepare.call_args.kwargs["transport"], carrier)
            self.assertEqual(
                json.loads(result_path.read_text(encoding="utf-8")),
                expected["result"],
            )

    def test_prepare_request_does_not_construct_hidden_provider(self) -> None:
        source = inspect.getsource(hosted_agent_tool.prepare_request)
        self.assertNotIn("GhApiTransport(", source)


if __name__ == "__main__":
    unittest.main()
