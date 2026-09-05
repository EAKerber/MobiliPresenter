"""Read-only Recovery & Re-entry classification for one canonical Work item.

This projection composes the canonical Work authority, the Work-bound Hosted
cycle lineage, and exact Hosted close transport records. It does not mutate
Work, replay operations, take over peer identity, or authorize any action.
"""
from __future__ import annotations

import copy
from typing import Any

from tools import agent_failure
from tools import continuation
from tools import hosted_agent_cycle
from tools import hosted_agent_cycle_waiting
from tools import hosted_cycle_handle
from tools import hosted_cycle_lineage
from tools import hosted_cycle_records
from tools.canonical import stable_hash

SCHEMA = "HostedCycleReentryInspection 0.1"
STATES = {
    "CLEAN_REENTRY",
    "LEGITIMATE_WAIT",
    "PRIORITY_OPERATION_REQUIRED",
    "INSUFFICIENT_OBSERVATION",
    "NO_REENTRY_REQUIRED",
}
ACTIONS = {
    "BEGIN_NEW_CYCLE",
    "RESUME_EXACT_CYCLE",
    "WAIT",
    "HONOR_HANDOFF",
    "RECONCILE_FAILURE",
    "OBSERVE",
    "NONE",
}
OUTCOME_STATES = {
    "OPEN",
    "PASS",
    "WAITING",
    "FAILURE",
    "PENDING_CLOSE_RESULT",
    "AMBIGUOUS_CLOSE_RESULT",
}
FIELDS = {
    "schemaVersion", "workRef", "workAuthorityHead", "workStateHash",
    "lineageHash", "workStatus", "state", "reasonCodes", "nextSafeAction",
    "targetCycle", "cycleOutcomes", "readOnly", "semanticAuthority",
    "authorizesMutation", "inspectionHash",
}
OUTCOME_FIELDS = {
    "cycleInstanceId", "state", "closeRequestCommentId", "resultCommentIds",
    "resultHash", "reasonCodes",
}
CLOSE_RESULT_FIELDS = {
    "schemaVersion", "requestId", "commandHash", "runId", "sourceSha",
    "beginRunId", "cycleId", "contextHash", "receiptHash", "closureHash",
    "status", "semanticAuthority", "authorizesMutation", "resultHash",
}


class HostedCycleReentryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _positive_int(value: Any, code: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise HostedCycleReentryError(code)
    return value


def _sha(value: Any, code: str) -> str:
    if not isinstance(value, str) or hosted_agent_cycle.SHA_RE.fullmatch(value) is None:
        raise HostedCycleReentryError(code)
    return value


def _hash(value: Any, code: str) -> str:
    if not isinstance(value, str) or hosted_agent_cycle.HASH_RE.fullmatch(value) is None:
        raise HostedCycleReentryError(code)
    return value


def _comment_id(value: Any) -> int:
    cid = hosted_cycle_records.comment_id(value)
    if cid is None:
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_COMMENT_INVALID")
    return cid


def _request_event(comment: dict[str, Any], issue_number: int) -> dict[str, Any]:
    return {
        "issue": {
            "number": issue_number,
            "title": hosted_agent_cycle.BUS_TITLE,
            "pull_request": None,
        },
        "comment": {
            "id": _comment_id(comment),
            "body": comment.get("body"),
            "author_association": comment.get("author_association"),
        },
        "repository": {"full_name": hosted_agent_cycle.REPOSITORY},
    }


def _candidate_begin(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "runId": candidate["runId"],
        "sourceSha": candidate["sourceSha"],
        "contextHash": candidate["contextHash"],
    }


def _close_claims_candidate(command: dict[str, Any], candidate: dict[str, Any]) -> bool:
    schema = command.get("schemaVersion")
    if schema == hosted_agent_cycle.COMMAND_SCHEMA_V02:
        try:
            handle, locator = hosted_cycle_handle.decode_handle(
                command.get("handle"), repository=hosted_agent_cycle.REPOSITORY
            )
            expected_handle, expected_locator = hosted_cycle_handle.decode_handle(
                candidate.get("handle"), repository=hosted_agent_cycle.REPOSITORY
            )
        except RuntimeError:
            return False
        return handle == expected_handle and locator == expected_locator
    if schema == hosted_agent_cycle.COMMAND_SCHEMA:
        handle = candidate.get("handle")
        return (
            isinstance(handle, dict)
            and command.get("begin") == _candidate_begin(candidate)
            and command.get("actor") == handle.get("actor")
        )
    return False


def _first_close_request(
    comments: list[dict[str, Any]],
    *,
    candidate: dict[str, Any],
    issue_number: int,
) -> tuple[int, dict[str, Any], str] | None:
    begin_comment_id = candidate["requestCommentId"]
    for comment in sorted(comments, key=_comment_id):
        cid = _comment_id(comment)
        if cid <= begin_comment_id or not hosted_cycle_records.request_comment_allowed(comment):
            continue
        body = comment.get("body")
        if not isinstance(body, str) or not any(
            body.startswith(marker + "\n")
            for marker in (
                hosted_agent_cycle.REQUEST_MARKER,
                hosted_agent_cycle.REQUEST_MARKER_V02,
            )
        ):
            continue
        try:
            command, _ = hosted_agent_cycle.parse_event(_request_event(comment, issue_number))
        except hosted_agent_cycle.HostedAgentCycleError as exc:
            raise HostedCycleReentryError(
                "HOSTED_CYCLE_REENTRY_CLOSE_REQUEST_INVALID:" + exc.code
            ) from exc
        if command.get("action") != "close" or not _close_claims_candidate(command, candidate):
            continue
        return cid, command, hosted_agent_cycle.transport_command_hash(command)
    return None


def _validate_close_pass(
    value: Any,
    *,
    candidate: dict[str, Any],
    request_id: str,
    command_hash: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != CLOSE_RESULT_FIELDS:
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_CLOSE_RESULT_FIELDS_INVALID")
    if (
        value.get("schemaVersion") != hosted_agent_cycle.CLOSE_RESULT_SCHEMA
        or value.get("status") != "PASS"
        or value.get("requestId") != request_id
        or value.get("commandHash") != command_hash
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_CLOSE_RESULT_INVALID")
    _positive_int(value.get("runId"), "HOSTED_CYCLE_REENTRY_CLOSE_RESULT_INVALID")
    _sha(value.get("sourceSha"), "HOSTED_CYCLE_REENTRY_CLOSE_RESULT_INVALID")
    for field in ("commandHash", "contextHash", "receiptHash", "closureHash", "resultHash"):
        _hash(value.get(field), "HOSTED_CYCLE_REENTRY_CLOSE_RESULT_INVALID")
    if (
        value.get("beginRunId") != candidate["runId"]
        or value.get("cycleId") != candidate["cycleId"]
        or value.get("contextHash") != candidate["contextHash"]
    ):
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_CLOSE_RESULT_BINDING_MISMATCH")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "resultHash"}
    if value["resultHash"] != stable_hash(core):
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_CLOSE_RESULT_HASH_MISMATCH")
    return value


def _normalize_result(
    value: dict[str, Any],
    *,
    candidate: dict[str, Any],
    request_id: str,
    command_hash: str,
) -> tuple[str, str, list[str]] | None:
    if value.get("requestId") != request_id or value.get("commandHash") != command_hash:
        return None
    schema = value.get("schemaVersion")
    if schema == hosted_agent_cycle.CLOSE_RESULT_SCHEMA:
        close = _validate_close_pass(
            value,
            candidate=candidate,
            request_id=request_id,
            command_hash=command_hash,
        )
        return "PASS", close["resultHash"], []
    if schema == hosted_agent_cycle_waiting.WAITING_SCHEMA:
        try:
            waiting = hosted_agent_cycle_waiting.validate_waiting(value)
        except RuntimeError as exc:
            raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_WAITING_INVALID") from exc
        if (
            waiting["cycleInstanceId"] != candidate["cycleInstanceId"]
            or waiting["commandHash"] != command_hash
        ):
            raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_WAITING_BINDING_MISMATCH")
        return "WAITING", waiting["resultHash"], list(waiting["waitingFor"])
    if schema == agent_failure.HOSTED_CYCLE_FAILURE_SCHEMA:
        try:
            failure = agent_failure.validate_hosted_cycle_failure(value)
        except RuntimeError as exc:
            raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_FAILURE_INVALID") from exc
        if failure.get("requestId") != request_id or failure.get("commandHash") != command_hash:
            raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_FAILURE_BINDING_MISMATCH")
        codes = [item["code"] for item in failure["failureCore"]["causes"]]
        return "FAILURE", failure["failureHash"], sorted(set(codes))
    return None


def _outcome_for_candidate(
    comments: list[dict[str, Any]],
    *,
    candidate: dict[str, Any],
    issue_number: int,
) -> dict[str, Any]:
    close = _first_close_request(
        comments,
        candidate=candidate,
        issue_number=issue_number,
    )
    if close is None:
        return {
            "cycleInstanceId": candidate["cycleInstanceId"],
            "state": "OPEN",
            "closeRequestCommentId": None,
            "resultCommentIds": [],
            "resultHash": None,
            "reasonCodes": [],
        }
    close_comment_id, command, command_hash = close
    matches: list[tuple[int, str, str, list[str]]] = []
    for comment in sorted(comments, key=_comment_id):
        cid = _comment_id(comment)
        if cid <= close_comment_id or not hosted_cycle_records.result_comment_allowed(comment):
            continue
        payload = hosted_cycle_records.json_after_marker(
            comment.get("body"), hosted_agent_cycle.RESULT_MARKER
        )
        if not isinstance(payload, dict):
            continue
        normalized = _normalize_result(
            payload,
            candidate=candidate,
            request_id=command["requestId"],
            command_hash=command_hash,
        )
        if normalized is None:
            continue
        state, result_hash, reasons = normalized
        matches.append((cid, state, result_hash, reasons))
    if not matches:
        return {
            "cycleInstanceId": candidate["cycleInstanceId"],
            "state": "PENDING_CLOSE_RESULT",
            "closeRequestCommentId": close_comment_id,
            "resultCommentIds": [],
            "resultHash": None,
            "reasonCodes": ["HOSTED_CLOSE_RESULT_PENDING"],
        }
    identities = {(state, digest) for _, state, digest, _ in matches}
    if len(identities) != 1:
        return {
            "cycleInstanceId": candidate["cycleInstanceId"],
            "state": "AMBIGUOUS_CLOSE_RESULT",
            "closeRequestCommentId": close_comment_id,
            "resultCommentIds": [cid for cid, *_ in matches],
            "resultHash": None,
            "reasonCodes": ["HOSTED_CLOSE_RESULT_AMBIGUOUS"],
        }
    state, digest = next(iter(identities))
    reasons: set[str] = set()
    for _, _, _, items in matches:
        reasons.update(items)
    return {
        "cycleInstanceId": candidate["cycleInstanceId"],
        "state": state,
        "closeRequestCommentId": close_comment_id,
        "resultCommentIds": [cid for cid, *_ in matches],
        "resultHash": digest,
        "reasonCodes": sorted(reasons),
    }


def _target(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {
        "cycleInstanceId": candidate["cycleInstanceId"],
        "handle": copy.deepcopy(candidate["handle"]),
    }


def _classify(
    *,
    work: dict[str, Any],
    lineage: dict[str, Any],
    outcomes: list[dict[str, Any]],
) -> tuple[str, str, list[str], dict[str, Any] | None]:
    status = work["status"]
    if status == "WAITING":
        return "LEGITIMATE_WAIT", "WAIT", ["WORK_WAITING"], None
    if status == "HANDOFF":
        return "PRIORITY_OPERATION_REQUIRED", "HONOR_HANDOFF", ["WORK_HANDOFF"], None

    pending = lineage["pendingRequests"]
    if pending:
        return (
            "INSUFFICIENT_OBSERVATION",
            "OBSERVE",
            ["HOSTED_BEGIN_PENDING"],
            None,
        )
    if lineage["ambiguous"]:
        return (
            "INSUFFICIENT_OBSERVATION",
            "OBSERVE",
            ["HOSTED_CYCLE_LINEAGE_AMBIGUOUS"],
            None,
        )

    if status == "DONE":
        nonterminal = [item for item in outcomes if item["state"] != "PASS"]
        if nonterminal:
            return (
                "INSUFFICIENT_OBSERVATION",
                "OBSERVE",
                ["WORK_DONE_WITH_NONTERMINAL_CYCLE"],
                None,
            )
        return "NO_REENTRY_REQUIRED", "NONE", ["WORK_DONE"], None

    candidates = lineage["candidates"]
    if not candidates:
        return "CLEAN_REENTRY", "BEGIN_NEW_CYCLE", ["NO_MATERIALIZED_CYCLE"], None
    if len(candidates) != 1 or len(outcomes) != 1:
        return (
            "INSUFFICIENT_OBSERVATION",
            "OBSERVE",
            ["HOSTED_CYCLE_LINEAGE_AMBIGUOUS"],
            None,
        )

    candidate, outcome = candidates[0], outcomes[0]
    state = outcome["state"]
    if state == "OPEN":
        return (
            "CLEAN_REENTRY",
            "RESUME_EXACT_CYCLE",
            ["EXACT_RESUMABLE_CYCLE"],
            _target(candidate),
        )
    if state == "PASS":
        return "CLEAN_REENTRY", "BEGIN_NEW_CYCLE", ["PREVIOUS_CYCLE_CLOSED"], None
    if state == "WAITING":
        return (
            "LEGITIMATE_WAIT",
            "WAIT",
            sorted(set(["HOSTED_CYCLE_WAITING", *outcome["reasonCodes"]])),
            _target(candidate),
        )
    if state == "FAILURE":
        return (
            "PRIORITY_OPERATION_REQUIRED",
            "RECONCILE_FAILURE",
            sorted(set(["HOSTED_CYCLE_CLOSE_FAILED", *outcome["reasonCodes"]])),
            _target(candidate),
        )
    return (
        "INSUFFICIENT_OBSERVATION",
        "OBSERVE",
        list(outcome["reasonCodes"] or ["HOSTED_CYCLE_OUTCOME_UNKNOWN"]),
        _target(candidate),
    )


def inspect_reentry(
    comments: list[dict[str, Any]],
    *,
    work: dict[str, Any],
    work_authority_head: str,
    issue_number: int,
) -> dict[str, Any]:
    try:
        work = continuation.valid(work, work.get("id") if isinstance(work, dict) else None)
    except RuntimeError as exc:
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_WORK_INVALID") from exc
    head = _sha(work_authority_head, "HOSTED_CYCLE_REENTRY_WORK_HEAD_INVALID")
    issue_number = _positive_int(issue_number, "HOSTED_CYCLE_REENTRY_ISSUE_INVALID")
    lineage = hosted_cycle_lineage.build_work_lineage(
        comments,
        work_ref={"workId": work["id"]},
        issue_number=issue_number,
    )
    outcomes = [
        _outcome_for_candidate(comments, candidate=item, issue_number=issue_number)
        for item in lineage["candidates"]
    ]
    outcomes.sort(key=lambda item: item["cycleInstanceId"])
    state, action, reasons, target = _classify(
        work=work,
        lineage=lineage,
        outcomes=outcomes,
    )
    core = {
        "schemaVersion": SCHEMA,
        "workRef": {"workId": work["id"]},
        "workAuthorityHead": head,
        "workStateHash": continuation.state_hash(work),
        "lineageHash": lineage["lineageHash"],
        "workStatus": work["status"],
        "state": state,
        "reasonCodes": sorted(set(reasons)),
        "nextSafeAction": action,
        "targetCycle": target,
        "cycleOutcomes": outcomes,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return validate_reentry({**core, "inspectionHash": stable_hash(core)})


def _validate_outcome(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != OUTCOME_FIELDS:
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_OUTCOME_FIELDS_INVALID")
    cycle_id = value.get("cycleInstanceId")
    if not isinstance(cycle_id, str) or hosted_agent_cycle.CYCLE_INSTANCE_RE.fullmatch(cycle_id) is None:
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_OUTCOME_INVALID")
    if value.get("state") not in OUTCOME_STATES:
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_OUTCOME_INVALID")
    close_id = value.get("closeRequestCommentId")
    if close_id is not None:
        _positive_int(close_id, "HOSTED_CYCLE_REENTRY_OUTCOME_INVALID")
    result_ids = value.get("resultCommentIds")
    if (
        not isinstance(result_ids, list)
        or result_ids != sorted(set(result_ids))
        or any(not isinstance(item, int) or isinstance(item, bool) or item <= 0 for item in result_ids)
    ):
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_OUTCOME_INVALID")
    digest = value.get("resultHash")
    if digest is not None:
        _hash(digest, "HOSTED_CYCLE_REENTRY_OUTCOME_INVALID")
    reasons = value.get("reasonCodes")
    if (
        not isinstance(reasons, list)
        or reasons != sorted(set(reasons))
        or any(not isinstance(item, str) or not item for item in reasons)
    ):
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_OUTCOME_INVALID")
    if value["state"] == "OPEN" and (close_id is not None or result_ids or digest is not None):
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_OUTCOME_BINDING_INVALID")
    if value["state"] == "PENDING_CLOSE_RESULT" and (close_id is None or result_ids or digest is not None):
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_OUTCOME_BINDING_INVALID")
    if value["state"] in {"PASS", "WAITING", "FAILURE"} and (
        close_id is None or not result_ids or digest is None
    ):
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_OUTCOME_BINDING_INVALID")
    return value


def validate_reentry(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_FIELDS_INVALID")
    if (
        value.get("schemaVersion") != SCHEMA
        or value.get("state") not in STATES
        or value.get("nextSafeAction") not in ACTIONS
        or value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_BOUNDARY_INVALID")
    work_ref = value.get("workRef")
    if not isinstance(work_ref, dict) or set(work_ref) != {"workId"}:
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_WORK_REF_INVALID")
    if not isinstance(work_ref["workId"], str) or not continuation.ID_RE.fullmatch(work_ref["workId"]):
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_WORK_REF_INVALID")
    _sha(value.get("workAuthorityHead"), "HOSTED_CYCLE_REENTRY_WORK_HEAD_INVALID")
    _hash(value.get("workStateHash"), "HOSTED_CYCLE_REENTRY_WORK_HASH_INVALID")
    _hash(value.get("lineageHash"), "HOSTED_CYCLE_REENTRY_LINEAGE_HASH_INVALID")
    if value.get("workStatus") not in continuation.STATUSES:
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_WORK_STATUS_INVALID")
    reasons = value.get("reasonCodes")
    if (
        not isinstance(reasons, list)
        or not reasons
        or reasons != sorted(set(reasons))
        or any(not isinstance(item, str) or not item for item in reasons)
    ):
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_REASON_INVALID")
    outcomes = value.get("cycleOutcomes")
    if not isinstance(outcomes, list):
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_OUTCOMES_INVALID")
    for item in outcomes:
        _validate_outcome(item)
    cycle_ids = [item["cycleInstanceId"] for item in outcomes]
    if cycle_ids != sorted(set(cycle_ids)):
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_OUTCOMES_INVALID")
    target = value.get("targetCycle")
    if target is not None:
        if not isinstance(target, dict) or set(target) != {"cycleInstanceId", "handle"}:
            raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_TARGET_INVALID")
        try:
            handle, _ = hosted_cycle_handle.decode_handle(
                target.get("handle"), repository=hosted_agent_cycle.REPOSITORY
            )
        except RuntimeError as exc:
            raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_TARGET_INVALID") from exc
        if handle.get("cycleInstanceId") != target.get("cycleInstanceId"):
            raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_TARGET_INVALID")
        if target["cycleInstanceId"] not in set(cycle_ids):
            raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_TARGET_INVALID")
    if value["nextSafeAction"] == "RESUME_EXACT_CYCLE" and target is None:
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_TARGET_REQUIRED")
    if value["state"] == "NO_REENTRY_REQUIRED" and value["nextSafeAction"] != "NONE":
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_ACTION_INVALID")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "inspectionHash"}
    if value.get("inspectionHash") != stable_hash(core):
        raise HostedCycleReentryError("HOSTED_CYCLE_REENTRY_HASH_MISMATCH")
    return value
