"""Read-only discovery of materialized Hosted Agent Cycles for one Work item.

This is deliberately pre-recovery: it discovers exact Work-bound begin lineage,
but never selects a cycle, authorizes replay, or mutates an authority.
"""
from __future__ import annotations

import copy
import json
from typing import Any

from tools import agent_cycle, hosted_agent_cycle, hosted_cycle_artifact, hosted_cycle_handle
from tools.canonical import stable_hash

LINEAGE_KIND = "work-bound-hosted-cycle-lineage-v0.1"
RESULT_FIELDS = {
    "schemaVersion", "requestId", "commandHash", "runId", "sourceSha",
    "artifactName", "cycleId", "cycleInstanceId", "contextHash",
    "carrierFeatures", "manifestHash", "handle", "status",
    "semanticAuthority", "authorizesMutation", "resumability", "resultHash",
}
LINEAGE_FIELDS = {
    "kind", "workRef", "issueNumber", "candidates", "pendingRequests",
    "ambiguous", "readOnly", "semanticAuthority", "authorizesMutation",
    "lineageHash",
}
REQUEST_MARKERS = (
    hosted_agent_cycle.REQUEST_MARKER,
    hosted_agent_cycle.REQUEST_MARKER_V02,
    hosted_agent_cycle.REQUEST_MARKER_V03,
    hosted_agent_cycle.REQUEST_MARKER_V04,
)


