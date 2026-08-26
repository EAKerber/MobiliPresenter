from __future__ import annotations

from typing import Any


def _path(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError("AGENT_TOOL_GIT_PATH_INVALID")
    if value.startswith("/") or value.endswith("/") or "\\" in value:
        raise RuntimeError("AGENT_TOOL_GIT_PATH_INVALID")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise RuntimeError("AGENT_TOOL_GIT_PATH_INVALID")
    return value


def change_paths(input_value: Any) -> list[str]:
    if not isinstance(input_value, dict) or set(input_value) != {"changes", "message"}:
        raise RuntimeError("AGENT_TOOL_GIT_INPUT_INVALID")
    if not isinstance(input_value.get("message"), str) or not input_value["message"].strip():
        raise RuntimeError("AGENT_TOOL_GIT_INPUT_INVALID")
    changes = input_value.get("changes")
    if not isinstance(changes, list) or not changes:
        raise RuntimeError("AGENT_TOOL_GIT_CHANGES_REQUIRED")
    paths: list[str] = []
    for change in changes:
        if not isinstance(change, dict):
            raise RuntimeError("AGENT_TOOL_GIT_CHANGE_INVALID")
        path = _path(change.get("path"))
        if set(change) == {"path", "content"}:
            if not isinstance(change.get("content"), str):
                raise RuntimeError("AGENT_TOOL_GIT_CHANGE_INVALID")
        elif set(change) == {"path", "delete"}:
            if change.get("delete") is not True:
                raise RuntimeError("AGENT_TOOL_GIT_CHANGE_INVALID")
        else:
            raise RuntimeError("AGENT_TOOL_GIT_CHANGE_INVALID")
        paths.append(path)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise RuntimeError("AGENT_TOOL_GIT_CHANGES_NOT_CANONICAL")
    return paths


def validate_target(
    policy: dict[str, Any], target: dict[str, Any], input_value: dict[str, Any] | None = None
) -> dict[str, Any]:
    kind = policy.get("kind")
    if kind == "none":
        if target:
            raise RuntimeError("AGENT_TOOL_TARGET_MUST_BE_EMPTY")
        return target
    if kind != "git-files":
        raise RuntimeError("AGENT_TOOL_TARGET_POLICY_KIND_UNSUPPORTED")
    if not isinstance(target, dict) or set(target) != {"branch"}:
        raise RuntimeError("AGENT_TOOL_GIT_TARGET_INVALID")
    branch = target.get("branch")
    if not isinstance(branch, str) or not branch:
        raise RuntimeError("AGENT_TOOL_GIT_TARGET_INVALID")
    if branch in set(policy.get("forbiddenBranches") or []):
        raise RuntimeError("AGENT_TOOL_TARGET_BRANCH_FORBIDDEN")
    branch_prefixes = policy.get("branchPrefixes") or []
    if branch_prefixes and not any(branch.startswith(prefix) and len(branch) > len(prefix) for prefix in branch_prefixes):
        raise RuntimeError("AGENT_TOOL_TARGET_BRANCH_FORBIDDEN")
    paths = change_paths(input_value)
    path_prefixes = policy.get("pathPrefixes") or []
    if path_prefixes and any(
        not any(path.startswith(prefix) and len(path) > len(prefix) for prefix in path_prefixes)
        for path in paths
    ):
        raise RuntimeError("AGENT_TOOL_TARGET_PATH_FORBIDDEN")
    return target
