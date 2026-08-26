"""M12-RP1B remote canonical execution bridge.

The bridge is the canonical execution host behind a transport carrier.  It does not
grant authority.  Commands are closed, non-authoritative envelopes; the bridge
re-observes canonical state, runs repository planners, applies only through the
existing domain writers or the governed direct-Git path, and emits a hash-bound
aggregate receipt.

GitHub issue comments / GitHub Actions are transport only.  They never become an
authority, planner, or source of semantic truth.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
from typing import Any
from urllib.parse import quote

from tools import coordination_apply
from tools import continuation_remote
from tools import git_mutation_bundle
from tools import git_mutation_plan
from tools import remote_canonical
from tools import transition_protocol
from tools.canonical import stable_hash
from tools.coordination_remote import (
    ApiError,
    GhApiTransport,
    GitHubCoordinationAuthority,
)

COMMAND_SCHEMA = "RemoteCanonicalCommand 0.1"
RECEIPT_SCHEMA = "RemoteCanonicalExecutionReceipt 0.1"
REPOSITORY = "EAKerber/MobiliPresenter"
CONTROL_BRANCH = "main"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
COMMAND_FIELDS = {
    "schemaVersion",
    "executionId",
    "kind",
    "actor",
    "declaredIntent",
    "target",
    "expected",
    "payload",
    "semanticAuthority",
    "authorizesMutation",
}
RECEIPT_FIELDS = {
    "schemaVersion",
    "executionId",
    "command",
    "commandHash",
    "route",
    "source",
    "planHash",
    "evidence",
    "aggregateReadback",
    "status",
    "blockers",
    "semanticAuthority",
    "authorizesMutation",
    "receiptHash",
}
GIT_ACTIONS = {
    "create-branch",
    "create-file",
    "update-file",
    "delete-file",
    "mutate-files",
}
DOMAIN_ACTIONS = {
    "coordination": {"intent", "acquire", "renew", "release"},
    "continuation": {
        "create",
        "advance",
        "wait",
        "handoff",
        "resume",
        "done",
        "bind-execution",
        "restart",
    },
}


class RemoteCanonicalExecutionError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _code(exc: BaseException) -> str:
    value = getattr(exc, "code", None)
    if isinstance(value, str) and value:
        return value
    text = str(exc)
    return text.split(":", 1)[0] if text else exc.__class__.__name__


def _nonempty(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RemoteCanonicalExecutionError(code)
    return value.strip()


def _identifier(value: Any, code: str) -> str:
    value = _nonempty(value, code)
    if not ID_RE.fullmatch(value):
        raise RemoteCanonicalExecutionError(code)
    return value


def _git_sha(value: Any, code: str) -> str:
    if not isinstance(value, str) or not GIT_SHA_RE.fullmatch(value):
        raise RemoteCanonicalExecutionError(code)
    return value


def _actor(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"role", "workerId", "sessionId"}:
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_ACTOR_INVALID")
    return {
        "role": _nonempty(value.get("role"), "REMOTE_COMMAND_ACTOR_INVALID"),
        "workerId": _nonempty(value.get("workerId"), "REMOTE_COMMAND_ACTOR_INVALID"),
        "sessionId": _nonempty(value.get("sessionId"), "REMOTE_COMMAND_ACTOR_INVALID"),
    }


def _subject(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"kind", "id"}:
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_SUBJECT_INVALID")
    return {
        "kind": _identifier(value.get("kind"), "REMOTE_COMMAND_SUBJECT_INVALID"),
        "id": _identifier(value.get("id"), "REMOTE_COMMAND_SUBJECT_INVALID"),
    }


def _path(value: Any) -> str:
    path = _nonempty(value, "REMOTE_COMMAND_PATH_INVALID")
    if path.startswith("/") or path.endswith("/") or "\\" in path:
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_PATH_INVALID")
    if any(segment in {"", ".", ".."} for segment in path.split("/")):
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_PATH_INVALID")
    return path


def _changes(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_CHANGES_REQUIRED")
    result: list[dict[str, Any]] = []
    for change in value:
        if not isinstance(change, dict):
            raise RemoteCanonicalExecutionError("REMOTE_COMMAND_CHANGE_INVALID")
        path = _path(change.get("path"))
        if set(change) == {"path", "content"} and isinstance(change.get("content"), str):
            result.append({"path": path, "content": change["content"]})
        elif set(change) == {"path", "delete"} and change.get("delete") is True:
            result.append({"path": path, "delete": True})
        else:
            raise RemoteCanonicalExecutionError("REMOTE_COMMAND_CHANGE_INVALID")
    paths = [change["path"] for change in result]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_CHANGES_NOT_CANONICAL")
    return result


def _target(value: Any, kind: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_TARGET_INVALID")
    if kind == "domain":
        if set(value) != {"domain", "action", "subject"}:
            raise RemoteCanonicalExecutionError("REMOTE_COMMAND_TARGET_INVALID")
        domain = _identifier(value.get("domain"), "REMOTE_COMMAND_DOMAIN_INVALID")
        action = _identifier(value.get("action"), "REMOTE_COMMAND_ACTION_INVALID")
        if domain not in DOMAIN_ACTIONS or action not in DOMAIN_ACTIONS[domain]:
            raise RemoteCanonicalExecutionError("REMOTE_COMMAND_ROUTE_UNSUPPORTED")
        return {"domain": domain, "action": action, "subject": _subject(value["subject"])}
    if set(value) not in ({"operation", "branch"}, {"operation", "branch", "path"}):
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_TARGET_INVALID")
    operation = _identifier(value.get("operation"), "REMOTE_COMMAND_GIT_OPERATION_INVALID")
    if operation not in GIT_ACTIONS:
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_GIT_OPERATION_UNSUPPORTED")
    branch = _nonempty(value.get("branch"), "REMOTE_COMMAND_BRANCH_INVALID")
    if branch == CONTROL_BRANCH:
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_CONTROL_BRANCH_FORBIDDEN")
    expected_fields = (
        {"operation", "branch"}
        if operation in {"create-branch", "mutate-files"}
        else {"operation", "branch", "path"}
    )
    if set(value) != expected_fields:
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_TARGET_INVALID")
    result: dict[str, Any] = {"operation": operation, "branch": branch}
    if operation not in {"create-branch", "mutate-files"}:
        result["path"] = _path(value.get("path"))
    return result


def _expected(value: Any, kind: str, target: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_EXPECTED_INVALID")
    if kind == "domain":
        if set(value) != {"authorityRevision"}:
            raise RemoteCanonicalExecutionError("REMOTE_COMMAND_EXPECTED_INVALID")
        return {
            "authorityRevision": _git_sha(
                value.get("authorityRevision"), "REMOTE_COMMAND_AUTHORITY_REVISION_INVALID"
            )
        }
    operation = target["operation"]
    if operation == "create-branch":
        if set(value) != {"baseSha"}:
            raise RemoteCanonicalExecutionError("REMOTE_COMMAND_EXPECTED_INVALID")
        return {"baseSha": _git_sha(value.get("baseSha"), "REMOTE_COMMAND_BASE_SHA_INVALID")}
    if operation == "create-file":
        if set(value) != {"branchHead"}:
            raise RemoteCanonicalExecutionError("REMOTE_COMMAND_EXPECTED_INVALID")
        return {
            "branchHead": _git_sha(
                value.get("branchHead"), "REMOTE_COMMAND_BRANCH_HEAD_INVALID"
            )
        }
    if operation == "mutate-files":
        if set(value) != {"branchHead"}:
            raise RemoteCanonicalExecutionError("REMOTE_COMMAND_EXPECTED_INVALID")
        return {
            "branchHead": _git_sha(
                value.get("branchHead"), "REMOTE_COMMAND_BRANCH_HEAD_INVALID"
            )
        }
    if set(value) != {"branchHead", "blobSha"}:
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_EXPECTED_INVALID")
    return {
        "branchHead": _git_sha(
            value.get("branchHead"), "REMOTE_COMMAND_BRANCH_HEAD_INVALID"
        ),
        "blobSha": _git_sha(value.get("blobSha"), "REMOTE_COMMAND_BLOB_SHA_INVALID"),
    }


def _payload(value: Any, kind: str, target: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_PAYLOAD_INVALID")
    if kind == "domain":
        return copy.deepcopy(value)
    operation = target["operation"]
    if operation == "create-branch":
        if value:
            raise RemoteCanonicalExecutionError("REMOTE_COMMAND_PAYLOAD_INVALID")
        return {}
    if operation in {"create-file", "update-file"}:
        if set(value) != {"content", "message"}:
            raise RemoteCanonicalExecutionError("REMOTE_COMMAND_PAYLOAD_INVALID")
        if not isinstance(value.get("content"), str):
            raise RemoteCanonicalExecutionError("REMOTE_COMMAND_CONTENT_INVALID")
        return {
            "content": value["content"],
            "message": _nonempty(value.get("message"), "REMOTE_COMMAND_MESSAGE_INVALID"),
        }
    if operation == "mutate-files":
        if set(value) != {"changes", "message"}:
            raise RemoteCanonicalExecutionError("REMOTE_COMMAND_PAYLOAD_INVALID")
        return {
            "changes": _changes(value.get("changes")),
            "message": _nonempty(value.get("message"), "REMOTE_COMMAND_MESSAGE_INVALID"),
        }
    if set(value) != {"message"}:
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_PAYLOAD_INVALID")
    return {"message": _nonempty(value.get("message"), "REMOTE_COMMAND_MESSAGE_INVALID")}


def validate_command(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != COMMAND_FIELDS:
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_FIELDS_INVALID")
    if value.get("schemaVersion") != COMMAND_SCHEMA:
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_SCHEMA_UNSUPPORTED")
    execution_id = _identifier(value.get("executionId"), "REMOTE_COMMAND_EXECUTION_ID_INVALID")
    kind = value.get("kind")
    if kind not in {"domain", "git-direct"}:
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_KIND_UNSUPPORTED")
    actor = _actor(value.get("actor"))
    declared = value.get("declaredIntent")
    if not isinstance(declared, dict):
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_DECLARED_INTENT_INVALID")
    target = _target(value.get("target"), kind)
    expected = _expected(value.get("expected"), kind, target)
    payload = _payload(value.get("payload"), kind, target)
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_MUST_NOT_AUTHORIZE")
    canonical = {
        "schemaVersion": COMMAND_SCHEMA,
        "executionId": execution_id,
        "kind": kind,
        "actor": actor,
        "declaredIntent": copy.deepcopy(declared),
        "target": target,
        "expected": expected,
        "payload": payload,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    if value != canonical:
        raise RemoteCanonicalExecutionError("REMOTE_COMMAND_NOT_CANONICAL")
    return value


def command_hash(command: dict[str, Any]) -> str:
    return stable_hash(validate_command(command))


def _json(response: Any, code: str) -> dict[str, Any]:
    try:
        value = json.loads(response.body)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise RemoteCanonicalExecutionError(code) from exc
    if not isinstance(value, dict):
        raise RemoteCanonicalExecutionError(code)
    return value


def _ref_head(transport: Any, branch: str, *, missing_ok: bool = False) -> str | None:
    endpoint = f"repos/{REPOSITORY}/git/ref/heads/{quote(branch, safe='')}"
    try:
        payload = _json(transport.request("GET", endpoint), "REMOTE_GIT_REF_INVALID")
    except ApiError as exc:
        if missing_ok and exc.status == 404:
            return None
        raise RemoteCanonicalExecutionError("REMOTE_GIT_REF_UNAVAILABLE", exc.detail) from exc
    value = (payload.get("object") or {}).get("sha")
    return _git_sha(value, "REMOTE_GIT_REF_INVALID")


def _commit(transport: Any, sha: str) -> dict[str, Any]:
    sha = _git_sha(sha, "REMOTE_GIT_COMMIT_SHA_INVALID")
    try:
        payload = _json(
            transport.request("GET", f"repos/{REPOSITORY}/git/commits/{sha}"),
            "REMOTE_GIT_COMMIT_INVALID",
        )
    except ApiError as exc:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_COMMIT_UNAVAILABLE", exc.detail) from exc
    tree_sha = _git_sha((payload.get("tree") or {}).get("sha"), "REMOTE_GIT_TREE_SHA_INVALID")
    parents_raw = payload.get("parents")
    parents: list[str] = []
    if not isinstance(parents_raw, list):
        raise RemoteCanonicalExecutionError("REMOTE_GIT_COMMIT_INVALID")
    for parent in parents_raw:
        parents.append(_git_sha((parent or {}).get("sha"), "REMOTE_GIT_PARENT_SHA_INVALID"))
    return {"sha": sha, "treeSha": tree_sha, "parents": parents}


def _tree_entries(transport: Any, tree_sha: str) -> list[dict[str, Any]]:
    tree_sha = _git_sha(tree_sha, "REMOTE_GIT_TREE_SHA_INVALID")
    try:
        payload = _json(
            transport.request(
                "GET", f"repos/{REPOSITORY}/git/trees/{tree_sha}?recursive=1"
            ),
            "REMOTE_GIT_TREE_INVALID",
        )
    except ApiError as exc:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_TREE_UNAVAILABLE", exc.detail) from exc
    if payload.get("truncated") is True:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_TREE_TRUNCATED")
    raw = payload.get("tree")
    if not isinstance(raw, list):
        raise RemoteCanonicalExecutionError("REMOTE_GIT_TREE_INVALID")
    result: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise RemoteCanonicalExecutionError("REMOTE_GIT_TREE_INVALID")
        path = item.get("path")
        kind = item.get("type")
        sha = item.get("sha")
        if isinstance(path, str) and isinstance(kind, str) and isinstance(sha, str):
            result.append({"path": path, "type": kind, "sha": sha})
    return result


def _blob_at(entries: list[dict[str, Any]], path: str) -> str | None:
    found = [
        item["sha"]
        for item in entries
        if item.get("type") == "blob" and item.get("path") == path
    ]
    if len(found) > 1:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_TREE_DUPLICATE_PATH")
    if not found:
        return None
    return _git_sha(found[0], "REMOTE_GIT_BLOB_SHA_INVALID")


def _content_sha256(transport: Any, path: str, ref: str) -> str:
    endpoint = (
        f"repos/{REPOSITORY}/contents/{quote(path, safe='/')}"
        f"?ref={quote(ref, safe='')}"
    )
    try:
        payload = _json(transport.request("GET", endpoint), "REMOTE_GIT_CONTENT_INVALID")
    except ApiError as exc:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_CONTENT_UNAVAILABLE", exc.detail) from exc
    if payload.get("encoding") != "base64" or not isinstance(payload.get("content"), str):
        raise RemoteCanonicalExecutionError("REMOTE_GIT_CONTENT_INVALID")
    try:
        raw = base64.b64decode(payload["content"], validate=False)
    except Exception as exc:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_CONTENT_INVALID") from exc
    return hashlib.sha256(raw).hexdigest()


def _create_blob(transport: Any, content: str) -> str:
    try:
        payload = _json(
            transport.request(
                "POST",
                f"repos/{REPOSITORY}/git/blobs",
                payload={"content": content, "encoding": "utf-8"},
            ),
            "REMOTE_GIT_BLOB_CREATE_INVALID",
        )
    except ApiError as exc:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_BLOB_CREATE_FAILED", exc.detail) from exc
    return _git_sha(payload.get("sha"), "REMOTE_GIT_BLOB_CREATE_INVALID")


def _create_tree(
    transport: Any,
    base_tree_sha: str,
    *,
    entries: list[dict[str, Any]],
) -> str:
    if not isinstance(entries, list) or not entries:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_TREE_ENTRIES_INVALID")
    try:
        payload = _json(
            transport.request(
                "POST",
                f"repos/{REPOSITORY}/git/trees",
                payload={"base_tree": base_tree_sha, "tree": entries},
            ),
            "REMOTE_GIT_TREE_CREATE_INVALID",
        )
    except ApiError as exc:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_TREE_CREATE_FAILED", exc.detail) from exc
    return _git_sha(payload.get("sha"), "REMOTE_GIT_TREE_CREATE_INVALID")


def _create_commit(
    transport: Any,
    *,
    message: str,
    tree_sha: str,
    parent_sha: str,
) -> str:
    try:
        payload = _json(
            transport.request(
                "POST",
                f"repos/{REPOSITORY}/git/commits",
                payload={"message": message, "tree": tree_sha, "parents": [parent_sha]},
            ),
            "REMOTE_GIT_COMMIT_CREATE_INVALID",
        )
    except ApiError as exc:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_COMMIT_CREATE_FAILED", exc.detail) from exc
    return _git_sha(payload.get("sha"), "REMOTE_GIT_COMMIT_CREATE_INVALID")


def _publish_ref(transport: Any, branch: str, commit_sha: str, expected_head: str) -> None:
    if _ref_head(transport, branch) != expected_head:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_REF_DRIFT")
    endpoint = f"repos/{REPOSITORY}/git/refs/heads/{quote(branch, safe='')}"
    try:
        transport.request("PATCH", endpoint, payload={"sha": commit_sha, "force": False})
    except ApiError as exc:
        if _ref_head(transport, branch, missing_ok=True) != commit_sha:
            raise RemoteCanonicalExecutionError("REMOTE_GIT_REF_UPDATE_FAILED", exc.detail) from exc
    if _ref_head(transport, branch) != commit_sha:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_REF_READBACK_MISMATCH")


def _create_ref(transport: Any, branch: str, sha: str) -> None:
    if _ref_head(transport, branch, missing_ok=True) is not None:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_BRANCH_ALREADY_EXISTS")
    try:
        transport.request(
            "POST",
            f"repos/{REPOSITORY}/git/refs",
            payload={"ref": f"refs/heads/{branch}", "sha": sha},
        )
    except ApiError as exc:
        if _ref_head(transport, branch, missing_ok=True) != sha:
            raise RemoteCanonicalExecutionError("REMOTE_GIT_REF_CREATE_FAILED", exc.detail) from exc
    if _ref_head(transport, branch) != sha:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_REF_READBACK_MISMATCH")


def _verify_git_plan_observed(plan: dict[str, Any], observed: Any) -> dict[str, Any]:
    git_mutation_plan.validate(plan)
    if not isinstance(observed, dict):
        raise RemoteCanonicalExecutionError("REMOTE_GIT_PLAN_READBACK_INVALID")
    expected = plan["readback"]
    kind = expected["kind"]
    if observed.get("kind") != kind or observed.get("status") != "PASS":
        raise RemoteCanonicalExecutionError("REMOTE_GIT_PLAN_READBACK_INVALID")
    if kind == "branch-head":
        if (
            observed.get("branch") != expected["branch"]
            or observed.get("sha") != expected["expectedSha"]
        ):
            raise RemoteCanonicalExecutionError("REMOTE_GIT_PLAN_READBACK_MISMATCH")
    elif kind == "file-content":
        if (
            observed.get("branch") != expected["branch"]
            or observed.get("path") != expected["path"]
            or observed.get("contentSha256") != expected["expectedContentSha256"]
        ):
            raise RemoteCanonicalExecutionError("REMOTE_GIT_PLAN_READBACK_MISMATCH")
    elif kind == "file-absent":
        if (
            observed.get("branch") != expected["branch"]
            or observed.get("path") != expected["path"]
            or observed.get("absent") is not True
        ):
            raise RemoteCanonicalExecutionError("REMOTE_GIT_PLAN_READBACK_MISMATCH")
    elif kind == "git-bundle":
        if (
            observed.get("branch") != expected["branch"]
            or observed.get("parentHead") != expected["expectedParentHead"]
            or observed.get("changedPaths") != expected["expectedChangedPaths"]
            or observed.get("contentSha256") != expected["expectedContentSha256"]
        ):
            raise RemoteCanonicalExecutionError("REMOTE_GIT_PLAN_READBACK_MISMATCH")
    else:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_PLAN_READBACK_KIND_UNSUPPORTED")
    return observed


def _build_git_plan(command: dict[str, Any]) -> dict[str, Any]:
    target = command["target"]
    expected = command["expected"]
    operation = target["operation"]
    if operation == "create-branch":
        plan = git_mutation_plan.create_branch(
            branch=target["branch"],
            base_sha=expected["baseSha"],
            control_branch=CONTROL_BRANCH,
        )
    elif operation == "create-file":
        digest = hashlib.sha256(command["payload"]["content"].encode("utf-8")).hexdigest()
        plan = git_mutation_plan.create_file(
            branch=target["branch"],
            path=target["path"],
            branch_head=expected["branchHead"],
            content_sha256=digest,
            control_branch=CONTROL_BRANCH,
        )
    elif operation == "update-file":
        digest = hashlib.sha256(command["payload"]["content"].encode("utf-8")).hexdigest()
        plan = git_mutation_plan.update_file(
            branch=target["branch"],
            path=target["path"],
            branch_head=expected["branchHead"],
            blob_sha=expected["blobSha"],
            content_sha256=digest,
            control_branch=CONTROL_BRANCH,
        )
    elif operation == "delete-file":
        plan = git_mutation_plan.delete_file(
            branch=target["branch"],
            path=target["path"],
            branch_head=expected["branchHead"],
            blob_sha=expected["blobSha"],
            control_branch=CONTROL_BRANCH,
        )
    else:
        plan = git_mutation_plan.mutate_files(
            branch=target["branch"],
            branch_head=expected["branchHead"],
            changes=command["payload"]["changes"],
            control_branch=CONTROL_BRANCH,
        )
    return git_mutation_plan.validate(plan)


def _path_absent(transport: Any, path: str, ref: str) -> bool:
    endpoint = (
        f"repos/{REPOSITORY}/contents/{quote(path, safe='/')}"
        f"?ref={quote(ref, safe='')}"
    )
    try:
        transport.request("GET", endpoint)
    except ApiError as exc:
        if exc.status == 404:
            return True
        raise RemoteCanonicalExecutionError("REMOTE_GIT_CONTENT_UNAVAILABLE", exc.detail) from exc
    return False


def _execute_multi_path(
    command: dict[str, Any],
    transport: Any,
    plan: dict[str, Any],
    *,
    observed_head: str,
    base_commit: dict[str, Any],
    base_tree_entries: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    changes = command["payload"]["changes"]
    bundle = git_mutation_bundle.build_bundle(
        repository=REPOSITORY,
        branch=plan["target"]["branch"],
        base_head=observed_head,
        base_tree_sha=base_commit["treeSha"],
        changes=changes,
        current_branch_head=observed_head,
    )
    content_by_path = {
        change["path"]: change["content"]
        for change in changes
        if "content" in change
    }
    git_mutation_bundle.verify_materialized_content(bundle, content_by_path)
    bundle_entries = {entry["path"]: entry for entry in bundle["entries"]}
    tree_entries: list[dict[str, Any]] = []
    for change in changes:
        path = change["path"]
        if "content" in change:
            blob_sha = _create_blob(transport, change["content"])
            if blob_sha != bundle_entries[path]["gitBlobSha"]:
                raise RemoteCanonicalExecutionError("REMOTE_GIT_BLOB_HASH_MISMATCH")
        else:
            blob_sha = None
        tree_entries.append(
            {"path": path, "mode": "100644", "type": "blob", "sha": blob_sha}
        )
    candidate_tree_sha = _create_tree(
        transport,
        base_commit["treeSha"],
        entries=tree_entries,
    )
    candidate_tree_entries = _tree_entries(transport, candidate_tree_sha)
    tree_proof = git_mutation_bundle.verify_tree(
        bundle,
        base_tree_entries=base_tree_entries,
        candidate_tree_entries=candidate_tree_entries,
        candidate_tree_sha=candidate_tree_sha,
    )
    commit_sha = _create_commit(
        transport,
        message=command["payload"]["message"],
        tree_sha=candidate_tree_sha,
        parent_sha=observed_head,
    )
    created_commit = _commit(transport, commit_sha)
    if created_commit["treeSha"] != candidate_tree_sha or created_commit["parents"] != [observed_head]:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_COMMIT_READBACK_MISMATCH")
    _publish_ref(transport, plan["target"]["branch"], commit_sha, observed_head)
    content_hashes: dict[str, str] = {}
    for change in changes:
        path = change["path"]
        if "content" in change:
            content_hashes[path] = _content_sha256(transport, path, commit_sha)
        elif not _path_absent(transport, path, commit_sha):
            raise RemoteCanonicalExecutionError("REMOTE_GIT_DELETE_READBACK_MISMATCH")
    observed = {
        "kind": "git-bundle",
        "branch": plan["target"]["branch"],
        "parentHead": observed_head,
        "branchHead": _ref_head(transport, plan["target"]["branch"]),
        "changedPaths": bundle["expectedChangedPaths"],
        "contentSha256": content_hashes,
        "status": "PASS",
    }
    _verify_git_plan_observed(plan, observed)
    provider_readback = {
        "branchHead": observed["branchHead"],
        "commitSha": commit_sha,
        "parentSha": observed_head,
        "treeSha": candidate_tree_sha,
        "changedPaths": bundle["expectedChangedPaths"],
        "contentSha256": content_hashes,
        "treeProof": tree_proof,
    }
    bundle_readback = git_mutation_bundle.verify_readback(bundle, provider_readback)
    evidence = {
        "kind": "git-mutation-bundle-readback",
        "plan": plan,
        "observed": observed,
        "bundle": bundle,
        "providerReadback": provider_readback,
        "bundleReadback": bundle_readback,
    }
    aggregate = {
        "kind": "git-bundle",
        "branch": bundle_readback["branch"],
        "branchHead": bundle_readback["branchHead"],
        "changedPaths": bundle_readback["changedPaths"],
        "readbackHash": bundle_readback["readbackHash"],
        "status": "PASS",
    }
    return plan, evidence, aggregate


def _execute_git_direct(
    command: dict[str, Any],
    transport: Any,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    plan = _build_git_plan(command)
    operation = plan["operation"]
    branch = plan["target"].get("branch")
    if branch == CONTROL_BRANCH:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_CONTROL_BRANCH_FORBIDDEN")
    if operation == "create-branch":
        base_sha = plan["preconditions"]["baseSha"]
        _commit(transport, base_sha)
        _create_ref(transport, branch, base_sha)
        observed = {
            "kind": "branch-head",
            "branch": branch,
            "sha": _ref_head(transport, branch),
            "status": "PASS",
        }
        _verify_git_plan_observed(plan, observed)
        return plan, {"kind": "git-mutation-plan-readback", "plan": plan, "observed": observed}, {
            "kind": "branch-head",
            "branch": branch,
            "head": observed["sha"],
            "status": "PASS",
        }

    expected_head = plan["preconditions"]["branchHead"]
    observed_head = _ref_head(transport, branch)
    if observed_head != expected_head:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_PLAN_STALE")
    base_commit = _commit(transport, observed_head)
    base_tree_entries = _tree_entries(transport, base_commit["treeSha"])
    if operation == "mutate-files":
        return _execute_multi_path(
            command,
            transport,
            plan,
            observed_head=observed_head,
            base_commit=base_commit,
            base_tree_entries=base_tree_entries,
        )
    path = plan["target"]["path"]
    current_blob = _blob_at(base_tree_entries, path)
    if operation == "create-file":
        if current_blob is not None:
            raise RemoteCanonicalExecutionError("REMOTE_GIT_PATH_ALREADY_EXISTS")
        changes = [{"path": path, "content": command["payload"]["content"]}]
    elif operation == "update-file":
        if current_blob != plan["preconditions"]["blobSha"]:
            raise RemoteCanonicalExecutionError("REMOTE_GIT_BLOB_DRIFT")
        changes = [{"path": path, "content": command["payload"]["content"]}]
    else:
        if current_blob != plan["preconditions"]["blobSha"]:
            raise RemoteCanonicalExecutionError("REMOTE_GIT_BLOB_DRIFT")
        changes = [{"path": path, "delete": True}]

    bundle = git_mutation_bundle.build_bundle(
        repository=REPOSITORY,
        branch=branch,
        base_head=observed_head,
        base_tree_sha=base_commit["treeSha"],
        changes=changes,
        current_branch_head=observed_head,
    )
    git_mutation_bundle.validate_bundle(bundle)
    if operation in {"create-file", "update-file"}:
        git_mutation_bundle.verify_materialized_content(
            bundle, {path: command["payload"]["content"]}
        )
        blob_sha = _create_blob(transport, command["payload"]["content"])
        if blob_sha != bundle["entries"][0]["gitBlobSha"]:
            raise RemoteCanonicalExecutionError("REMOTE_GIT_BLOB_HASH_MISMATCH")
    else:
        blob_sha = None

    candidate_tree_sha = _create_tree(
        transport,
        base_commit["treeSha"],
        entries=[{"path": path, "mode": "100644", "type": "blob", "sha": blob_sha}],
    )
    candidate_tree_entries = _tree_entries(transport, candidate_tree_sha)
    tree_proof = git_mutation_bundle.verify_tree(
        bundle,
        base_tree_entries=base_tree_entries,
        candidate_tree_entries=candidate_tree_entries,
        candidate_tree_sha=candidate_tree_sha,
    )
    commit_sha = _create_commit(
        transport,
        message=command["payload"]["message"],
        tree_sha=candidate_tree_sha,
        parent_sha=observed_head,
    )
    created_commit = _commit(transport, commit_sha)
    if created_commit["treeSha"] != candidate_tree_sha or created_commit["parents"] != [observed_head]:
        raise RemoteCanonicalExecutionError("REMOTE_GIT_COMMIT_READBACK_MISMATCH")
    _publish_ref(transport, branch, commit_sha, observed_head)

    if operation in {"create-file", "update-file"}:
        content_digest = _content_sha256(transport, path, commit_sha)
        observed = {
            "kind": "file-content",
            "branch": branch,
            "path": path,
            "contentSha256": content_digest,
            "status": "PASS",
        }
        content_hashes = {path: content_digest}
    else:
        if not _path_absent(transport, path, commit_sha):
            raise RemoteCanonicalExecutionError("REMOTE_GIT_DELETE_READBACK_MISMATCH")
        observed = {
            "kind": "file-absent",
            "branch": branch,
            "path": path,
            "absent": True,
            "status": "PASS",
        }
        content_hashes = {}

    _verify_git_plan_observed(plan, observed)
    provider_readback = {
        "branchHead": _ref_head(transport, branch),
        "commitSha": commit_sha,
        "parentSha": observed_head,
        "treeSha": candidate_tree_sha,
        "changedPaths": bundle["expectedChangedPaths"],
        "contentSha256": content_hashes,
        "treeProof": tree_proof,
    }
    bundle_readback = git_mutation_bundle.verify_readback(bundle, provider_readback)
    evidence = {
        "kind": "git-mutation-bundle-readback",
        "plan": plan,
        "observed": observed,
        "bundle": bundle,
        "providerReadback": provider_readback,
        "bundleReadback": bundle_readback,
    }
    aggregate = {
        "kind": "git-bundle",
        "branch": branch,
        "branchHead": bundle_readback["branchHead"],
        "changedPaths": bundle_readback["changedPaths"],
        "readbackHash": bundle_readback["readbackHash"],
        "status": "PASS",
    }
    return plan, evidence, aggregate


def _iso_utc(value: Any) -> str:
    if not hasattr(value, "isoformat"):
        raise RemoteCanonicalExecutionError("REMOTE_AUTHORITY_TIME_INVALID")
    text = value.isoformat().replace("+00:00", "Z")
    return text


def _build_domain_request(
    command: dict[str, Any],
    observation: dict[str, Any],
) -> dict[str, Any]:
    domain = command["target"]["domain"]
    if domain == "coordination":
        authority = remote_canonical.COORDINATION_AUTHORITY
        planner = {"id": "tools.coordination_transition", "contract": transition_protocol.PLAN_SCHEMA}
        capabilities = ["coordination.mutate"]
    else:
        authority = remote_canonical.CONTINUATION_AUTHORITY
        planner = {"id": "tools.continuation_transition", "contract": transition_protocol.PLAN_SCHEMA}
        capabilities = ["work.lifecycle.mutate"]
    return remote_canonical.build_request(
        request_id=command["executionId"],
        domain=domain,
        action=command["target"]["action"],
        subject=command["target"]["subject"],
        declared_intent=command["declaredIntent"],
        actor=command["actor"],
        expected_authorities=[
            {"authority": authority, "revision": command["expected"]["authorityRevision"]}
        ],
        allowed_authorities=[authority],
        forbidden_authorities=[],
        planner=planner,
        required_capabilities=capabilities,
        payload=command["payload"],
    )


def _execute_domain(
    command: dict[str, Any],
    transport: Any,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    domain = command["target"]["domain"]
    expected = command["expected"]["authorityRevision"]
    if domain == "coordination":
        authority = GitHubCoordinationAuthority(transport=transport)
        observed = authority.observe()
        if observed.head_sha != expected:
            raise RemoteCanonicalExecutionError("REMOTE_AUTHORITY_DRIFT")
        observation = {
            "authority": remote_canonical.COORDINATION_AUTHORITY,
            "revision": observed.head_sha,
            "state": observed.state,
            "authorityNow": _iso_utc(observed.authority_now),
        }
        request = _build_domain_request(command, observation)
        plan = remote_canonical.plan_request(request, [observation])
        receipt = coordination_apply.apply(authority, plan, plan["planHash"])
    else:
        authority = continuation_remote.GitHubContinuationAuthority(transport=transport)
        observed = authority.observe()
        if observed.head_sha != expected:
            raise RemoteCanonicalExecutionError("REMOTE_AUTHORITY_DRIFT")
        observation = {
            "authority": remote_canonical.CONTINUATION_AUTHORITY,
            "revision": observed.head_sha,
            "state": observed.items,
            "authorityNow": None,
        }
        request = _build_domain_request(command, observation)
        plan = remote_canonical.plan_request(request, [observation])
        receipt = authority.apply(plan, plan["planHash"])
    transition_protocol.validate_plan(plan)
    transition_protocol.validate_receipt(receipt, plan)
    evidence = {
        "kind": "transition-receipt",
        "request": request,
        "plan": plan,
        "receipt": receipt,
    }
    aggregate = {
        "kind": "authority-state",
        "authority": copy.deepcopy(receipt["authority"]),
        "authorityRevision": receipt["authorityRevision"],
        "stateHash": receipt["readbackStateHash"],
        "receiptHash": receipt["receiptHash"],
        "status": "PASS",
    }
    return plan, evidence, aggregate


def _source(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "workflow",
        "sourceSha",
        "runId",
        "issueNumber",
        "commentId",
    }:
        raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_SOURCE_INVALID")
    workflow = _nonempty(value.get("workflow"), "REMOTE_EXECUTION_SOURCE_INVALID")
    source_sha = _git_sha(value.get("sourceSha"), "REMOTE_EXECUTION_SOURCE_SHA_INVALID")
    run_id = _nonempty(value.get("runId"), "REMOTE_EXECUTION_RUN_ID_INVALID")
    issue_number = value.get("issueNumber")
    comment_id = value.get("commentId")
    if (
        not isinstance(issue_number, int)
        or isinstance(issue_number, bool)
        or issue_number <= 0
        or not isinstance(comment_id, int)
        or isinstance(comment_id, bool)
        or comment_id <= 0
    ):
        raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_SOURCE_INVALID")
    return {
        "workflow": workflow,
        "sourceSha": source_sha,
        "runId": run_id,
        "issueNumber": issue_number,
        "commentId": comment_id,
    }


def _route(command: dict[str, Any]) -> dict[str, str]:
    if command["kind"] == "domain":
        return {
            "kind": "domain",
            "domain": command["target"]["domain"],
            "action": command["target"]["action"],
        }
    return {
        "kind": "git-direct",
        "domain": "git",
        "action": command["target"]["operation"],
    }


def build_receipt(
    command: dict[str, Any],
    *,
    source: dict[str, Any],
    plan: dict[str, Any],
    evidence: dict[str, Any],
    aggregate_readback: dict[str, Any],
) -> dict[str, Any]:
    validate_command(command)
    source_value = _source(source)
    route = _route(command)
    if command["kind"] == "domain":
        transition_protocol.validate_plan(plan)
        inner = evidence
        if not isinstance(inner, dict) or set(inner) != {"kind", "request", "plan", "receipt"}:
            raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_EVIDENCE_INVALID")
        if inner["kind"] != "transition-receipt" or inner["plan"] != plan:
            raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_EVIDENCE_MISMATCH")
        remote_canonical.validate_request(inner["request"])
        transition_protocol.validate_receipt(inner["receipt"], plan)
        expected_aggregate = {
            "kind": "authority-state",
            "authority": copy.deepcopy(inner["receipt"]["authority"]),
            "authorityRevision": inner["receipt"]["authorityRevision"],
            "stateHash": inner["receipt"]["readbackStateHash"],
            "receiptHash": inner["receipt"]["receiptHash"],
            "status": "PASS",
        }
        plan_hash = plan["planHash"]
    else:
        git_mutation_plan.validate(plan)
        inner = evidence
        required = {"kind", "plan", "observed"}
        if plan["operation"] == "create-branch":
            if not isinstance(inner, dict) or set(inner) != required:
                raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_EVIDENCE_INVALID")
            if inner["kind"] != "git-mutation-plan-readback" or inner["plan"] != plan:
                raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_EVIDENCE_MISMATCH")
            observed = _verify_git_plan_observed(plan, inner["observed"])
            expected_aggregate = {
                "kind": "branch-head",
                "branch": plan["target"]["branch"],
                "head": observed["sha"],
                "status": "PASS",
            }
        else:
            required = {
                "kind",
                "plan",
                "observed",
                "bundle",
                "providerReadback",
                "bundleReadback",
            }
            if not isinstance(inner, dict) or set(inner) != required:
                raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_EVIDENCE_INVALID")
            if inner["kind"] != "git-mutation-bundle-readback" or inner["plan"] != plan:
                raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_EVIDENCE_MISMATCH")
            _verify_git_plan_observed(plan, inner["observed"])
            bundle = git_mutation_bundle.validate_bundle(inner["bundle"])
            readback = git_mutation_bundle.verify_readback(bundle, inner["providerReadback"])
            if readback != inner["bundleReadback"]:
                raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_BUNDLE_READBACK_MISMATCH")
            expected_aggregate = {
                "kind": "git-bundle",
                "branch": readback["branch"],
                "branchHead": readback["branchHead"],
                "changedPaths": readback["changedPaths"],
                "readbackHash": readback["readbackHash"],
                "status": "PASS",
            }
        plan_hash = plan["planHash"]
    if aggregate_readback != expected_aggregate:
        raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_AGGREGATE_READBACK_MISMATCH")
    body = {
        "schemaVersion": RECEIPT_SCHEMA,
        "executionId": command["executionId"],
        "command": copy.deepcopy(command),
        "commandHash": command_hash(command),
        "route": route,
        "source": source_value,
        "planHash": plan_hash,
        "evidence": copy.deepcopy(evidence),
        "aggregateReadback": copy.deepcopy(expected_aggregate),
        "status": "PASS",
        "blockers": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "receiptHash": stable_hash(body)}


def validate_receipt(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RECEIPT_FIELDS:
        raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_RECEIPT_FIELDS_INVALID")
    if value.get("schemaVersion") != RECEIPT_SCHEMA:
        raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_RECEIPT_SCHEMA_UNSUPPORTED")
    command = validate_command(value.get("command"))
    if value.get("executionId") != command["executionId"]:
        raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_ID_MISMATCH")
    if value.get("commandHash") != command_hash(command):
        raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_COMMAND_HASH_MISMATCH")
    if value.get("status") != "PASS" or value.get("blockers") != []:
        raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_RECEIPT_STATUS_INVALID")
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_RECEIPT_MUST_NOT_AUTHORIZE")
    _source(value.get("source"))
    plan_hash = value.get("planHash")
    if not isinstance(plan_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_hash):
        raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_PLAN_HASH_INVALID")
    receipt_hash = value.get("receiptHash")
    if not isinstance(receipt_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", receipt_hash):
        raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_RECEIPT_HASH_INVALID")
    expected = build_receipt(
        command,
        source=value["source"],
        plan=value["evidence"]["plan"],
        evidence=value["evidence"],
        aggregate_readback=value["aggregateReadback"],
    )
    if value != expected:
        if stable_hash({key: copy.deepcopy(item) for key, item in value.items() if key != "receiptHash"}) != receipt_hash:
            raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_RECEIPT_HASH_MISMATCH")
        raise RemoteCanonicalExecutionError("REMOTE_EXECUTION_RECEIPT_MISMATCH")
    return value


def execute_command(
    command: dict[str, Any],
    *,
    source: dict[str, Any],
    transport: Any | None = None,
) -> dict[str, Any]:
    command = validate_command(command)
    carrier = transport or GhApiTransport()
    try:
        if command["kind"] == "domain":
            plan, evidence, aggregate = _execute_domain(command, carrier)
        else:
            plan, evidence, aggregate = _execute_git_direct(command, carrier)
        receipt = build_receipt(
            command,
            source=source,
            plan=plan,
            evidence=evidence,
            aggregate_readback=aggregate,
        )
        return validate_receipt(receipt)
    except RemoteCanonicalExecutionError:
        raise
    except Exception as exc:
        raise RemoteCanonicalExecutionError(_code(exc), str(exc)) from exc
