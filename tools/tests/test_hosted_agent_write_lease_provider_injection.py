from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import hosted_agent_write_lease


class HostedAgentWriteLeaseProviderInjectionTests(unittest.TestCase):
    def test_prepare_cli_injects_explicit_github_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            begin = root / "begin"
            begin.mkdir()
            request_path = root / "request.json"
            meta_path = root / "meta.json"
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
            expected_dispatch = {"schemaVersion": "test-dispatch"}

            with (
                mock.patch.object(
                    hosted_agent_write_lease,
                    "GhApiTransport",
                    return_value=carrier,
                ) as transport_cls,
                mock.patch.object(
                    hosted_agent_write_lease,
                    "prepare",
                    return_value=expected_dispatch,
                ) as prepare,
            ):
                rc = hosted_agent_write_lease.main(
                    [
                        "prepare",
                        "--request",
                        str(request_path),
                        "--meta",
                        str(meta_path),
                        "--begin-dir",
                        str(begin),
                        "--dispatch",
                        str(dispatch_path),
                    ]
                )

            self.assertEqual(rc, 0)
            transport_cls.assert_called_once_with()
            self.assertIs(
                prepare.call_args.kwargs["transport"],
                carrier,
            )
            self.assertEqual(
                json.loads(dispatch_path.read_text(encoding="utf-8")),
                expected_dispatch,
            )


if __name__ == "__main__":
    unittest.main()
