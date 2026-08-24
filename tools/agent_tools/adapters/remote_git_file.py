from __future__ import annotations

import copy
from typing import Any

from tools import remote_canonical_execution as remote
from tools.agent_tools.contracts import request_hash
from tools.coordination_remote import GhApiTransport

TOOL_TO_OPERATION = {
    "git.file.create": "create-file",
    "git.file.update": "update-file",
    "git.file.delete": "delete-file",
}


def _observe_blob(transport: Any, branch: str, path: str) -> tuple[str, str | None]:
    head = remote._ref_head(transport, branch)
    if not isinstance(head, str):
        raise RuntimeError("AGENT_TOOL_GIT_BRANCH_UNAVAILABLE")
    commit = remote._commit(transport, head)
    entries = remote._tree_entries(transport, commit["treeSha"])
    return head, remote._blob_at(entries, path)


def build_concrete(
    request: dict[str, Any],
    context: dict[str, Any],
    *,
    transport: Any | None = None,
    **_: Any,
) -> dict[str, Any]:
    tool_id = request["toolId"]
    operation = TOOL_TO_OPERATION.get(tool_id)
    if operation is None:
        raise RuntimeError("AGENT_TOOL_GIT_OPERATION_UNSUPPORTED")
    target = request["target"]
    branch = target["branch"]
    path = target["path"]
    carrier = transport or GhApiTransport()
    head, blob = _observe_blob(carrier, branch, path)
    input_value = request["input"]
    if operation in {"create-file", "update-file"}:
        if set(input_value) != {"content", "message"}:
            raise RuntimeError("AGENT_TOOL_GIT_INPUT_INVALID")
        if not isinstance(input_value.get("content"), str) or not isinstance(input_value.get("message"), str) or not input_value["message"].strip():
            raise RuntimeError("AGENT_TOOL_GIT_INPUT_INVALID")
    else:
        if set(input_value) != {"message"} or not isinstance(input_value.get("message"), str) or not input_value["message"].strip():
            raise RuntimeError("AGENT_TOOL_GIT_INPUT_INVALID")
    if operation == "create-file" and blob is not None:
        raise RuntimeError("AGENT_TOOL_GIT_CREATE_TARGET_EXISTS")
    if operation in {"update-file", "delete-file"} and blob is None:
        raise RuntimeError("AGENT_TOOL_GIT_TARGET_MISSING")
    expected: dict[str, Any] = {"branchHead": head}
    if blob is not None and operation != "create-file":
        expected["blobSha"] = blob
    payload = (
        {"content": input_value["content"], "message": input_value["message"].strip()}
        if operation in {"create-file", "update-file"}
        else {"message": input_value["message"].strip()}
    )
    command = {
        "schemaVersion": remote.COMMAND_SCHEMA,
        "executionId": "agent-tool-" + request_hash(request)[:24],
        "kind": "git-direct",
        "actor": copy.deepcopy(request["actor"]),
        "declaredIntent": {
            "goal": f"agent-tool:{tool_id}",
            "agentToolRequestId": request["requestId"],
        },
        "target": {
            "operation": operation,
            "branch": branch,
            "path": path,
        },
        "expected": expected,
        "payload": payload,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    remote.validate_command(command)
    return {
        "kind": "remote-canonical-command",
        "command": command,
        "commandHash": remote.command_hash(command),
        "mutationEnabled": False,
    }


def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
    raise RuntimeError("AGENT_TOOL_MUTATION_EXECUTION_NOT_ADMITTED")
