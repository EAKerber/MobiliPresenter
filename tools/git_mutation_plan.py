"""Read-only semantic planning for direct Git/GitHub mutations.

A GitMutationPlan does not authorize a mutation and never performs one. It binds an
explicit target, observed preconditions, the intended connector action, and the
required readback so an agent can reason about a write before entering apply.
"""
from __future__ import annotations

import copy
import re
from typing import Any

from tools.canonical import stable_hash

SCHEMA_VERSION = "GitMutationPlan 0.1"
REPOSITORY = "EAKerber/MobiliPresenter"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
OPERATIONS = {
    "create-branch",
    "create-file",
    "update-file",
    "delete-file",
    "create-pr",
    "merge-pr",
    "update-ref",
}
RISK_CLASS = {
    "create-branch": "ref-write",
    "create-file": "content-write",
    "update-file": "content-write",
    "delete-file": "content-delete",
    "create-pr": "pr-write",
    "merge-pr": "integration-write",
    "update-ref": "ref-write",
}
CONNECTOR_ACTION = {
    "create-branch": "create_branch",
    "create-file": "create_file",
    "update-file": "update_file",
    "delete-file": "delete_file",
    "create-pr": "create_pull_request",
    "merge-pr": "merge_pull_request",
    "update-ref": "update_ref",
}
PLAN_FIELDS = {
    "schemaVersion",
    "repository",
    "operation",
    "riskClass",
    "target",
    "preconditions",
    "mutation",
    "connectorAction",
    "readback",
    "authorizesMutation",
    "planHash",
}


