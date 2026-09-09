from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import hosted_agent_tool as hosted
from tools import hosted_agent_tool_payload_ref as payload_ref
from tools import hosted_record_vocabulary
from tools.coordination_remote import ApiResponse


class FakeTransport:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, endpoint: str) -> ApiResponse:
        self.calls.append((method, endpoint))
        return ApiResponse(status=200, headers={}, body=json.dumps(self.payload))


def referenced_outer(input_value: dict) -> tuple[dict, bytes]:
    raw = json.dumps(input_value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return (
        {
            "schemaVersion": payload_ref.REQUEST_SCHEMA,
            "requestId": "agent-tool-payload-ref-test",
            "handle": {"opaque": "handle"},
            "toolId": "git.files.mutate",
            "target": {"branch": "work/operations/example"},
            "inputRef": {
                "provider": payload_ref.INPUT_REF_PROVIDER,
                "blobSha": "a" * 40,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "mediaType": payload_ref.INPUT_REF_MEDIA_TYPE,
            },
            "semanticAuthority": False,
            "authorizesMutation": False,
        },
        raw,
    )


def blob_payload(raw: bytes, *, sha: str = "a" * 40) -> dict:
    encoded = base64.b64encode(raw).decode("ascii")
    split = encoded[: max(1, len(encoded) // 2)] + "\n" + encoded[max(1, len(encoded) // 2) :]
    return {"sha": sha, "encoding": "base64", "content": split, "size": len(raw)}


class HostedAgentToolPayloadRefTests(unittest.TestCase):
    @patch("tools.hosted_agent_tool_payload_ref.hosted_agent_tool.validate_handle_request")
    def test_materializes_same_input_into_existing_v02_envelope(self, validate_handle):
        input_value = {
            "changes": [{"path": "docs/example.txt", "content": "payload"}],
            "message": "payload ref",
        }
        outer, raw = referenced_outer(input_value)
        validate_handle.side_effect = lambda value: value
        transport = FakeTransport(blob_payload(raw))

        normalized = payload_ref.normalize_request(outer, transport=transport)

        self.assertEqual(normalized["schemaVersion"], hosted.HANDLE_REQUEST_SCHEMA)
        self.assertEqual(normalized["requestId"], outer["requestId"])
        self.assertEqual(normalized["handle"], outer["handle"])
        self.assertEqual(normalized["toolId"], outer["toolId"])
        self.assertEqual(normalized["target"], outer["target"])
        self.assertEqual(normalized["input"], input_value)
        self.assertNotIn("inputRef", normalized)
        self.assertFalse(normalized["semanticAuthority"])
        self.assertFalse(normalized["authorizesMutation"])
        self.assertEqual(
            transport.calls,
            [("GET", f"repos/{hosted.REPOSITORY}/git/blobs/{'a' * 40}")],
        )

    @patch("tools.hosted_agent_tool_payload_ref.hosted_agent_tool.validate_handle_request")
    def test_hash_mismatch_blocks_before_normalized_request_is_admitted(self, validate_handle):
        outer, raw = referenced_outer({"message": "x"})
        outer["inputRef"]["sha256"] = "0" * 64
        validate_handle.side_effect = lambda value: value
        transport = FakeTransport(blob_payload(raw))

        with self.assertRaisesRegex(RuntimeError, "HOSTED_AGENT_TOOL_INPUT_REF_HASH_MISMATCH"):
            payload_ref.normalize_request(outer, transport=transport)

    @patch("tools.hosted_agent_tool_payload_ref.hosted_agent_tool.validate_handle_request")
    def test_blob_identity_mismatch_is_rejected(self, validate_handle):
        outer, raw = referenced_outer({"message": "x"})
        validate_handle.side_effect = lambda value: value
        transport = FakeTransport(blob_payload(raw, sha="b" * 40))

        with self.assertRaisesRegex(
            RuntimeError, "HOSTED_AGENT_TOOL_INPUT_REF_BLOB_RESPONSE_INVALID"
        ):
            payload_ref.normalize_request(outer, transport=transport)

    @patch("tools.hosted_agent_tool_payload_ref.hosted_agent_tool.validate_handle_request")
    def test_contract_is_closed_and_provider_is_fixed(self, validate_handle):
        outer, _ = referenced_outer({"message": "x"})
        validate_handle.side_effect = lambda value: value

        bad = copy.deepcopy(outer)
        bad["extra"] = True
        with self.assertRaisesRegex(
            RuntimeError, "HOSTED_AGENT_TOOL_INPUT_REF_REQUEST_FIELDS_INVALID"
        ):
            payload_ref.validate_request(bad)

        bad = copy.deepcopy(outer)
        bad["inputRef"]["provider"] = "url"
        with self.assertRaisesRegex(
            RuntimeError, "HOSTED_AGENT_TOOL_INPUT_REF_PROVIDER_UNSUPPORTED"
        ):
            payload_ref.validate_request(bad)

    @patch("tools.hosted_agent_tool_payload_ref.normalize_request")
    def test_v03_event_rewrites_to_existing_v02_marker(self, normalize_request):
        outer, _ = referenced_outer({"message": "x"})
        normalized = {
            "schemaVersion": hosted.HANDLE_REQUEST_SCHEMA,
            "requestId": outer["requestId"],
            "handle": outer["handle"],
            "toolId": outer["toolId"],
            "target": outer["target"],
            "input": {"message": "x"},
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        normalize_request.return_value = normalized
        event = {
            "comment": {
                "body": hosted_record_vocabulary.AGENT_TOOL_REQUEST_V03
                + "\n"
                + json.dumps(outer)
            }
        }

        result = payload_ref.normalize_event(event)

        marker, body = result["comment"]["body"].split("\n", 1)
        self.assertEqual(marker, hosted_record_vocabulary.AGENT_TOOL_REQUEST_V02)
        self.assertEqual(json.loads(body), normalized)
        normalize_request.assert_called_once()

    def test_v01_and_v02_events_are_passthrough(self):
        for marker in (
            hosted_record_vocabulary.AGENT_TOOL_REQUEST_V01,
            hosted_record_vocabulary.AGENT_TOOL_REQUEST_V02,
        ):
            event = {"comment": {"body": marker + "\n{}"}}
            self.assertEqual(payload_ref.normalize_event(event), event)

    def test_cli_normalize_event_writes_passthrough_event(self):
        event = {
            "comment": {
                "body": hosted_record_vocabulary.AGENT_TOOL_REQUEST_V02 + "\n{}"
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            event_path = Path(tmp) / "event.json"
            output_path = Path(tmp) / "normalized.json"
            event_path.write_text(json.dumps(event), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(hosted.__file__).resolve()),
                    "normalize-event",
                    "--event",
                    str(event_path),
                    "--event-out",
                    str(output_path),
                ],
                cwd=payload_ref.ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(output_path.exists())
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), event)

    def test_cli_normalize_event_failure_is_fail_closed_without_result_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_path = Path(tmp) / "missing-event.json"
            output_path = Path(tmp) / "normalized.json"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(hosted.__file__).resolve()),
                    "normalize-event",
                    "--event",
                    str(missing_path),
                    "--event-out",
                    str(output_path),
                ],
                cwd=payload_ref.ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertFalse(output_path.exists())
            failure = json.loads(completed.stdout)
            self.assertEqual(failure["schemaVersion"], hosted.FAILURE_SCHEMA)
            self.assertEqual(failure["status"], "BLOCKED")
            self.assertFalse(failure["semanticAuthority"])
            self.assertFalse(failure["authorizesMutation"])
            self.assertNotIn("AttributeError", completed.stderr)


if __name__ == "__main__":
    unittest.main()
