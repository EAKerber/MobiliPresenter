from __future__ import annotations

import copy
from typing import Any

from tools import git_observation
from tools import remote_canonical_execution as remote
from tools.agent_tools.contracts import request_hash

TOOL_TO_OPERATION = {
    "git.file.create": "create-file",
    "git.file.update": "update-file",
    "git.file.delete": "delete-file",
}


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
    observed = git_observation.observe_file(branch, path, transport=transport)
    head = observed["branchHead"]
    blob = observed["blobSha"]
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
