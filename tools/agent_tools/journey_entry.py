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
from tools.coordination_remote import GhApiTransport

RESULT_SCHEMA = "JourneyEntryComposition 0.1"
STATUSES = {"PASS", "PENDING", "BLOCKED", "UNKNOWN"}
DISPOSITIONS = {
    "BUILD_ONLY",
    "REQUESTED",
    "REQUEST_PENDING",
    "OBSERVED_READY",
    "OBSERVED_FAILURE",
}
BEGIN_RESULT_SCHEMA = hosted_cycle_artifact.BEGIN_RESULT_SCHEMA


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


def _payload(body: Any, marker: str) -> Any | None:
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
                f"repos/{hosted_agent_cycle.REPOSITORY}/issues"
                f"?state=open&per_page=100&page={page}",
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
    else:
        raise JourneyEntryError("JOURNEY_ENTRY_BUS_ISSUES_UNBOUNDED")
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
                f"repos/{hosted_agent_cycle.REPOSITORY}/issues/{issue_number}"
                f"/comments?per_page=100&page={page}",
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


def _identity(
    *, role: str, declared_intent: str, work_id: str, worker_id: str
) -> tuple[str, dict[str, str]]:
    role = _text(role, "JOURNEY_ENTRY_ROLE_INVALID")
    declared_intent = _text(declared_intent, "JOURNEY_ENTRY_INTENT_INVALID")
    body = {
        "repository": hosted_agent_cycle.REPOSITORY,
        "role": role,
        "declaredIntent": declared_intent,
        "workId": work_id,
        "workerId": worker_id,
    }
    digest = stable_hash(body)
    request_id = "journey-begin-" + digest[:24]
    actor = agent_cycle_identity.canonical_actor({
        "role": role,
        "workerId": worker_id,
        "sessionId": "journey-entry-" + digest[:24],
    })
    return request_id, actor


