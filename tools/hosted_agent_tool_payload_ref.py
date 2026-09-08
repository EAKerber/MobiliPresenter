#!/usr/bin/env python3
"""Normalize Hosted Agent Tool 0.3 inputRef transport into the 0.2 handle envelope."""
from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import hosted_agent_tool, hosted_record_vocabulary
from tools.coordination_remote import ApiError, CoordinationRemoteError, GhApiTransport

REPOSITORY = hosted_agent_tool.REPOSITORY
REQUEST_MARKER_V01 = hosted_record_vocabulary.AGENT_TOOL_REQUEST_V01
REQUEST_MARKER_V02 = hosted_record_vocabulary.AGENT_TOOL_REQUEST_V02
REQUEST_MARKER_V03 = hosted_record_vocabulary.AGENT_TOOL_REQUEST_V03
REQUEST_SCHEMA = "HostedAgentToolRequest 0.3"
REQUEST_FIELDS = {
    "schemaVersion", "requestId", "handle", "toolId", "target", "inputRef",
    "semanticAuthority", "authorizesMutation",
}
INPUT_REF_FIELDS = {"provider", "blobSha", "sha256", "mediaType"}
INPUT_REF_PROVIDER = "github-git-blob"
INPUT_REF_MEDIA_TYPE = "application/json"
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _code(exc: BaseException) -> str:
    value = getattr(exc, "code", None)
    if isinstance(value, str) and value:
        return value
    text = str(exc)
    return text.split(":", 1)[0] if text else exc.__class__.__name__


def validate_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != REQUEST_FIELDS:
        raise hosted_agent_tool.HostedAgentToolError(
            "HOSTED_AGENT_TOOL_INPUT_REF_REQUEST_FIELDS_INVALID"
        )
    if value.get("schemaVersion") != REQUEST_SCHEMA:
        raise hosted_agent_tool.HostedAgentToolError(
            "HOSTED_AGENT_TOOL_INPUT_REF_REQUEST_SCHEMA_UNSUPPORTED"
        )

    probe = {
        "schemaVersion": hosted_agent_tool.HANDLE_REQUEST_SCHEMA,
        "requestId": value.get("requestId"),
        "handle": value.get("handle"),
        "toolId": value.get("toolId"),
        "target": copy.deepcopy(value.get("target")),
        "input": {},
        "semanticAuthority": value.get("semanticAuthority"),
        "authorizesMutation": value.get("authorizesMutation"),
    }
    try:
        hosted_agent_tool.validate_handle_request(probe)
    except RuntimeError as exc:
        raise hosted_agent_tool.HostedAgentToolError(_code(exc)) from exc

    ref = value.get("inputRef")
    if not isinstance(ref, dict) or set(ref) != INPUT_REF_FIELDS:
        raise hosted_agent_tool.HostedAgentToolError(
            "HOSTED_AGENT_TOOL_INPUT_REF_FIELDS_INVALID"
        )
    if ref.get("provider") != INPUT_REF_PROVIDER:
        raise hosted_agent_tool.HostedAgentToolError(
            "HOSTED_AGENT_TOOL_INPUT_REF_PROVIDER_UNSUPPORTED"
        )
    if not isinstance(ref.get("blobSha"), str) or GIT_SHA_RE.fullmatch(ref["blobSha"]) is None:
        raise hosted_agent_tool.HostedAgentToolError(
            "HOSTED_AGENT_TOOL_INPUT_REF_BLOB_SHA_INVALID"
        )
    if not isinstance(ref.get("sha256"), str) or SHA256_RE.fullmatch(ref["sha256"]) is None:
        raise hosted_agent_tool.HostedAgentToolError(
            "HOSTED_AGENT_TOOL_INPUT_REF_HASH_INVALID"
        )
    if ref.get("mediaType") != INPUT_REF_MEDIA_TYPE:
        raise hosted_agent_tool.HostedAgentToolError(
            "HOSTED_AGENT_TOOL_INPUT_REF_MEDIA_TYPE_UNSUPPORTED"
        )
    return value


