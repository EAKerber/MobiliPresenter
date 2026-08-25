from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote

from tools import coordination
from tools.coordination_remote import ApiError, GhApiTransport

REPOSITORY = "EAKerber/MobiliPresenter"
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")


class GitObservationError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _sha(value: Any, code: str) -> str:
    if not isinstance(value, str) or not GIT_SHA_RE.fullmatch(value):
        raise GitObservationError(code)
    return value


def _json(response: Any, code: str) -> dict[str, Any]:
    try:
        value = json.loads(response.body)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise GitObservationError(code) from exc
    if not isinstance(value, dict):
        raise GitObservationError(code)
    return value


def canonical_branch(branch: str) -> str:
    return coordination.normalize_resource(f"branch:{branch}").split(":", 1)[1]


def canonical_path(path: str) -> str:
    return coordination.normalize_resource(f"file:{path}").split(":", 1)[1]


def ref_head(transport: Any, branch: str, *, missing_ok: bool = False) -> str | None:
    branch = canonical_branch(branch)
    endpoint = f"repos/{REPOSITORY}/git/ref/heads/{quote(branch, safe='')}"
    try:
        payload = _json(transport.request("GET", endpoint), "GIT_OBSERVATION_REF_INVALID")
    except ApiError as exc:
        if missing_ok and exc.status == 404:
            return None
        raise GitObservationError("GIT_OBSERVATION_REF_UNAVAILABLE", exc.detail) from exc
    return _sha((payload.get("object") or {}).get("sha"), "GIT_OBSERVATION_REF_INVALID")


def commit_info(transport: Any, sha: str) -> dict[str, Any]:
    sha = _sha(sha, "GIT_OBSERVATION_COMMIT_SHA_INVALID")
    try:
        payload = _json(
            transport.request("GET", f"repos/{REPOSITORY}/git/commits/{sha}"),
            "GIT_OBSERVATION_COMMIT_INVALID",
        )
    except ApiError as exc:
        raise GitObservationError("GIT_OBSERVATION_COMMIT_UNAVAILABLE", exc.detail) from exc
    tree_sha = _sha((payload.get("tree") or {}).get("sha"), "GIT_OBSERVATION_TREE_SHA_INVALID")
    parents_raw = payload.get("parents")
    if not isinstance(parents_raw, list):
        raise GitObservationError("GIT_OBSERVATION_COMMIT_INVALID")
    parents = [
        _sha((parent or {}).get("sha"), "GIT_OBSERVATION_PARENT_SHA_INVALID")
        for parent in parents_raw
    ]
    return {"sha": sha, "treeSha": tree_sha, "parents": parents}


def tree_entries(transport: Any, tree_sha: str) -> list[dict[str, Any]]:
    tree_sha = _sha(tree_sha, "GIT_OBSERVATION_TREE_SHA_INVALID")
    try:
        payload = _json(
            transport.request("GET", f"repos/{REPOSITORY}/git/trees/{tree_sha}?recursive=1"),
            "GIT_OBSERVATION_TREE_INVALID",
        )
    except ApiError as exc:
        raise GitObservationError("GIT_OBSERVATION_TREE_UNAVAILABLE", exc.detail) from exc
    if payload.get("truncated") is True:
        raise GitObservationError("GIT_OBSERVATION_TREE_TRUNCATED")
    raw = payload.get("tree")
    if not isinstance(raw, list):
        raise GitObservationError("GIT_OBSERVATION_TREE_INVALID")
    result: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise GitObservationError("GIT_OBSERVATION_TREE_INVALID")
        path = item.get("path")
        kind = item.get("type")
        sha = item.get("sha")
        if isinstance(path, str) and isinstance(kind, str) and isinstance(sha, str):
            result.append({"path": path, "type": kind, "sha": sha})
    return result


def blob_at(entries: list[dict[str, Any]], path: str) -> str | None:
    path = canonical_path(path)
    found = [
        item["sha"]
        for item in entries
        if item.get("type") == "blob" and item.get("path") == path
    ]
    if len(found) > 1:
        raise GitObservationError("GIT_OBSERVATION_TREE_DUPLICATE_PATH")
    if not found:
        return None
    return _sha(found[0], "GIT_OBSERVATION_BLOB_SHA_INVALID")


def observe_branch(branch: str, *, transport: Any | None = None) -> dict[str, Any]:
    carrier = transport or GhApiTransport()
    canonical = canonical_branch(branch)
    return {
        "repository": REPOSITORY,
        "branch": canonical,
        "branchHead": ref_head(carrier, canonical),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def observe_file(
    branch: str,
    path: str,
    *,
    transport: Any | None = None,
) -> dict[str, Any]:
    carrier = transport or GhApiTransport()
    canonical_branch_value = canonical_branch(branch)
    canonical_path_value = canonical_path(path)
    head = ref_head(carrier, canonical_branch_value)
    if not isinstance(head, str):
        raise GitObservationError("GIT_OBSERVATION_BRANCH_UNAVAILABLE")
    commit = commit_info(carrier, head)
    entries = tree_entries(carrier, commit["treeSha"])
    return {
        "repository": REPOSITORY,
        "branch": canonical_branch_value,
        "path": canonical_path_value,
        "branchHead": head,
        "blobSha": blob_at(entries, canonical_path_value),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