def _nonempty(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(code)
    return value


def _git_sha(value: Any, code: str) -> str:
    if not isinstance(value, str) or not GIT_SHA_RE.fullmatch(value):
        raise RuntimeError(code)
    return value


def _sha256(value: Any, code: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise RuntimeError(code)
    return value


def _positive_int(value: Any, code: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise RuntimeError(code)
    return value


def _branch(value: Any, *, control_branch: str, allow_control: bool = False) -> str:
    branch = _nonempty(value, "GIT_MUTATION_BRANCH_REQUIRED")
    if not allow_control and branch == control_branch:
        raise RuntimeError("GIT_MUTATION_DIRECT_CONTROL_BRANCH_FORBIDDEN")
    return branch


def _path(value: Any) -> str:
    path = _nonempty(value, "GIT_MUTATION_PATH_REQUIRED")
    if path.startswith("/") or path.endswith("/") or ".." in path.split("/"):
        raise RuntimeError("GIT_MUTATION_PATH_INVALID")
    return path


def _core(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(value) for key, value in plan.items() if key != "planHash"}


def _finish(
    operation: str,
    *,
    target: dict[str, Any],
    preconditions: dict[str, Any],
    mutation: dict[str, Any],
    readback: dict[str, Any],
) -> dict[str, Any]:
    if operation not in OPERATIONS:
        raise RuntimeError("GIT_MUTATION_OPERATION_UNSUPPORTED")
    core = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": REPOSITORY,
        "operation": operation,
        "riskClass": RISK_CLASS[operation],
        "target": copy.deepcopy(target),
        "preconditions": copy.deepcopy(preconditions),
        "mutation": copy.deepcopy(mutation),
        "connectorAction": CONNECTOR_ACTION[operation],
        "readback": copy.deepcopy(readback),
        "authorizesMutation": False,
    }
    return {**core, "planHash": stable_hash(core)}


def create_branch(*, branch: str, base_sha: str, control_branch: str) -> dict[str, Any]:
    branch = _branch(branch, control_branch=control_branch)
    base_sha = _git_sha(base_sha, "GIT_MUTATION_BASE_SHA_INVALID")
    return _finish(
        "create-branch",
        target={"branch": branch},
        preconditions={"branchMustBeAbsent": True, "baseSha": base_sha},
        mutation={"fromSha": base_sha},
        readback={"kind": "branch-head", "branch": branch, "expectedSha": base_sha},
    )


def create_file(*, branch: str, path: str, branch_head: str, content_sha256: str, control_branch: str) -> dict[str, Any]:
    branch = _branch(branch, control_branch=control_branch)
    path = _path(path)
    branch_head = _git_sha(branch_head, "GIT_MUTATION_BRANCH_HEAD_INVALID")
    content_sha256 = _sha256(content_sha256, "GIT_MUTATION_CONTENT_HASH_INVALID")
    return _finish(
        "create-file",
        target={"branch": branch, "path": path},
        preconditions={"branchHead": branch_head, "pathMustBeAbsent": True},
        mutation={"contentSha256": content_sha256},
        readback={"kind": "file-content", "branch": branch, "path": path, "expectedContentSha256": content_sha256, "expectedParentHead": branch_head},
    )


def update_file(*, branch: str, path: str, branch_head: str, blob_sha: str, content_sha256: str, control_branch: str) -> dict[str, Any]:
    branch = _branch(branch, control_branch=control_branch)
    path = _path(path)
    branch_head = _git_sha(branch_head, "GIT_MUTATION_BRANCH_HEAD_INVALID")
    blob_sha = _git_sha(blob_sha, "GIT_MUTATION_BLOB_SHA_INVALID")
    content_sha256 = _sha256(content_sha256, "GIT_MUTATION_CONTENT_HASH_INVALID")
    return _finish(
        "update-file",
        target={"branch": branch, "path": path},
        preconditions={"branchHead": branch_head, "blobSha": blob_sha},
        mutation={"contentSha256": content_sha256},
        readback={"kind": "file-content", "branch": branch, "path": path, "expectedContentSha256": content_sha256, "expectedParentHead": branch_head},
    )


def delete_file(*, branch: str, path: str, branch_head: str, blob_sha: str, control_branch: str) -> dict[str, Any]:
    branch = _branch(branch, control_branch=control_branch)
    path = _path(path)
    branch_head = _git_sha(branch_head, "GIT_MUTATION_BRANCH_HEAD_INVALID")
    blob_sha = _git_sha(blob_sha, "GIT_MUTATION_BLOB_SHA_INVALID")
    return _finish(
        "delete-file",
        target={"branch": branch, "path": path},
        preconditions={"branchHead": branch_head, "blobSha": blob_sha},
        mutation={"delete": True},
        readback={"kind": "file-absent", "branch": branch, "path": path, "expectedParentHead": branch_head},
    )


def create_pr(*, head: str, base: str, head_sha: str, title: str, body_sha256: str, control_branch: str) -> dict[str, Any]:
    head = _branch(head, control_branch=control_branch)
    base = _nonempty(base, "GIT_MUTATION_PR_BASE_REQUIRED")
    head_sha = _git_sha(head_sha, "GIT_MUTATION_PR_HEAD_SHA_INVALID")
    title = _nonempty(title, "GIT_MUTATION_PR_TITLE_REQUIRED")
    body_sha256 = _sha256(body_sha256, "GIT_MUTATION_PR_BODY_HASH_INVALID")
    return _finish(
        "create-pr",
        target={"head": head, "base": base},
        preconditions={"headSha": head_sha, "openPrForHeadMustBeAbsent": True},
        mutation={"title": title, "bodySha256": body_sha256},
        readback={"kind": "open-pr", "head": head, "base": base, "expectedHeadSha": head_sha},
    )


def merge_pr(*, pr_number: int, head_sha: str, merge_method: str = "squash") -> dict[str, Any]:
    pr_number = _positive_int(pr_number, "GIT_MUTATION_PR_NUMBER_INVALID")
    head_sha = _git_sha(head_sha, "GIT_MUTATION_PR_HEAD_SHA_INVALID")
    if merge_method not in {"merge", "squash", "rebase"}:
        raise RuntimeError("GIT_MUTATION_MERGE_METHOD_INVALID")
    return _finish(
        "merge-pr",
        target={"prNumber": pr_number},
        preconditions={"expectedHeadSha": head_sha, "requiredGatesMustBeGreen": True},
        mutation={"mergeMethod": merge_method},
        readback={"kind": "merged-pr", "prNumber": pr_number, "expectedHeadSha": head_sha},
    )


def update_ref(*, branch: str, current_sha: str, new_sha: str, control_branch: str, force: bool = False) -> dict[str, Any]:
    branch = _branch(branch, control_branch=control_branch, allow_control=False)
    current_sha = _git_sha(current_sha, "GIT_MUTATION_CURRENT_REF_SHA_INVALID")
    new_sha = _git_sha(new_sha, "GIT_MUTATION_NEW_REF_SHA_INVALID")
    if force is not False:
        raise RuntimeError("GIT_MUTATION_FORCE_FORBIDDEN")
    return _finish(
        "update-ref",
        target={"branch": branch},
        preconditions={"currentSha": current_sha},
        mutation={"newSha": new_sha, "force": False},
        readback={"kind": "branch-head", "branch": branch, "expectedSha": new_sha},
    )


def validate(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict) or set(plan) != PLAN_FIELDS:
        raise RuntimeError("GIT_MUTATION_PLAN_FIELDS_INVALID")
    if plan.get("schemaVersion") != SCHEMA_VERSION or plan.get("repository") != REPOSITORY:
        raise RuntimeError("GIT_MUTATION_PLAN_CONTRACT_INVALID")
    operation = plan.get("operation")
    if operation not in OPERATIONS or plan.get("riskClass") != RISK_CLASS[operation] or plan.get("connectorAction") != CONNECTOR_ACTION[operation]:
        raise RuntimeError("GIT_MUTATION_PLAN_OPERATION_INVALID")
    if not isinstance(plan.get("target"), dict) or not plan["target"]:
        raise RuntimeError("GIT_MUTATION_TARGET_INVALID")
    if not isinstance(plan.get("preconditions"), dict) or not plan["preconditions"]:
        raise RuntimeError("GIT_MUTATION_PRECONDITIONS_INVALID")
    if not isinstance(plan.get("mutation"), dict) or not plan["mutation"]:
        raise RuntimeError("GIT_MUTATION_PAYLOAD_INVALID")
    if not isinstance(plan.get("readback"), dict) or not plan["readback"]:
        raise RuntimeError("GIT_MUTATION_READBACK_INVALID")
    if plan.get("authorizesMutation") is not False:
        raise RuntimeError("GIT_MUTATION_PLAN_MUST_NOT_AUTHORIZE")
    expected = stable_hash(_core(plan))
    if plan.get("planHash") != expected:
        raise RuntimeError("GIT_MUTATION_PLAN_HASH_MISMATCH")
    return plan