def build_begin_request(
    *,
    role: str,
    declared_intent: str,
    work_id: str,
    worker_id: str,
    runtime_environment: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    request_id, actor = _identity(
        role=role,
        declared_intent=declared_intent,
        work_id=work_id,
        worker_id=worker_id,
    )
    if runtime_environment is None:
        value = {
            "schemaVersion": hosted_agent_cycle.COMMAND_SCHEMA_V03,
            "requestId": request_id,
            "action": "begin",
            "actor": actor,
            "declaredIntent": declared_intent.strip(),
            "machineScope": "live",
            "workRef": {"workId": work_id},
            "evidenceCommentIds": [],
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        return (
            hosted_agent_cycle.REQUEST_MARKER_V03,
            hosted_agent_cycle.validate_work_begin_command(value),
        )
    environment = hosted_agent_cycle.validate_runtime_environment(
        copy.deepcopy(runtime_environment)
    )
    value = {
        "schemaVersion": hosted_agent_cycle.COMMAND_SCHEMA_V04,
        "requestId": request_id,
        "action": "begin",
        "actor": actor,
        "declaredIntent": declared_intent.strip(),
        "machineScope": "live",
        "workRef": {"workId": work_id},
        "runtimeEnvironment": environment,
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return (
        hosted_agent_cycle.REQUEST_MARKER_V04,
        hosted_agent_cycle.validate_runtime_begin_command(value),
    )


def _request_observation(
    comments: list[dict[str, Any]],
    *,
    marker: str,
    command: dict[str, Any],
) -> tuple[int | None, bool]:
    exact: list[int] = []
    conflict = False
    for comment in comments:
        if comment.get("author_association") != "OWNER":
            continue
        observed_marker = None
        value = None
        for candidate in (
            hosted_agent_cycle.REQUEST_MARKER_V03,
            hosted_agent_cycle.REQUEST_MARKER_V04,
        ):
            parsed = _payload(comment.get("body"), candidate)
            if isinstance(parsed, dict) and parsed.get("requestId") == command["requestId"]:
                observed_marker = candidate
                value = parsed
                break
        if value is None:
            continue
        comment_id = comment.get("id")
        if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id <= 0:
            raise JourneyEntryError("JOURNEY_ENTRY_REQUEST_COMMENT_INVALID")
        if observed_marker == marker and value == command:
            exact.append(comment_id)
        else:
            conflict = True
    if conflict:
        raise JourneyEntryError("JOURNEY_ENTRY_REQUEST_ID_CONFLICT")
    if len(exact) > 1:
        raise JourneyEntryError("JOURNEY_ENTRY_REQUEST_DUPLICATE")
    return (exact[0] if exact else None), bool(exact)


def _validate_ready_result(
    value: Any,
    *,
    command: dict[str, Any],
    issue_number: int,
    request_comment_id: int,
) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schemaVersion") != BEGIN_RESULT_SCHEMA:
        raise JourneyEntryError("JOURNEY_ENTRY_BEGIN_RESULT_INVALID")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "resultHash"}
    if value.get("resultHash") != stable_hash(core):
        raise JourneyEntryError("JOURNEY_ENTRY_BEGIN_RESULT_HASH_INVALID")
    if (
        value.get("requestId") != command["requestId"]
        or value.get("commandHash") != hosted_agent_cycle.transport_command_hash(command)
        or value.get("status") != "READY"
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise JourneyEntryError("JOURNEY_ENTRY_BEGIN_RESULT_BINDING_INVALID")
    try:
        handle, locator = hosted_cycle_handle.decode_handle(
            value.get("handle"), repository=hosted_agent_cycle.REPOSITORY
        )
    except RuntimeError as exc:
        raise JourneyEntryError("JOURNEY_ENTRY_BEGIN_HANDLE_INVALID") from exc
    if handle["actor"] != command["actor"]:
        raise JourneyEntryError("JOURNEY_ENTRY_BEGIN_ACTOR_MISMATCH")
    if (
        value.get("cycleId") != handle["cycleId"]
        or value.get("cycleInstanceId") != handle["cycleInstanceId"]
        or value.get("contextHash") != handle["context"]["contextHash"]
        or locator["issueNumber"] != issue_number
        or locator["beginCommentId"] != request_comment_id
        or locator["runId"] != value.get("runId")
        or locator["sourceSha"] != value.get("sourceSha")
        or locator["artifactName"] != value.get("artifactName")
    ):
        raise JourneyEntryError("JOURNEY_ENTRY_BEGIN_HANDLE_BINDING_MISMATCH")
    try:
        resumability = hosted_cycle_artifact.validate_projection(value.get("resumability"))
    except RuntimeError as exc:
        raise JourneyEntryError("JOURNEY_ENTRY_BEGIN_RESUMABILITY_INVALID") from exc
    if (
        resumability["state"] != "AVAILABLE"
        or resumability["runId"] != locator["runId"]
        or resumability["headSha"] != locator["sourceSha"]
        or resumability["artifactName"] != locator["artifactName"]
    ):
        raise JourneyEntryError("JOURNEY_ENTRY_BEGIN_RESUMABILITY_MISMATCH")
    return copy.deepcopy(handle)


def _result_observation(
    comments: list[dict[str, Any]],
    *,
    command: dict[str, Any],
    issue_number: int,
    request_comment_id: int,
) -> tuple[str, int | None, dict[str, Any] | None, list[str]]:
    candidates: list[tuple[int, dict[str, Any]]] = []
    expected_hash = hosted_agent_cycle.transport_command_hash(command)
    for comment in comments:
        user = comment.get("user") if isinstance(comment, dict) else None
        if not isinstance(user, dict) or user.get("login") != "github-actions[bot]":
            continue
        value = _payload(comment.get("body"), hosted_agent_cycle.RESULT_MARKER)
        if not isinstance(value, dict) or value.get("requestId") != command["requestId"]:
            continue
        comment_id = comment.get("id")
        if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id <= 0:
            raise JourneyEntryError("JOURNEY_ENTRY_RESULT_COMMENT_INVALID")
        if value.get("commandHash") != expected_hash:
            raise JourneyEntryError("JOURNEY_ENTRY_RESULT_COMMAND_MISMATCH")
        candidates.append((comment_id, value))
    if not candidates:
        return "PENDING", None, None, []
    candidates.sort(key=lambda item: item[0])
    latest_id, latest = candidates[-1]
    if latest.get("schemaVersion") == BEGIN_RESULT_SCHEMA:
        handle = _validate_ready_result(
            latest,
            command=command,
            issue_number=issue_number,
            request_comment_id=request_comment_id,
        )
        return "PASS", latest_id, handle, []
    try:
        failure = agent_failure.validate_hosted_cycle_failure(latest)
    except RuntimeError as exc:
        raise JourneyEntryError("JOURNEY_ENTRY_RESULT_INVALID") from exc
    core = failure["failureCore"]
    status = "UNKNOWN" if core.get("status") == "UNKNOWN" else "BLOCKED"
    causes = core.get("causes") or []
    blockers = sorted({
        item.get("code")
        for item in causes
        if isinstance(item, dict) and isinstance(item.get("code"), str)
    })
    return status, latest_id, None, blockers


def _result(
    *,
    status: str,
    disposition: str,
    work_id: str,
    actor: dict[str, str],
    issue_number: int,
    request: dict[str, Any],
    request_comment_id: int | None,
    result_comment_id: int | None,
    handle: dict[str, Any] | None,
    blockers: list[str],
    submitted: bool,
) -> dict[str, Any]:
    if status not in STATUSES or disposition not in DISPOSITIONS:
        raise JourneyEntryError("JOURNEY_ENTRY_RESULT_INVALID")
    core = {
        "schemaVersion": RESULT_SCHEMA,
        "status": status,
        "disposition": disposition,
        "workId": work_id,
        "actor": copy.deepcopy(actor),
        "issueNumber": issue_number,
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
    runtime_environment: dict[str, Any] | None = None,
    submit: bool = False,
    transport: Any | None = None,
) -> dict[str, Any]:
    carrier = transport or GhApiTransport()
    work = _work(work_id, carrier)
    marker, command = build_begin_request(
        role=role,
        declared_intent=declared_intent,
        work_id=work_id,
        worker_id=work["workerId"],
        runtime_environment=runtime_environment,
    )
    issue_number = _bus_issue(carrier)
    comments = _comments(carrier, issue_number)
    request_comment_id, exists = _request_observation(
        comments, marker=marker, command=command
    )
    if exists:
        status, result_comment_id, handle, blockers = _result_observation(
            comments,
            command=command,
            issue_number=issue_number,
            request_comment_id=request_comment_id,
        )
        if status == "PASS":
            disposition = "OBSERVED_READY"
        elif status in {"BLOCKED", "UNKNOWN"}:
            disposition = "OBSERVED_FAILURE"
        else:
            disposition = "REQUEST_PENDING"
        return _result(
            status=status,
            disposition=disposition,
            work_id=work_id,
            actor=command["actor"],
            issue_number=issue_number,
            request=command,
            request_comment_id=request_comment_id,
            result_comment_id=result_comment_id,
            handle=handle,
            blockers=blockers,
            submitted=False,
        )

    if not submit:
        return _result(
            status="PENDING",
            disposition="BUILD_ONLY",
            work_id=work_id,
            actor=command["actor"],
            issue_number=issue_number,
            request=command,
            request_comment_id=None,
            result_comment_id=None,
            handle=None,
            blockers=[],
            submitted=False,
        )

    body = marker + "\n" + json.dumps(
        command, separators=(",", ":"), ensure_ascii=False
    )
    response = _json_response(
        carrier.request(
            "POST",
            f"repos/{hosted_agent_cycle.REPOSITORY}/issues/{issue_number}/comments",
            payload={"body": body},
        ),
        "JOURNEY_ENTRY_SUBMIT_INVALID",
    )
    request_comment_id = response.get("id") if isinstance(response, dict) else None
    if (
        not isinstance(request_comment_id, int)
        or isinstance(request_comment_id, bool)
        or request_comment_id <= 0
    ):
        raise JourneyEntryError("JOURNEY_ENTRY_SUBMIT_INVALID")
    return _result(
        status="PENDING",
        disposition="REQUESTED",
        work_id=work_id,
        actor=command["actor"],
        issue_number=issue_number,
        request=command,
        request_comment_id=request_comment_id,
        result_comment_id=None,
        handle=None,
        blockers=[],
        submitted=True,
    )
