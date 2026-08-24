from __future__ import annotations

from typing import Any


def validate_target(policy: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    kind = policy.get("kind")
    if kind == "none":
        if target:
            raise RuntimeError("AGENT_TOOL_TARGET_MUST_BE_EMPTY")
        return target
    if kind != "git-file":
        raise RuntimeError("AGENT_TOOL_TARGET_POLICY_KIND_UNSUPPORTED")
    if not isinstance(target, dict) or set(target) != {"branch", "path"}:
        raise RuntimeError("AGENT_TOOL_GIT_TARGET_INVALID")
    branch = target.get("branch")
    path = target.get("path")
    if not isinstance(branch, str) or not branch or not isinstance(path, str) or not path:
        raise RuntimeError("AGENT_TOOL_GIT_TARGET_INVALID")
    if branch in set(policy.get("forbiddenBranches") or []):
        raise RuntimeError("AGENT_TOOL_TARGET_BRANCH_FORBIDDEN")
    branch_prefixes = policy.get("branchPrefixes") or []
    if branch_prefixes and not any(branch.startswith(prefix) and len(branch) > len(prefix) for prefix in branch_prefixes):
        raise RuntimeError("AGENT_TOOL_TARGET_BRANCH_FORBIDDEN")
    path_prefixes = policy.get("pathPrefixes") or []
    if path_prefixes and not any(path.startswith(prefix) and len(path) > len(prefix) for prefix in path_prefixes):
        raise RuntimeError("AGENT_TOOL_TARGET_PATH_FORBIDDEN")
    if path.startswith("/") or path.endswith("/") or "\\" in path or any(part in {"", ".", ".."} for part in path.split("/")):
        raise RuntimeError("AGENT_TOOL_TARGET_PATH_INVALID")
    return target
