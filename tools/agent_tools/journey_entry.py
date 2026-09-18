from __future__ import annotations

import copy
import json
from typing import Any

from tools import (
    agent_cycle_identity,
    agent_failure,
    continuation_remote,
    hosted_agent_cycle,
    hosted_cycle_artifact,
    hosted_cycle_handle,
)
from tools.canonical import stable_hash

RESULT_SCHEMA = "JourneyEntryComposition 0.2"
BEGIN_RESULT_SCHEMA = hosted_cycle_artifact.BEGIN_RESULT_SCHEMA
STATUSES = {"PASS", "PENDING", "BLOCKED", "UNKNOWN"}
DISPOSITIONS = {"BUILD_ONLY", "REQUESTED", "REQUEST_PENDING", "REUSED", "OBSERVED_FAILURE"}


class JourneyEntryError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise JourneyEntryError(code)
    return value.strip()


def _json_response(response: Any, code: str) -> Any:
    try:
        return json.loads(response.body)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise JourneyEntryError(code) from exc


def _marker_payload(body: Any, marker: str) -> Any | None:
    prefix = marker + "\n"
    if not isinstance(body, str) or not body.startswith(prefix):
        return None
    raw = body[len(prefix):].strip()
    if raw.startswith("```json") and raw.endswith("```"):
        raw = raw[len("```json"):-len("```")].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _bus_issue(transport: Any) -> int:
    matches: list[int] = []
    for page in range(1, 101):
        value = _json_response(
            transport.request(
                "GET",
                f"repos/{hosted_agent_cycle.REPOSITORY}/issues?state=open&per_page=100&page={page}",
            ),
            "JOURNEY_ENTRY_BUS_ISSUES_INVALID",
        )
        if not isinstance(value, list):
            raise JourneyEntryError("JOURNEY_ENTRY_BUS_ISSUES_INVALID")
        for issue in value:
            if not isinstance(issue, dict):
                continue
            number = issue.get("number")
            if (
                issue.get("title") == hosted_agent_cycle.BUS_TITLE
                and issue.get("pull_request") is None
                and isinstance(number, int)
                and not isinstance(number, bool)
                and number > 0
            ):
                matches.append(number)
        if len(value) < 100:
            break
    if len(matches) != 1:
        raise JourneyEntryError(
            "JOURNEY_ENTRY_BUS_MISSING" if not matches else "JOURNEY_ENTRY_BUS_AMBIGUOUS"
        )
    return matches[0]


def _comments(transport: Any, issue_number: int) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    for page in range(1, 101):
        value = _json_response(
            transport.request(
                "GET",
                f"repos/{hosted_agent_cycle.REPOSITORY}/issues/{issue_number}/comments?per_page=100&page={page}",
            ),
            "JOURNEY_ENTRY_COMMENTS_INVALID",
        )
        if not isinstance(value, list):
            raise JourneyEntryError("JOURNEY_ENTRY_COMMENTS_INVALID")
        comments.extend(item for item in value if isinstance(item, dict))
        if len(value) < 100:
            return comments
    raise JourneyEntryError("JOURNEY_ENTRY_COMMENTS_UNBOUNDED")


def _work(work_id: str, transport: Any) -> dict[str, Any]:
    work_id = _text(work_id, "JOURNEY_ENTRY_WORK_ID_INVALID")
    try:
        observed = continuation_remote.GitHubContinuationAuthority(
            transport=transport,
            repository=hosted_agent_cycle.REPOSITORY,
        ).observe()
    except Exception as exc:
        raise JourneyEntryError("JOURNEY_ENTRY_WORK_OBSERVATION_FAILED") from exc
    work = observed.items.get(work_id)
    if not isinstance(work, dict):
        raise JourneyEntryError("JOURNEY_ENTRY_WORK_MISSING")
    if work.get("status") not in {"READY", "IN_PROGRESS"}:
        raise JourneyEntryError("JOURNEY_ENTRY_WORK_NOT_ACTIVE")
    worker_id = work.get("workerId")
    if not isinstance(worker_id, str) or not worker_id.strip():
        raise JourneyEntryError("JOURNEY_ENTRY_WORK_WORKER_INVALID")
    return copy.deepcopy(work)