def materialize_input(
    outer: dict[str, Any],
    *,
    transport: Any | None = None,
) -> dict[str, Any]:
    outer = validate_request(outer)
    ref = outer["inputRef"]
    carrier = transport or GhApiTransport()
    endpoint = f"repos/{REPOSITORY}/git/blobs/{ref['blobSha']}"
    try:
        response = carrier.request("GET", endpoint)
    except (ApiError, CoordinationRemoteError) as exc:
        raise hosted_agent_tool.HostedAgentToolError(
            "HOSTED_AGENT_TOOL_INPUT_REF_UNAVAILABLE", str(exc)
        ) from exc

    try:
        payload = json.loads(response.body)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise hosted_agent_tool.HostedAgentToolError(
            "HOSTED_AGENT_TOOL_INPUT_REF_BLOB_RESPONSE_INVALID"
        ) from exc
    if (
        not isinstance(payload, dict)
        or payload.get("sha") != ref["blobSha"]
        or payload.get("encoding") != "base64"
        or not isinstance(payload.get("content"), str)
    ):
        raise hosted_agent_tool.HostedAgentToolError(
            "HOSTED_AGENT_TOOL_INPUT_REF_BLOB_RESPONSE_INVALID"
        )

    try:
        raw = base64.b64decode("".join(payload["content"].split()), validate=True)
    except (binascii.Error, ValueError, TypeError) as exc:
        raise hosted_agent_tool.HostedAgentToolError(
            "HOSTED_AGENT_TOOL_INPUT_REF_BLOB_RESPONSE_INVALID"
        ) from exc
    size = payload.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size != len(raw):
        raise hosted_agent_tool.HostedAgentToolError(
            "HOSTED_AGENT_TOOL_INPUT_REF_BLOB_RESPONSE_INVALID"
        )
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise hosted_agent_tool.HostedAgentToolError(
            "HOSTED_AGENT_TOOL_INPUT_REF_HASH_MISMATCH"
        )
    try:
        input_value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise hosted_agent_tool.HostedAgentToolError(
            "HOSTED_AGENT_TOOL_INPUT_REF_CONTENT_INVALID"
        ) from exc
    if not isinstance(input_value, dict):
        raise hosted_agent_tool.HostedAgentToolError(
            "HOSTED_AGENT_TOOL_INPUT_REF_CONTENT_INVALID"
        )
    return input_value


def normalize_request(
    outer: dict[str, Any],
    *,
    transport: Any | None = None,
) -> dict[str, Any]:
    outer = validate_request(outer)
    normalized = {
        "schemaVersion": hosted_agent_tool.HANDLE_REQUEST_SCHEMA,
        "requestId": outer["requestId"],
        "handle": copy.deepcopy(outer["handle"]),
        "toolId": outer["toolId"],
        "target": copy.deepcopy(outer["target"]),
        "input": materialize_input(outer, transport=transport),
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return hosted_agent_tool.validate_handle_request(normalized)


def normalize_event(
    event: Any,
    *,
    transport: Any | None = None,
) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise hosted_agent_tool.HostedAgentToolError("HOSTED_AGENT_TOOL_EVENT_INVALID")
    comment = event.get("comment")
    body = comment.get("body") if isinstance(comment, dict) else None
    if not isinstance(body, str):
        raise hosted_agent_tool.HostedAgentToolError("HOSTED_AGENT_TOOL_MARKER_INVALID")
    if body.startswith(REQUEST_MARKER_V01 + "\n") or body.startswith(REQUEST_MARKER_V02 + "\n"):
        return copy.deepcopy(event)
    if not body.startswith(REQUEST_MARKER_V03 + "\n"):
        raise hosted_agent_tool.HostedAgentToolError("HOSTED_AGENT_TOOL_MARKER_INVALID")

    try:
        outer = json.loads(body[len(REQUEST_MARKER_V03) + 1:].strip())
    except json.JSONDecodeError as exc:
        raise hosted_agent_tool.HostedAgentToolError("HOSTED_AGENT_TOOL_JSON_INVALID") from exc
    normalized = normalize_request(outer, transport=transport)
    result = copy.deepcopy(event)
    result["comment"]["body"] = (
        REQUEST_MARKER_V02
        + "\n"
        + json.dumps(normalized, separators=(",", ":"), ensure_ascii=False)
    )
    return result


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="hosted-agent-tool-payload-ref")
    parser.add_argument("command", choices=["normalize-event"])
    parser.add_argument("--event", required=True)
    parser.add_argument("--event-out", required=True)
    args = parser.parse_args(argv)

    try:
        event = json.loads(Path(args.event).read_text(encoding="utf-8"))
        normalized = normalize_event(event)
        Path(args.event_out).write_text(
            json.dumps(normalized, separators=(",", ":"), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
