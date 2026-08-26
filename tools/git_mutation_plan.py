"""Read-only semantic planning for direct Git/GitHub mutations.

A GitMutationPlan does not authorize a mutation and never performs one. It binds an
explicit target, observed preconditions, the intended connector action, and the
required readback so an agent can reason about a write before entering apply.
"""
from __future__ import annotations

import copy
import hashlib
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
    "mutate-files",
    "create-pr",
    "merge-pr",
    "update-ref",
}
RISK_CLASS = {
    "create-branch": "ref-write",
    "create-file": "content-write",
    "update-file": "content-write",
    "delete-file": "content-delete",
    "mutate-files": "content-mutation",
    "create-pr": "pr-write",
    "merge-pr": "integration-write",
    "update-ref": "ref-write",
}
CONNECTOR_ACTION = {
    "create-branch": "create_branch",
    "create-file": "create_file",
    "update-file": "update_file",
    "delete-file": "delete_file",
    "mutate-files": "create_tree_commit_update_ref",
    "create-pr": "create_pull_request",
    "merge-pr": "merge_pull_request",
    "update-ref": "update_ref",
}
PLAN_FIELDS = {
    "schemaVersion",
    "repository",
    "controlBranch",
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


def _exact(value: Any, keys: set[str], code: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise RuntimeError(code)
    return value


def _core(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(value) for key, value in plan.items() if key != "planHash"}


def _finish(
    operation: str,
    *,
    control_branch: str,
    target: dict[str, Any],
    preconditions: dict[str, Any],
    mutation: dict[str, Any],
    readback: dict[str, Any],
) -> dict[str, Any]:
    if operation not in OPERATIONS:
        raise RuntimeError("GIT_MUTATION_OPERATION_UNSUPPORTED")
    control_branch = _nonempty(control_branch, "GIT_MUTATION_CONTROL_BRANCH_REQUIRED")
    core = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": REPOSITORY,
        "controlBranch": control_branch,
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
        "create-branch", control_branch=control_branch,
        target={"branch": branch},
        preconditions={"branchMustBeAbsent": True, "baseSha": base_sha},
        mutation={"fromSha": base_sha},
        readback={"kind": "branch-head", "branch": branch, "expectedSha": base_sha},
    )


def create_file(*, branch: str, path: str, branch_head: str, content_sha256: str, control_branch: str) -> dict[str, Any]:
    branch = _branch(branch, control_branch=control_branch);path = _path(path)
    branch_head = _git_sha(branch_head, "GIT_MUTATION_BRANCH_HEAD_INVALID");content_sha256 = _sha256(content_sha256, "GIT_MUTATION_CONTENT_HASH_INVALID")
    return _finish(
        "create-file", control_branch=control_branch,
        target={"branch": branch, "path": path},
        preconditions={"branchHead": branch_head, "pathMustBeAbsent": True},
        mutation={"contentSha256": content_sha256},
        readback={"kind": "file-content", "branch": branch, "path": path, "expectedContentSha256": content_sha256, "expectedParentHead": branch_head},
    )


def update_file(*, branch: str, path: str, branch_head: str, blob_sha: str, content_sha256: str, control_branch: str) -> dict[str, Any]:
    branch = _branch(branch, control_branch=control_branch);path = _path(path)
    branch_head = _git_sha(branch_head, "GIT_MUTATION_BRANCH_HEAD_INVALID");blob_sha = _git_sha(blob_sha, "GIT_MUTATION_BLOB_SHA_INVALID");content_sha256 = _sha256(content_sha256, "GIT_MUTATION_CONTENT_HASH_INVALID")
    return _finish(
        "update-file", control_branch=control_branch,
        target={"branch": branch, "path": path},
        preconditions={"branchHead": branch_head, "blobSha": blob_sha},
        mutation={"contentSha256": content_sha256},
        readback={"kind": "file-content", "branch": branch, "path": path, "expectedContentSha256": content_sha256, "expectedParentHead": branch_head},
    )


def delete_file(*, branch: str, path: str, branch_head: str, blob_sha: str, control_branch: str) -> dict[str, Any]:
    branch = _branch(branch, control_branch=control_branch);path = _path(path)
    branch_head = _git_sha(branch_head, "GIT_MUTATION_BRANCH_HEAD_INVALID");blob_sha = _git_sha(blob_sha, "GIT_MUTATION_BLOB_SHA_INVALID")
    return _finish(
        "delete-file", control_branch=control_branch,
        target={"branch": branch, "path": path},
        preconditions={"branchHead": branch_head, "blobSha": blob_sha},
        mutation={"delete": True},
        readback={"kind": "file-absent", "branch": branch, "path": path, "expectedParentHead": branch_head},
    )


def mutate_files(
    *,
    branch: str,
    branch_head: str,
    changes: list[dict[str, Any]],
    control_branch: str,
) -> dict[str, Any]:
    branch = _branch(branch, control_branch=control_branch)
    branch_head = _git_sha(branch_head, "GIT_MUTATION_BRANCH_HEAD_INVALID")
    if not isinstance(changes, list) or not changes:
        raise RuntimeError("GIT_MUTATION_CHANGES_REQUIRED")
    entries: list[dict[str, Any]] = []
    for change in changes:
        if not isinstance(change, dict):
            raise RuntimeError("GIT_MUTATION_CHANGE_INVALID")
        path = _path(change.get("path"))
        if set(change) == {"path", "content"} and isinstance(change.get("content"), str):
            digest = hashlib.sha256(change["content"].encode("utf-8")).hexdigest()
            entries.append({"path": path, "operation": "write", "contentSha256": digest})
        elif set(change) == {"path", "delete"} and change.get("delete") is True:
            entries.append({"path": path, "operation": "delete", "contentSha256": None})
        else:
            raise RuntimeError("GIT_MUTATION_CHANGE_INVALID")
    paths = [entry["path"] for entry in entries]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise RuntimeError("GIT_MUTATION_CHANGES_NOT_CANONICAL")
    content_hashes = {
        entry["path"]: entry["contentSha256"]
        for entry in entries
        if entry["operation"] == "write"
    }
    return _finish(
        "mutate-files",
        control_branch=control_branch,
        target={"branch": branch},
        preconditions={"branchHead": branch_head},
        mutation={"entries": entries},
        readback={
            "kind": "git-bundle",
            "branch": branch,
            "expectedParentHead": branch_head,
            "expectedChangedPaths": paths,
            "expectedContentSha256": content_hashes,
        },
    )


def create_pr(*, head: str, base: str, head_sha: str, title: str, body_sha256: str, control_branch: str) -> dict[str, Any]:
    head = _branch(head, control_branch=control_branch);base = _nonempty(base, "GIT_MUTATION_PR_BASE_REQUIRED")
    head_sha = _git_sha(head_sha, "GIT_MUTATION_PR_HEAD_SHA_INVALID");title = _nonempty(title, "GIT_MUTATION_PR_TITLE_REQUIRED");body_sha256 = _sha256(body_sha256, "GIT_MUTATION_PR_BODY_HASH_INVALID")
    return _finish(
        "create-pr", control_branch=control_branch,
        target={"head": head, "base": base},
        preconditions={"headSha": head_sha, "openPrForHeadMustBeAbsent": True},
        mutation={"title": title, "bodySha256": body_sha256},
        readback={"kind": "open-pr", "head": head, "base": base, "expectedHeadSha": head_sha},
    )


def merge_pr(*, pr_number: int, head_sha: str, base: str, control_branch: str, merge_method: str = "squash") -> dict[str, Any]:
    pr_number = _positive_int(pr_number, "GIT_MUTATION_PR_NUMBER_INVALID");head_sha = _git_sha(head_sha, "GIT_MUTATION_PR_HEAD_SHA_INVALID");base = _nonempty(base, "GIT_MUTATION_PR_BASE_REQUIRED")
    if merge_method not in {"merge", "squash", "rebase"}:raise RuntimeError("GIT_MUTATION_MERGE_METHOD_INVALID")
    return _finish(
        "merge-pr", control_branch=control_branch,
        target={"prNumber": pr_number},
        preconditions={"expectedHeadSha": head_sha, "expectedBase": base, "requiredGatesMustBeGreen": True},
        mutation={"mergeMethod": merge_method},
        readback={"kind": "merged-pr", "prNumber": pr_number, "expectedHeadSha": head_sha, "expectedBase": base},
    )


def update_ref(*, branch: str, current_sha: str, new_sha: str, control_branch: str, force: bool = False) -> dict[str, Any]:
    branch = _branch(branch, control_branch=control_branch);current_sha = _git_sha(current_sha, "GIT_MUTATION_CURRENT_REF_SHA_INVALID");new_sha = _git_sha(new_sha, "GIT_MUTATION_NEW_REF_SHA_INVALID")
    if force is not False:raise RuntimeError("GIT_MUTATION_FORCE_FORBIDDEN")
    return _finish(
        "update-ref", control_branch=control_branch,
        target={"branch": branch},
        preconditions={"currentSha": current_sha},
        mutation={"newSha": new_sha, "force": False},
        readback={"kind": "branch-head", "branch": branch, "expectedSha": new_sha},
    )


def _validate_semantics(plan: dict[str, Any]) -> None:
    operation=plan["operation"];control=_nonempty(plan.get("controlBranch"),"GIT_MUTATION_CONTROL_BRANCH_REQUIRED");target=plan["target"];pre=plan["preconditions"];mutation=plan["mutation"];readback=plan["readback"]
    if operation=="create-branch":
        _exact(target,{"branch"},"GIT_MUTATION_TARGET_INVALID");_exact(pre,{"branchMustBeAbsent","baseSha"},"GIT_MUTATION_PRECONDITIONS_INVALID");_exact(mutation,{"fromSha"},"GIT_MUTATION_PAYLOAD_INVALID");_exact(readback,{"kind","branch","expectedSha"},"GIT_MUTATION_READBACK_INVALID")
        branch=_branch(target["branch"],control_branch=control);base=_git_sha(pre["baseSha"],"GIT_MUTATION_BASE_SHA_INVALID")
        if pre["branchMustBeAbsent"] is not True or mutation["fromSha"]!=base or readback!={"kind":"branch-head","branch":branch,"expectedSha":base}:raise RuntimeError("GIT_MUTATION_PLAN_SEMANTICS_INVALID")
    elif operation in {"create-file","update-file","delete-file"}:
        _exact(target,{"branch","path"},"GIT_MUTATION_TARGET_INVALID");branch=_branch(target["branch"],control_branch=control);path=_path(target["path"])
        if operation=="create-file":
            _exact(pre,{"branchHead","pathMustBeAbsent"},"GIT_MUTATION_PRECONDITIONS_INVALID");_exact(mutation,{"contentSha256"},"GIT_MUTATION_PAYLOAD_INVALID");_exact(readback,{"kind","branch","path","expectedContentSha256","expectedParentHead"},"GIT_MUTATION_READBACK_INVALID")
            head=_git_sha(pre["branchHead"],"GIT_MUTATION_BRANCH_HEAD_INVALID");digest=_sha256(mutation["contentSha256"],"GIT_MUTATION_CONTENT_HASH_INVALID")
            if pre["pathMustBeAbsent"] is not True or readback!={"kind":"file-content","branch":branch,"path":path,"expectedContentSha256":digest,"expectedParentHead":head}:raise RuntimeError("GIT_MUTATION_PLAN_SEMANTICS_INVALID")
        elif operation=="update-file":
            _exact(pre,{"branchHead","blobSha"},"GIT_MUTATION_PRECONDITIONS_INVALID");_exact(mutation,{"contentSha256"},"GIT_MUTATION_PAYLOAD_INVALID");_exact(readback,{"kind","branch","path","expectedContentSha256","expectedParentHead"},"GIT_MUTATION_READBACK_INVALID")
            head=_git_sha(pre["branchHead"],"GIT_MUTATION_BRANCH_HEAD_INVALID");_git_sha(pre["blobSha"],"GIT_MUTATION_BLOB_SHA_INVALID");digest=_sha256(mutation["contentSha256"],"GIT_MUTATION_CONTENT_HASH_INVALID")
            if readback!={"kind":"file-content","branch":branch,"path":path,"expectedContentSha256":digest,"expectedParentHead":head}:raise RuntimeError("GIT_MUTATION_PLAN_SEMANTICS_INVALID")
        else:
            _exact(pre,{"branchHead","blobSha"},"GIT_MUTATION_PRECONDITIONS_INVALID");_exact(mutation,{"delete"},"GIT_MUTATION_PAYLOAD_INVALID");_exact(readback,{"kind","branch","path","expectedParentHead"},"GIT_MUTATION_READBACK_INVALID")
            head=_git_sha(pre["branchHead"],"GIT_MUTATION_BRANCH_HEAD_INVALID");_git_sha(pre["blobSha"],"GIT_MUTATION_BLOB_SHA_INVALID")
            if mutation["delete"] is not True or readback!={"kind":"file-absent","branch":branch,"path":path,"expectedParentHead":head}:raise RuntimeError("GIT_MUTATION_PLAN_SEMANTICS_INVALID")
    elif operation=="mutate-files":
        _exact(target,{"branch"},"GIT_MUTATION_TARGET_INVALID");branch=_branch(target["branch"],control_branch=control)
        _exact(pre,{"branchHead"},"GIT_MUTATION_PRECONDITIONS_INVALID");head=_git_sha(pre["branchHead"],"GIT_MUTATION_BRANCH_HEAD_INVALID")
        _exact(mutation,{"entries"},"GIT_MUTATION_PAYLOAD_INVALID");entries=mutation["entries"]
        if not isinstance(entries,list) or not entries:raise RuntimeError("GIT_MUTATION_CHANGES_REQUIRED")
        canonical=[]
        for entry in entries:
            _exact(entry,{"path","operation","contentSha256"},"GIT_MUTATION_CHANGE_INVALID");path=_path(entry["path"]);kind=entry["operation"]
            if kind=="write":digest=_sha256(entry["contentSha256"],"GIT_MUTATION_CONTENT_HASH_INVALID")
            elif kind=="delete" and entry["contentSha256"] is None:digest=None
            else:raise RuntimeError("GIT_MUTATION_CHANGE_INVALID")
            canonical.append({"path":path,"operation":kind,"contentSha256":digest})
        paths=[item["path"] for item in canonical]
        if paths!=sorted(paths) or len(paths)!=len(set(paths)):raise RuntimeError("GIT_MUTATION_CHANGES_NOT_CANONICAL")
        hashes={item["path"]:item["contentSha256"] for item in canonical if item["operation"]=="write"}
        expected={"kind":"git-bundle","branch":branch,"expectedParentHead":head,"expectedChangedPaths":paths,"expectedContentSha256":hashes}
        _exact(readback,set(expected),"GIT_MUTATION_READBACK_INVALID")
        if entries!=canonical or readback!=expected:raise RuntimeError("GIT_MUTATION_PLAN_SEMANTICS_INVALID")
    elif operation=="create-pr":
        _exact(target,{"head","base"},"GIT_MUTATION_TARGET_INVALID");_exact(pre,{"headSha","openPrForHeadMustBeAbsent"},"GIT_MUTATION_PRECONDITIONS_INVALID");_exact(mutation,{"title","bodySha256"},"GIT_MUTATION_PAYLOAD_INVALID");_exact(readback,{"kind","head","base","expectedHeadSha"},"GIT_MUTATION_READBACK_INVALID")
        head=_branch(target["head"],control_branch=control);base=_nonempty(target["base"],"GIT_MUTATION_PR_BASE_REQUIRED");head_sha=_git_sha(pre["headSha"],"GIT_MUTATION_PR_HEAD_SHA_INVALID");_nonempty(mutation["title"],"GIT_MUTATION_PR_TITLE_REQUIRED");_sha256(mutation["bodySha256"],"GIT_MUTATION_PR_BODY_HASH_INVALID")
        if pre["openPrForHeadMustBeAbsent"] is not True or readback!={"kind":"open-pr","head":head,"base":base,"expectedHeadSha":head_sha}:raise RuntimeError("GIT_MUTATION_PLAN_SEMANTICS_INVALID")
    elif operation=="merge-pr":
        _exact(target,{"prNumber"},"GIT_MUTATION_TARGET_INVALID");_exact(pre,{"expectedHeadSha","expectedBase","requiredGatesMustBeGreen"},"GIT_MUTATION_PRECONDITIONS_INVALID");_exact(mutation,{"mergeMethod"},"GIT_MUTATION_PAYLOAD_INVALID");_exact(readback,{"kind","prNumber","expectedHeadSha","expectedBase"},"GIT_MUTATION_READBACK_INVALID")
        number=_positive_int(target["prNumber"],"GIT_MUTATION_PR_NUMBER_INVALID");head_sha=_git_sha(pre["expectedHeadSha"],"GIT_MUTATION_PR_HEAD_SHA_INVALID");base=_nonempty(pre["expectedBase"],"GIT_MUTATION_PR_BASE_REQUIRED")
        if pre["requiredGatesMustBeGreen"] is not True or mutation["mergeMethod"] not in {"merge","squash","rebase"} or readback!={"kind":"merged-pr","prNumber":number,"expectedHeadSha":head_sha,"expectedBase":base}:raise RuntimeError("GIT_MUTATION_PLAN_SEMANTICS_INVALID")
    elif operation=="update-ref":
        _exact(target,{"branch"},"GIT_MUTATION_TARGET_INVALID");_exact(pre,{"currentSha"},"GIT_MUTATION_PRECONDITIONS_INVALID");_exact(mutation,{"newSha","force"},"GIT_MUTATION_PAYLOAD_INVALID");_exact(readback,{"kind","branch","expectedSha"},"GIT_MUTATION_READBACK_INVALID")
        branch=_branch(target["branch"],control_branch=control);_git_sha(pre["currentSha"],"GIT_MUTATION_CURRENT_REF_SHA_INVALID");new_sha=_git_sha(mutation["newSha"],"GIT_MUTATION_NEW_REF_SHA_INVALID")
        if mutation["force"] is not False or readback!={"kind":"branch-head","branch":branch,"expectedSha":new_sha}:raise RuntimeError("GIT_MUTATION_FORCE_FORBIDDEN")


def validate(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict) or set(plan) != PLAN_FIELDS:raise RuntimeError("GIT_MUTATION_PLAN_FIELDS_INVALID")
    if plan.get("schemaVersion") != SCHEMA_VERSION or plan.get("repository") != REPOSITORY:raise RuntimeError("GIT_MUTATION_PLAN_CONTRACT_INVALID")
    operation = plan.get("operation")
    if operation not in OPERATIONS or plan.get("riskClass") != RISK_CLASS[operation] or plan.get("connectorAction") != CONNECTOR_ACTION[operation]:raise RuntimeError("GIT_MUTATION_PLAN_OPERATION_INVALID")
    if not isinstance(plan.get("target"),dict) or not isinstance(plan.get("preconditions"),dict) or not isinstance(plan.get("mutation"),dict) or not isinstance(plan.get("readback"),dict):raise RuntimeError("GIT_MUTATION_PLAN_FIELDS_INVALID")
    if plan.get("authorizesMutation") is not False:raise RuntimeError("GIT_MUTATION_PLAN_MUST_NOT_AUTHORIZE")
    _validate_semantics(plan)
    if plan.get("planHash") != stable_hash(_core(plan)):raise RuntimeError("GIT_MUTATION_PLAN_HASH_MISMATCH")
    return plan