def _identity(*, role: str, declared_intent: str, work_id: str, worker_id: str) -> tuple[str, dict[str, str]]:
    role = _text(role, "JOURNEY_ENTRY_ROLE_INVALID")
    intent = _text(declared_intent, "JOURNEY_ENTRY_INTENT_INVALID")
    digest = stable_hash({
        "repository": hosted_agent_cycle.REPOSITORY,
        "role": role,
        "declaredIntent": intent,
        "workId": work_id,
        "workerId": worker_id,
    })
    actor = agent_cycle_identity.canonical_actor({
        "role": role,
        "workerId": worker_id,
        "sessionId": "journey-entry-" + digest[:24],
    })
    return "journey-begin-" + digest[:24], actor


def build_begin_request(
    *,
    role: str,
    declared_intent: str,
    work_id: str,
    worker_id: str,
    tool_surfaces: list[str],
    inventory_complete: bool,
) -> dict[str, Any]:
    request_id, actor = _identity(
        role=role,
        declared_intent=declared_intent,
        work_id=work_id,
        worker_id=worker_id,
    )
    value = {
        "schemaVersion": hosted_agent_cycle.COMMAND_SCHEMA_V04,
        "requestId": request_id,
        "action": "begin",
        "actor": actor,
        "declaredIntent": declared_intent.strip(),
        "machineScope": "live",
        "workRef": {"workId": work_id},
        "runtimeEnvironment": {
            "toolSurfaces": sorted(tool_surfaces),
            "inventoryComplete": inventory_complete,
        },
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    try:
        return hosted_agent_cycle.validate_runtime_begin_command(value)
    except hosted_agent_cycle.HostedAgentCycleError as exc:
        raise JourneyEntryError("JOURNEY_ENTRY_BEGIN_REQUEST_INVALID", exc.code) from exc


def _find_request(comments: list[dict[str, Any]], command: dict[str, Any]) -> int | None:
    exact: list[int] = []
    conflict = False
    for comment in comments:
        if comment.get("author_association") != "OWNER":
            continue
        value = _marker_payload(comment.get("body"), hosted_agent_cycle.REQUEST_MARKER_V04)
        if not isinstance(value, dict) or value.get("requestId") != command["requestId"]:
            continue
        comment_id = comment.get("id")
        if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id <= 0:
            raise JourneyEntryError("JOURNEY_ENTRY_REQUEST_COMMENT_INVALID")
        if value == command:
            exact.append(comment_id)
        else:
            conflict = True
    if conflict:
        raise JourneyEntryError("JOURNEY_ENTRY_REQUEST_ID_CONFLICT")
    if len(exact) > 1:
        raise JourneyEntryError("JOURNEY_ENTRY_REQUEST_DUPLICATE")
    return exact[0] if exact else None


def _observe_result(
    comments: list[dict[str, Any]],
    *,
    command: dict[str, Any],
) -> tuple[str, int | None, dict[str, Any] | None, list[str]]:
    expected_hash = hosted_agent_cycle.transport_command_hash(command)
    candidates: list[tuple[int, dict[str, Any]]] = []
    for comment in comments:
        user = comment.get("user") if isinstance(comment, dict) else None
        if not isinstance(user, dict) or user.get("login") != "github-actions[bot]":
            continue
        value = _marker_payload(comment.get("body"), hosted_agent_cycle.RESULT_MARKER)
        if not isinstance(value, dict) or value.get("requestId") != command["requestId"]:
            continue
        if value.get("commandHash") != expected_hash:
            raise JourneyEntryError("JOURNEY_ENTRY_RESULT_COMMAND_MISMATCH")
        comment_id = comment.get("id")
        if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id <= 0:
            raise JourneyEntryError("JOURNEY_ENTRY_RESULT_COMMENT_INVALID")
        candidates.append((comment_id, value))
    if not candidates:
        return "PENDING", None, None, []
    result_comment_id, result = sorted(candidates, key=lambda item: item[0])[-1]
    if result.get("schemaVersion") == BEGIN_RESULT_SCHEMA and result.get("status") == "READY":
        try:
            handle, _ = hosted_cycle_handle.decode_handle(
                result.get("handle"), repository=hosted_agent_cycle.REPOSITORY
            )
        except RuntimeError as exc:
            raise JourneyEntryError("JOURNEY_ENTRY_BEGIN_HANDLE_INVALID") from exc
        if handle.get("actor") != command["actor"]:
            raise JourneyEntryError("JOURNEY_ENTRY_BEGIN_ACTOR_MISMATCH")
        return "PASS", result_comment_id, copy.deepcopy(handle), []
    try:
        failure = agent_failure.validate_hosted_cycle_failure(result)
    except RuntimeError as exc:
        raise JourneyEntryError("JOURNEY_ENTRY_RESULT_INVALID") from exc
    core = failure["failureCore"]
    status = "UNKNOWN" if core.get("status") == "UNKNOWN" else "BLOCKED"
    blockers = sorted({
        item.get("code")
        for item in core.get("causes") or []
        if isinstance(item, dict) and isinstance(item.get("code"), str)
    })
    return status, result_comment_id, None, blockers


def _result(
    *, status: str, disposition: str, work_id: str, request: dict[str, Any],
    request_comment_id: int | None, result_comment_id: int | None,
    handle: dict[str, Any] | None, blockers: list[str], submitted: bool,
) -> dict[str, Any]:
    if status not in STATUSES or disposition not in DISPOSITIONS:
        raise JourneyEntryError("JOURNEY_ENTRY_RESULT_INVALID")
    core = {
        "schemaVersion": RESULT_SCHEMA,
        "status": status,
        "disposition": disposition,
        "workId": work_id,
        "request": copy.deepcopy(request),
        "requestCommentId": request_comment_id,
        "resultCommentId": result_comment_id,
        "handle": copy.deepcopy(handle),
        "blockers": sorted(set(blockers)),
        "submitted": submitted,
        "readOnly": not submitted,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "resultHash": stable_hash(core)}


def compose_entry(
    *,
    role: str,
    declared_intent: str,
    work_id: str,
    tool_surfaces: list[str],
    inventory_complete: bool,
    submit: bool = False,
    transport: Any | None = None,
) -> dict[str, Any]:
    if inventory_complete is not True:
        return _result(
            status="UNKNOWN", disposition="BUILD_ONLY", work_id=work_id,
            request={}, request_comment_id=None, result_comment_id=None,
            handle=None, blockers=["TOOL_SURFACE_INVENTORY_INCOMPLETE"], submitted=False,
        )
    if transport is None:
        return _result(
            status="UNKNOWN", disposition="BUILD_ONLY", work_id=work_id,
            request={}, request_comment_id=None, result_comment_id=None,
            handle=None, blockers=["BLOCKED_EXECUTION_SURFACE"], submitted=False,
        )
    carrier = transport
    work = _work(work_id, carrier)
    command = build_begin_request(
        role=role,
        declared_intent=declared_intent,
        work_id=work_id,
        worker_id=work["workerId"],
        tool_surfaces=tool_surfaces,
        inventory_complete=True,
    )
    issue_number = _bus_issue(carrier)
    comments = _comments(carrier, issue_number)
    request_comment_id = _find_request(comments, command)
    if request_comment_id is not None:
        status, result_comment_id, handle, blockers = _observe_result(
            comments, command=command
        )
        disposition = (
            "REUSED" if status == "PASS"
            else "OBSERVED_FAILURE" if status in {"BLOCKED", "UNKNOWN"}
            else "REQUEST_PENDING"
        )
        return _result(
            status=status, disposition=disposition, work_id=work_id, request=command,
            request_comment_id=request_comment_id, result_comment_id=result_comment_id,
            handle=handle, blockers=blockers, submitted=False,
        )
    if not submit:
        return _result(
            status="PENDING", disposition="BUILD_ONLY", work_id=work_id, request=command,
            request_comment_id=None, result_comment_id=None, handle=None, blockers=[], submitted=False,
        )
    response = carrier.request(
        "POST",
        f"repos/{hosted_agent_cycle.REPOSITORY}/issues/{issue_number}/comments",
        payload={"body": hosted_agent_cycle.REQUEST_MARKER_V04 + "\n" + json.dumps(command, separators=(",", ":"))},
    )
    value = _json_response(response, "JOURNEY_ENTRY_SUBMIT_RESPONSE_INVALID")
    comment_id = value.get("id") if isinstance(value, dict) else None
    if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id <= 0:
        raise JourneyEntryError("JOURNEY_ENTRY_SUBMIT_RESPONSE_INVALID")
    return _result(
        status="PENDING", disposition="REQUESTED", work_id=work_id, request=command,
        request_comment_id=comment_id, result_comment_id=None, handle=None, blockers=[], submitted=True,
    )
