from __future__ import annotations

import copy
from typing import Any

from tools import git_observation
from tools import remote_canonical_execution as remote
from tools.agent_tools.contracts import request_hash
from tools.agent_tools.target_policy import change_paths


def build_concrete(
    request: dict[str, Any],
    context: dict[str, Any],
    *,
    transport: Any | None = None,
    **_: Any,
) -> dict[str, Any]:
    if request["toolId"] != "git.files.mutate":
        raise RuntimeError("AGENT_TOOL_GIT_OPERATION_UNSUPPORTED")
    target = request["target"]
    branch = target["branch"]
    input_value = request["input"]
    change_paths(input_value)
    observed = git_observation.observe_branch(branch, transport=transport)
    command = {
        "schemaVersion": remote.COMMAND_SCHEMA,
        "executionId": "agent-tool-" + request_hash(request)[:24],
        "kind": "git-direct",
        "actor": copy.deepcopy(request["actor"]),
        "declaredIntent": {
            "goal": "agent-tool:git.files.mutate",
            "agentToolRequestId": request["requestId"],
        },
        "target": {
            "operation": "mutate-files",
            "branch": branch,
        },
        "expected": {"branchHead": observed["branchHead"]},
        "payload": {
            "changes": copy.deepcopy(input_value["changes"]),
            "message": input_value["message"].strip(),
        },
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
