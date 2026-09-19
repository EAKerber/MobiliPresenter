from __future__ import annotations

import copy
import hashlib
import re
from typing import Any

from tools.canonical import stable_hash

SCHEMA = "ProviderHostActionPlan 0.1"
TOOL_SURFACE = "github-connector-tools"
OPERATIONS = {"issue-comment.create", "workflow-run.rerun"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
FIELDS = {
    "schemaVersion",
    "toolSurface",
    "operation",
    "requiredFeature",
    "request",
    "preconditions",
    "readback",
    "readOnly",
    "semanticAuthority",
    "authorizesMutation",
    "planHash",
}


class ProviderHostActionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderHostActionError(code)
    return value.strip()


def _positive_int(value: Any, code: str) -> int:
    if type(value) is not int or value <= 0:
        raise ProviderHostActionError(code)
    return value


def _sha(value: Any, code: str) -> str:
    if not isinstance(value, str) or SHA_RE.fullmatch(value) is None:
        raise ProviderHostActionError(code)
    return value


def _body_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _finish(
    *,
    operation: str,
    required_feature: str,
    request: dict[str, Any],
    preconditions: dict[str, Any],
    readback: dict[str, Any],
) -> dict[str, Any]:
    if operation not in OPERATIONS:
        raise ProviderHostActionError("PROVIDER_HOST_ACTION_OPERATION_UNSUPPORTED")
    core = {
        "schemaVersion": SCHEMA,
        "toolSurface": TOOL_SURFACE,
        "operation": operation,
        "requiredFeature": _text(
            required_feature, "PROVIDER_HOST_ACTION_FEATURE_REQUIRED"
        ),
        "request": copy.deepcopy(request),
        "preconditions": copy.deepcopy(preconditions),
        "readback": copy.deepcopy(readback),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "planHash": stable_hash(core)}


def issue_comment(
    *,
    repository: str,
    issue_number: int,
    body: str,
    required_feature: str = "issue-comment-create",
) -> dict[str, Any]:
    repository = _text(repository, "PROVIDER_HOST_ACTION_REPOSITORY_REQUIRED")
    issue_number = _positive_int(
        issue_number, "PROVIDER_HOST_ACTION_ISSUE_NUMBER_INVALID"
    )
    body = _text(body, "PROVIDER_HOST_ACTION_COMMENT_BODY_REQUIRED")
    digest = _body_hash(body)
    return _finish(
        operation="issue-comment.create",
        required_feature=required_feature,
        request={
            "method": "POST",
            "endpoint": f"repos/{repository}/issues/{issue_number}/comments",
            "payload": {"body": body},
        },
        preconditions={
            "repository": repository,
            "issueNumber": issue_number,
            "bodySha256": digest,
        },
        readback={
            "kind": "issue-comment-body",
            "repository": repository,
            "issueNumber": issue_number,
            "expectedBodySha256": digest,
        },
    )


def workflow_rerun(
    *,
    repository: str,
    run_id: int,
    head_sha: str,
    run_attempt: int,
) -> dict[str, Any]:
    repository = _text(repository, "PROVIDER_HOST_ACTION_REPOSITORY_REQUIRED")
    run_id = _positive_int(run_id, "PROVIDER_HOST_ACTION_RUN_ID_INVALID")
    head_sha = _sha(head_sha, "PROVIDER_HOST_ACTION_HEAD_SHA_INVALID")
    run_attempt = _positive_int(
        run_attempt, "PROVIDER_HOST_ACTION_RUN_ATTEMPT_INVALID"
    )
    return _finish(
        operation="workflow-run.rerun",
        required_feature="workflow-run-rerun",
        request={
            "method": "POST",
            "endpoint": f"repos/{repository}/actions/runs/{run_id}/rerun",
            "payload": None,
        },
        preconditions={
            "repository": repository,
            "runId": run_id,
            "headSha": head_sha,
            "runAttempt": run_attempt,
        },
        readback={
            "kind": "workflow-run-attempt",
            "repository": repository,
            "runId": run_id,
            "expectedHeadSha": head_sha,
            "minimumRunAttempt": run_attempt + 1,
        },
    )


def validate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ProviderHostActionError("PROVIDER_HOST_ACTION_FIELDS_INVALID")
    if (
        value.get("schemaVersion") != SCHEMA
        or value.get("toolSurface") != TOOL_SURFACE
        or value.get("operation") not in OPERATIONS
    ):
        raise ProviderHostActionError("PROVIDER_HOST_ACTION_CONTRACT_INVALID")
    if (
        value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise ProviderHostActionError("PROVIDER_HOST_ACTION_BOUNDARY_INVALID")
    _text(value.get("requiredFeature"), "PROVIDER_HOST_ACTION_FEATURE_REQUIRED")
    request = value.get("request")
    preconditions = value.get("preconditions")
    readback = value.get("readback")
    if not all(isinstance(item, dict) for item in (request, preconditions, readback)):
        raise ProviderHostActionError("PROVIDER_HOST_ACTION_PAYLOAD_INVALID")

    operation = value["operation"]
    if operation == "issue-comment.create":
        repository = _text(
            preconditions.get("repository"),
            "PROVIDER_HOST_ACTION_REPOSITORY_REQUIRED",
        )
        issue_number = _positive_int(
            preconditions.get("issueNumber"),
            "PROVIDER_HOST_ACTION_ISSUE_NUMBER_INVALID",
        )
        payload = request.get("payload")
        body = payload.get("body") if isinstance(payload, dict) else None
        if (
            request.get("method") != "POST"
            or request.get("endpoint")
            != f"repos/{repository}/issues/{issue_number}/comments"
            or not isinstance(body, str)
            or preconditions.get("bodySha256") != _body_hash(body)
            or readback
            != {
                "kind": "issue-comment-body",
                "repository": repository,
                "issueNumber": issue_number,
                "expectedBodySha256": _body_hash(body),
            }
        ):
            raise ProviderHostActionError("PROVIDER_HOST_ACTION_SEMANTICS_INVALID")
    else:
        repository = _text(
            preconditions.get("repository"),
            "PROVIDER_HOST_ACTION_REPOSITORY_REQUIRED",
        )
        run_id = _positive_int(
            preconditions.get("runId"), "PROVIDER_HOST_ACTION_RUN_ID_INVALID"
        )
        head_sha = _sha(
            preconditions.get("headSha"),
            "PROVIDER_HOST_ACTION_HEAD_SHA_INVALID",
        )
        run_attempt = _positive_int(
            preconditions.get("runAttempt"),
            "PROVIDER_HOST_ACTION_RUN_ATTEMPT_INVALID",
        )
        if (
            request
            != {
                "method": "POST",
                "endpoint": f"repos/{repository}/actions/runs/{run_id}/rerun",
                "payload": None,
            }
            or readback
            != {
                "kind": "workflow-run-attempt",
                "repository": repository,
                "runId": run_id,
                "expectedHeadSha": head_sha,
                "minimumRunAttempt": run_attempt + 1,
            }
        ):
            raise ProviderHostActionError("PROVIDER_HOST_ACTION_SEMANTICS_INVALID")

    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "planHash"}
    if value.get("planHash") != stable_hash(core):
        raise ProviderHostActionError("PROVIDER_HOST_ACTION_HASH_MISMATCH")
    return value
