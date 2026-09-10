from __future__ import annotations

import copy
import json
import re
from typing import Any, Protocol
from urllib.parse import quote

from tools import continuation, git_mutation_plan, integration_reconcile
from tools.canonical import stable_hash
from tools.continuation_remote import GitHubContinuationAuthority
from tools.coordination_remote import ApiError, ApiResponse, GhApiTransport

REPOSITORY = "EAKerber/MobiliPresenter"
CONTROL_BRANCH = "main"
REQUEST_SCHEMA = "HostedDeliveryMergeRequest 0.1"
DISPATCH_SCHEMA = "DeliveryMergeDispatch 0.1"
RESULT_SCHEMA = "DeliveryMergeResult 0.1"
FAILURE_SCHEMA = "DeliveryMergeFailure 0.1"
MERGE_METHODS = {"squash"}
ACTIVE_WORK_STATUSES = {"READY", "IN_PROGRESS"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
REQUEST_FIELDS = {
    "schemaVersion", "requestId", "actor", "workId", "prNumber",
    "expectedWorkAuthorityHead", "expectedHeadSha", "expectedBase",
    "expectedTargetSha", "mergeMethod", "semanticAuthority", "authorizesMutation",
}
ACTOR_FIELDS = {"role", "workerId", "sessionId"}
DISPATCH_FIELDS = {
    "schemaVersion", "repository", "request", "requestHash", "work", "pr", "ci", "scope",
    "targetSha", "plan", "planHash", "mergeMethod", "semanticAuthority",
    "authorizesMutation", "dispatchHash",
}


class DeliveryMergeError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


class Transport(Protocol):
    def request(
        self,
        method: str,
        endpoint: str,
        *,
        payload: dict[str, Any] | None = None,
        include_headers: bool = False,
    ) -> ApiResponse: ...


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeliveryMergeError(code)
    return value.strip()


def _id(value: Any, code: str) -> str:
    value = _text(value, code)
    if ID_RE.fullmatch(value) is None:
        raise DeliveryMergeError(code)
    return value


def _sha(value: Any, code: str) -> str:
    if not isinstance(value, str) or SHA_RE.fullmatch(value) is None:
        raise DeliveryMergeError(code)
    return value


def _positive_int(value: Any, code: str) -> int:
    if type(value) is not int or value <= 0:
        raise DeliveryMergeError(code)
    return value


def _actor(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != ACTOR_FIELDS:
        raise DeliveryMergeError("DELIVERY_MERGE_ACTOR_INVALID")
    actor = {
        "role": _text(value.get("role"), "DELIVERY_MERGE_ACTOR_INVALID"),
        "workerId": _id(value.get("workerId"), "DELIVERY_MERGE_ACTOR_INVALID"),
        "sessionId": _id(value.get("sessionId"), "DELIVERY_MERGE_ACTOR_INVALID"),
    }
    if actor["role"] != "manager-gitops":
        raise DeliveryMergeError("DELIVERY_MERGE_ROLE_FORBIDDEN")
    return actor


def validate_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != REQUEST_FIELDS:
        raise DeliveryMergeError("DELIVERY_MERGE_REQUEST_FIELDS_INVALID")
    if value.get("schemaVersion") != REQUEST_SCHEMA:
        raise DeliveryMergeError("DELIVERY_MERGE_REQUEST_SCHEMA_UNSUPPORTED")
    canonical = {
        "schemaVersion": REQUEST_SCHEMA,
        "requestId": _id(value.get("requestId"), "DELIVERY_MERGE_REQUEST_ID_INVALID"),
        "actor": _actor(value.get("actor")),
        "workId": _id(value.get("workId"), "DELIVERY_MERGE_WORK_ID_INVALID"),
        "prNumber": _positive_int(value.get("prNumber"), "DELIVERY_MERGE_PR_NUMBER_INVALID"),
        "expectedWorkAuthorityHead": _sha(
            value.get("expectedWorkAuthorityHead"), "DELIVERY_MERGE_WORK_AUTHORITY_INVALID"
        ),
        "expectedHeadSha": _sha(value.get("expectedHeadSha"), "DELIVERY_MERGE_HEAD_INVALID"),
        "expectedBase": _text(value.get("expectedBase"), "DELIVERY_MERGE_BASE_INVALID"),
        "expectedTargetSha": _sha(
            value.get("expectedTargetSha"), "DELIVERY_MERGE_TARGET_INVALID"
        ),
        "mergeMethod": _text(value.get("mergeMethod"), "DELIVERY_MERGE_METHOD_INVALID"),
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    if canonical["expectedBase"] != CONTROL_BRANCH:
        raise DeliveryMergeError("DELIVERY_MERGE_BASE_FORBIDDEN")
    if canonical["mergeMethod"] not in MERGE_METHODS:
        raise DeliveryMergeError("DELIVERY_MERGE_METHOD_INVALID")
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise DeliveryMergeError("DELIVERY_MERGE_REQUEST_MUST_NOT_AUTHORIZE")
    if value != canonical:
        raise DeliveryMergeError("DELIVERY_MERGE_REQUEST_NOT_CANONICAL")
    return value


def request_hash(request: dict[str, Any]) -> str:
    return stable_hash(validate_request(request))


def _json(response: ApiResponse, code: str) -> Any:
    try:
        return json.loads(response.body)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise DeliveryMergeError(code) from exc


def _request(transport: Transport, method: str, endpoint: str, *, payload=None) -> Any:
    try:
        return _json(transport.request(method, endpoint, payload=payload), "DELIVERY_MERGE_PROVIDER_RESPONSE_INVALID")
    except ApiError as exc:
        raise DeliveryMergeError("DELIVERY_MERGE_PROVIDER_UNAVAILABLE", exc.detail) from exc


def _observe_pr(transport: Transport, pr_number: int) -> dict[str, Any]:
    raw = _request(transport, "GET", f"repos/{REPOSITORY}/pulls/{pr_number}")
    if not isinstance(raw, dict):
        raise DeliveryMergeError("DELIVERY_MERGE_PR_OBSERVATION_INVALID")
    head = raw.get("head") or {}
    base = raw.get("base") or {}
    head_repo = head.get("repo") or {}
    value = {
        "number": raw.get("number"),
        "state": raw.get("state"),
        "draft": raw.get("draft"),
        "merged": raw.get("merged"),
        "headSha": head.get("sha"),
        "headRef": head.get("ref"),
        "headRepository": head_repo.get("full_name"),
        "baseRef": base.get("ref"),
        "mergeCommitSha": raw.get("merge_commit_sha"),
    }
    if (
        value["number"] != pr_number
        or not isinstance(value["headRef"], str)
        or not isinstance(value["baseRef"], str)
        or not isinstance(value["headRepository"], str)
    ):
        raise DeliveryMergeError("DELIVERY_MERGE_PR_OBSERVATION_INVALID")
    _sha(value["headSha"], "DELIVERY_MERGE_PR_OBSERVATION_INVALID")
    return value


def _observe_ref(transport: Transport, branch: str) -> str:
    raw = _request(
        transport,
        "GET",
        f"repos/{REPOSITORY}/git/ref/heads/{quote(branch, safe='/')}",
    )
    if not isinstance(raw, dict):
        raise DeliveryMergeError("DELIVERY_MERGE_REF_OBSERVATION_INVALID")
    return _sha((raw.get("object") or {}).get("sha"), "DELIVERY_MERGE_REF_OBSERVATION_INVALID")


def _observe_ci(transport: Transport, head_sha: str, head_ref: str) -> dict[str, Any]:
    raw = _request(
        transport,
        "GET",
        f"repos/{REPOSITORY}/actions/runs?head_sha={head_sha}&per_page=100",
    )
    runs = raw.get("workflow_runs") if isinstance(raw, dict) else None
    if not isinstance(runs, list):
        raise DeliveryMergeError("DELIVERY_MERGE_CI_OBSERVATION_INVALID")
    normalized = []
    for run in runs:
        if not isinstance(run, dict):
            raise DeliveryMergeError("DELIVERY_MERGE_CI_OBSERVATION_INVALID")
        normalized.append({
            "name": run.get("name"),
            "id": run.get("id"),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
        })
    try:
        return integration_reconcile.aggregate_ci(normalized, head_sha, head_ref)
    except RuntimeError as exc:
        raise DeliveryMergeError("DELIVERY_MERGE_CI_OBSERVATION_INVALID", str(exc)) from exc


def _observe_changed_files(transport: Transport, pr_number: int) -> list[str]:
    files: list[str] = []
    page = 1
    while True:
        raw = _request(
            transport,
            "GET",
            f"repos/{REPOSITORY}/pulls/{pr_number}/files?per_page=100&page={page}",
        )
        if not isinstance(raw, list):
            raise DeliveryMergeError("DELIVERY_MERGE_FILES_OBSERVATION_INVALID")
        for item in raw:
            filename = item.get("filename") if isinstance(item, dict) else None
            if not isinstance(filename, str) or not filename:
                raise DeliveryMergeError("DELIVERY_MERGE_FILES_OBSERVATION_INVALID")
            files.append(filename)
        if len(raw) < 100:
            return sorted(set(files))
        page += 1


def _observe_merge_commit_parent(transport: Transport, merged_sha: str) -> str:
    raw = _request(transport, "GET", f"repos/{REPOSITORY}/git/commits/{merged_sha}")
    parents = raw.get("parents") if isinstance(raw, dict) else None
    if not isinstance(parents, list) or len(parents) != 1:
        raise DeliveryMergeError("DELIVERY_MERGE_COMMIT_PARENT_INVALID")
    return _sha((parents[0] or {}).get("sha"), "DELIVERY_MERGE_COMMIT_PARENT_INVALID")


def _target_contains_merge(transport: Transport, merged_sha: str, target_sha: str) -> bool:
    if target_sha == merged_sha:
        return True
    raw = _request(
        transport,
        "GET",
        f"repos/{REPOSITORY}/compare/{merged_sha}...{target_sha}",
    )
    if not isinstance(raw, dict):
        raise DeliveryMergeError("DELIVERY_MERGE_TARGET_CONTAINMENT_INVALID")
    merge_base = raw.get("merge_base_commit") or {}
    return raw.get("status") in {"ahead", "identical"} and merge_base.get("sha") == merged_sha


def _observe_work(transport: Transport, request: dict[str, Any]) -> dict[str, Any]:
    try:
        observation = GitHubContinuationAuthority(transport=transport, repository=REPOSITORY).observe()
    except RuntimeError as exc:
        raise DeliveryMergeError("DELIVERY_MERGE_WORK_OBSERVATION_UNAVAILABLE", str(exc)) from exc
    if observation.head_sha != request["expectedWorkAuthorityHead"]:
        raise DeliveryMergeError("DELIVERY_MERGE_WORK_AUTHORITY_DRIFT")
    work = observation.items.get(request["workId"])
    if work is None:
        raise DeliveryMergeError("DELIVERY_MERGE_WORK_MISSING")
    continuation.require_current(work, request["workId"])
    if work["status"] not in ACTIVE_WORK_STATUSES:
        raise DeliveryMergeError("DELIVERY_MERGE_WORK_NOT_ACTIVE")
    if work["prNumber"] != request["prNumber"] or not isinstance(work["branch"], str):
        raise DeliveryMergeError("DELIVERY_MERGE_WORK_BINDING_MISMATCH")
    return {
        "authorityHead": observation.head_sha,
        "id": work["id"],
        "workerId": work["workerId"],
        "status": work["status"],
        "branch": work["branch"],
        "prNumber": work["prNumber"],
        "stateHash": continuation.state_hash(work),
    }


def _snapshot(request: dict[str, Any], transport: Transport) -> dict[str, Any]:
    work = _observe_work(transport, request)
    pr = _observe_pr(transport, request["prNumber"])
    if pr["state"] != "open" or pr["draft"] is not False or pr["merged"] is not False:
        raise DeliveryMergeError("DELIVERY_MERGE_PR_NOT_OPEN_READY")
    if pr["headRepository"] != REPOSITORY:
        raise DeliveryMergeError("DELIVERY_MERGE_CROSS_REPOSITORY_FORBIDDEN")
    if pr["headSha"] != request["expectedHeadSha"]:
        raise DeliveryMergeError("DELIVERY_MERGE_PR_HEAD_DRIFT")
    if pr["baseRef"] != request["expectedBase"]:
        raise DeliveryMergeError("DELIVERY_MERGE_PR_BASE_DRIFT")
    if pr["headRef"] != work["branch"]:
        raise DeliveryMergeError("DELIVERY_MERGE_WORK_BRANCH_MISMATCH")
    target = _observe_ref(transport, CONTROL_BRANCH)
    if target != request["expectedTargetSha"]:
        raise DeliveryMergeError("DELIVERY_MERGE_TARGET_DRIFT")
    changed_files = _observe_changed_files(transport, request["prNumber"])
    scope = integration_reconcile.boundary_assessment(work["branch"], changed_files)
    if scope["boundaryViolations"]:
        raise DeliveryMergeError("DELIVERY_MERGE_BOUNDARY_VIOLATION")
    ci = _observe_ci(transport, request["expectedHeadSha"], work["branch"])
    if ci["status"] != "green":
        raise DeliveryMergeError(f"DELIVERY_MERGE_CI_{ci['status'].upper()}")
    plan = git_mutation_plan.merge_pr(
        pr_number=request["prNumber"],
        head_sha=request["expectedHeadSha"],
        base=request["expectedBase"],
        control_branch=CONTROL_BRANCH,
        merge_method=request["mergeMethod"],
    )
    git_mutation_plan.validate(plan)
    return {
        "work": work,
        "pr": pr,
        "targetSha": target,
        "ci": ci,
        "scope": {"changedFiles": changed_files, **scope},
        "plan": plan,
    }


def prepare(request: dict[str, Any], transport: Transport | None = None) -> dict[str, Any]:
    request = validate_request(request)
    transport = transport or GhApiTransport()
    observed = _snapshot(request, transport)
    body = {
        "schemaVersion": DISPATCH_SCHEMA,
        "repository": REPOSITORY,
        "request": copy.deepcopy(request),
        "requestHash": request_hash(request),
        "work": observed["work"],
        "pr": observed["pr"],
        "ci": observed["ci"],
        "scope": observed["scope"],
        "targetSha": observed["targetSha"],
        "plan": observed["plan"],
        "planHash": observed["plan"]["planHash"],
        "mergeMethod": request["mergeMethod"],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "dispatchHash": stable_hash(body)}


def validate_dispatch(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != DISPATCH_FIELDS:
        raise DeliveryMergeError("DELIVERY_MERGE_DISPATCH_INVALID")
    if (
        value.get("schemaVersion") != DISPATCH_SCHEMA
        or value.get("repository") != REPOSITORY
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise DeliveryMergeError("DELIVERY_MERGE_DISPATCH_INVALID")
    validate_request(value.get("request"))
    if value.get("requestHash") != request_hash(value["request"]):
        raise DeliveryMergeError("DELIVERY_MERGE_DISPATCH_REQUEST_HASH_MISMATCH")
    plan = value.get("plan")
    try:
        git_mutation_plan.validate(plan)
    except RuntimeError as exc:
        raise DeliveryMergeError("DELIVERY_MERGE_DISPATCH_PLAN_INVALID") from exc
    if plan.get("operation") != "merge-pr" or value.get("planHash") != plan.get("planHash"):
        raise DeliveryMergeError("DELIVERY_MERGE_DISPATCH_PLAN_INVALID")
    body = {key: copy.deepcopy(item) for key, item in value.items() if key != "dispatchHash"}
    if value.get("dispatchHash") != stable_hash(body):
        raise DeliveryMergeError("DELIVERY_MERGE_DISPATCH_HASH_MISMATCH")
    return value


def _same_dispatch(before: dict[str, Any], after: dict[str, Any]) -> None:
    keys = ("requestHash", "work", "pr", "ci", "scope", "targetSha", "planHash", "mergeMethod")
    if any(before.get(key) != after.get(key) for key in keys):
        raise DeliveryMergeError("DELIVERY_MERGE_PRECONDITION_DRIFT")


def execute(dispatch: dict[str, Any], transport: Transport | None = None) -> dict[str, Any]:
    dispatch = validate_dispatch(dispatch)
    transport = transport or GhApiTransport()
    current = prepare(dispatch.get("request"), transport)
    _same_dispatch(dispatch, current)
    request = current["request"]
    raw = _request(
        transport,
        "PUT",
        f"repos/{REPOSITORY}/pulls/{request['prNumber']}/merge",
        payload={"sha": request["expectedHeadSha"], "merge_method": request["mergeMethod"]},
    )
    if raw.get("merged") is not True:
        raise DeliveryMergeError("DELIVERY_MERGE_PROVIDER_REJECTED", str(raw.get("message") or ""))
    merged_sha = _sha(raw.get("sha"), "DELIVERY_MERGE_PROVIDER_RESULT_INVALID")
    pr_after = _observe_pr(transport, request["prNumber"])
    target_after = _observe_ref(transport, CONTROL_BRANCH)
    parent_sha = _observe_merge_commit_parent(transport, merged_sha)
    if parent_sha != request["expectedTargetSha"]:
        raise DeliveryMergeError("DELIVERY_MERGE_TARGET_PARENT_DRIFT")
    if (
        pr_after["merged"] is not True
        or pr_after["state"] != "closed"
        or pr_after["headSha"] != request["expectedHeadSha"]
        or pr_after["baseRef"] != request["expectedBase"]
        or pr_after["mergeCommitSha"] != merged_sha
    ):
        raise DeliveryMergeError("DELIVERY_MERGE_PR_READBACK_MISMATCH")
    target_contains_merge = _target_contains_merge(transport, merged_sha, target_after)
    if not target_contains_merge:
        raise DeliveryMergeError("DELIVERY_MERGE_TARGET_READBACK_MISMATCH")
    body = {
        "schemaVersion": RESULT_SCHEMA,
        "repository": REPOSITORY,
        "requestId": request["requestId"],
        "requestHash": current["requestHash"],
        "dispatchHash": current["dispatchHash"],
        "planHash": current["planHash"],
        "work": copy.deepcopy(current["work"]),
        "prNumber": request["prNumber"],
        "expectedHeadSha": request["expectedHeadSha"],
        "beforeTargetSha": request["expectedTargetSha"],
        "mergedSha": merged_sha,
        "afterTargetSha": target_after,
        "mergedCommitParentSha": parent_sha,
        "targetContainsMergedSha": target_contains_merge,
        "mergeMethod": request["mergeMethod"],
        "ci": copy.deepcopy(current["ci"]),
        "status": "PASS",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "resultHash": stable_hash(body)}


def failure(exc: BaseException, request: dict[str, Any] | None = None) -> dict[str, Any]:
    code = getattr(exc, "code", None)
    if not isinstance(code, str) or not code:
        code = str(exc).split(":", 1)[0] or "DELIVERY_MERGE_UNEXPECTED_FAILURE"
    body = {
        "schemaVersion": FAILURE_SCHEMA,
        "requestId": request.get("requestId") if isinstance(request, dict) else None,
        "requestHash": stable_hash(request) if isinstance(request, dict) else None,
        "status": "BLOCKED",
        "blockers": [code],
        "detail": str(exc),
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "failureHash": stable_hash(body)}