class HostedCycleLineageError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _positive_int(value: Any, code: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise HostedCycleLineageError(code)
    return value


def _hash(value: Any, code: str) -> str:
    if not isinstance(value, str) or hosted_agent_cycle.HASH_RE.fullmatch(value) is None:
        raise HostedCycleLineageError(code)
    return value


def _comment_id(comment: Any) -> int:
    if not isinstance(comment, dict):
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_COMMENT_INVALID")
    return _positive_int(comment.get("id"), "HOSTED_CYCLE_LINEAGE_COMMENT_INVALID")


def _body(comment: dict[str, Any]) -> str:
    body = comment.get("body")
    if not isinstance(body, str):
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_COMMENT_INVALID")
    return body


def _request_event(comment: dict[str, Any], issue_number: int) -> dict[str, Any]:
    return {
        "issue": {
            "number": issue_number,
            "title": hosted_agent_cycle.BUS_TITLE,
            "pull_request": None,
        },
        "comment": {
            "id": _comment_id(comment),
            "body": _body(comment),
            "author_association": comment.get("author_association"),
        },
        "repository": {"full_name": hosted_agent_cycle.REPOSITORY},
    }


def _result_payload(comment: dict[str, Any]) -> dict[str, Any] | None:
    """Return a parseable begin-result envelope without assigning it to a Work.

    Deep validation is intentionally deferred until requestId+commandHash claims
    a target Work request. Malformed or foreign ambient result records therefore
    cannot poison an unrelated Work reconstruction.
    """
    body = _body(comment)
    marker = hosted_agent_cycle.RESULT_MARKER + "\n"
    user = comment.get("user")
    if (
        not body.startswith(marker)
        or not isinstance(user, dict)
        or user.get("login") != "github-actions[bot]"
    ):
        return None
    try:
        value = json.loads(body[len(marker):].strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    if (
        value.get("schemaVersion") != hosted_cycle_artifact.BEGIN_RESULT_SCHEMA
        or value.get("status") != "READY"
    ):
        return None
    return value


def _validate_begin_result(
    value: Any, *, issue_number: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != RESULT_FIELDS:
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_BEGIN_RESULT_FIELDS_INVALID")
    if (
        value.get("schemaVersion") != hosted_cycle_artifact.BEGIN_RESULT_SCHEMA
        or value.get("status") != "READY"
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_BEGIN_RESULT_INVALID")
    if not isinstance(value.get("requestId"), str) or not value["requestId"].strip():
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_BEGIN_RESULT_INVALID")
    for field in ("commandHash", "contextHash", "manifestHash", "resultHash"):
        _hash(value.get(field), "HOSTED_CYCLE_LINEAGE_BEGIN_RESULT_HASH_INVALID")
    run_id = _positive_int(
        value.get("runId"), "HOSTED_CYCLE_LINEAGE_BEGIN_RESULT_INVALID"
    )
    source_sha = value.get("sourceSha")
    if not isinstance(source_sha, str) or hosted_agent_cycle.SHA_RE.fullmatch(source_sha) is None:
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_BEGIN_RESULT_INVALID")
    if value.get("artifactName") != f"agent-cycle-begin-{run_id}":
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_BEGIN_RESULT_BINDING_MISMATCH")
    if value.get("carrierFeatures") != hosted_agent_cycle.CURRENT_FEATURES:
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_BEGIN_RESULT_FEATURES_INVALID")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "resultHash"}
    if value["resultHash"] != stable_hash(core):
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_BEGIN_RESULT_HASH_MISMATCH")
    try:
        resumability = hosted_cycle_artifact.validate_projection(value.get("resumability"))
        handle, locator = hosted_cycle_handle.decode_handle(
            value.get("handle"), repository=hosted_agent_cycle.REPOSITORY
        )
    except RuntimeError as exc:
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_BEGIN_RESULT_BINDING_INVALID") from exc
    if resumability["state"] != "AVAILABLE":
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_BEGIN_NOT_RESUMABLE")
    expected_locator = {
        "runId": run_id,
        "sourceSha": source_sha,
        "artifactName": value["artifactName"],
        "contextHash": value["contextHash"],
        "cycleInstanceId": value["cycleInstanceId"],
    }
    if any(locator.get(key) != item for key, item in expected_locator.items()):
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_BEGIN_RESULT_BINDING_MISMATCH")
    if locator.get("issueNumber") != issue_number:
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_BEGIN_RESULT_ISSUE_MISMATCH")
    if handle.get("cycleId") != value.get("cycleId"):
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_BEGIN_RESULT_BINDING_MISMATCH")
    if (
        resumability.get("runId") != run_id
        or resumability.get("headSha") != source_sha
        or resumability.get("artifactName") != value["artifactName"]
    ):
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_RESUMABILITY_BINDING_MISMATCH")
    return value, locator


def build_work_lineage(
    comments: list[dict[str, Any]],
    *,
    work_ref: dict[str, str],
    issue_number: int,
) -> dict[str, Any]:
    """Join one exact Work selector to materialized Hosted begin results."""
    try:
        work_ref = agent_cycle.validate_work_ref(work_ref)
    except RuntimeError as exc:
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_WORK_REF_INVALID") from exc
    if work_ref is None:
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_WORK_REF_REQUIRED")
    issue_number = _positive_int(issue_number, "HOSTED_CYCLE_LINEAGE_ISSUE_INVALID")
    if not isinstance(comments, list):
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_COMMENTS_INVALID")

    ordered = sorted(comments, key=_comment_id)
    ids = [_comment_id(item) for item in ordered]
    if len(ids) != len(set(ids)):
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_COMMENT_DUPLICATE")

    requests: dict[int, dict[str, Any]] = {}
    for comment in ordered:
        body = _body(comment)
        if not any(body.startswith(marker + "\n") for marker in REQUEST_MARKERS):
            continue
        try:
            command, meta = hosted_agent_cycle.parse_event(
                _request_event(comment, issue_number)
            )
        except hosted_agent_cycle.HostedAgentCycleError as exc:
            raise HostedCycleLineageError(
                "HOSTED_CYCLE_LINEAGE_REQUEST_INVALID:" + exc.code
            ) from exc
        if (
            command.get("schemaVersion") not in {
                hosted_agent_cycle.COMMAND_SCHEMA_V03,
                hosted_agent_cycle.COMMAND_SCHEMA_V04,
            }
            or command.get("action") != "begin"
            or command.get("workRef") != work_ref
        ):
            continue
        requests[meta["commentId"]] = {
            "commentId": meta["commentId"],
            "requestId": command["requestId"],
            "commandHash": hosted_agent_cycle.transport_command_hash(command),
            "commandSchema": command["schemaVersion"],
        }

    target_claims = {
        (item["requestId"], item["commandHash"])
        for item in requests.values()
    }
    matched: dict[int, dict[str, Any]] = {}
    for comment in ordered:
        raw = _result_payload(comment)
        if raw is None:
            continue
        claim = (raw.get("requestId"), raw.get("commandHash"))
        if claim not in target_claims:
            continue
        result, locator = _validate_begin_result(raw, issue_number=issue_number)
        request_comment_id = locator["beginCommentId"]
        request = requests.get(request_comment_id)
        if request is None or claim != (request["requestId"], request["commandHash"]):
            raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_REQUEST_RESULT_MISMATCH")
        candidate = {
            "requestCommentId": request_comment_id,
            "resultCommentIds": [_comment_id(comment)],
            "requestId": result["requestId"],
            "commandHash": result["commandHash"],
            "runId": result["runId"],
            "sourceSha": result["sourceSha"],
            "artifactName": result["artifactName"],
            "cycleId": result["cycleId"],
            "cycleInstanceId": result["cycleInstanceId"],
            "contextHash": result["contextHash"],
            "handle": copy.deepcopy(result["handle"]),
            "resumability": copy.deepcopy(result["resumability"]),
            "resultHash": result["resultHash"],
        }
        previous = matched.get(request_comment_id)
        if previous is None:
            matched[request_comment_id] = candidate
        elif previous["resultHash"] == candidate["resultHash"]:
            previous["resultCommentIds"] = sorted(
                set(previous["resultCommentIds"] + candidate["resultCommentIds"])
            )
        else:
            raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_BEGIN_RESULT_AMBIGUOUS")

    candidates = [matched[key] for key in sorted(matched)]
    pending = [copy.deepcopy(requests[key]) for key in sorted(requests) if key not in matched]
    core = {
        "kind": LINEAGE_KIND,
        "workRef": copy.deepcopy(work_ref),
        "issueNumber": issue_number,
        "candidates": candidates,
        "pendingRequests": pending,
        "ambiguous": len(candidates) > 1,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "lineageHash": stable_hash(core)}


def validate_work_lineage(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != LINEAGE_FIELDS:
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_FIELDS_INVALID")
    if (
        value.get("kind") != LINEAGE_KIND
        or value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_BOUNDARY_INVALID")
    try:
        work_ref = agent_cycle.validate_work_ref(value.get("workRef"))
    except RuntimeError as exc:
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_WORK_REF_INVALID") from exc
    if work_ref is None:
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_WORK_REF_REQUIRED")
    _positive_int(value.get("issueNumber"), "HOSTED_CYCLE_LINEAGE_ISSUE_INVALID")
    candidates, pending = value.get("candidates"), value.get("pendingRequests")
    if not isinstance(candidates, list) or not isinstance(pending, list):
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_ENTRIES_INVALID")
    request_ids = [item.get("requestCommentId") for item in candidates if isinstance(item, dict)]
    pending_ids = [item.get("commentId") for item in pending if isinstance(item, dict)]
    if len(request_ids) != len(candidates) or request_ids != sorted(set(request_ids)):
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_CANDIDATES_INVALID")
    if len(pending_ids) != len(pending) or pending_ids != sorted(set(pending_ids)):
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_PENDING_INVALID")
    if set(request_ids) & set(pending_ids):
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_ENTRY_OVERLAP")
    if value.get("ambiguous") is not (len(candidates) > 1):
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_AMBIGUITY_INVALID")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "lineageHash"}
    if value.get("lineageHash") != stable_hash(core):
        raise HostedCycleLineageError("HOSTED_CYCLE_LINEAGE_HASH_MISMATCH")
    return value
