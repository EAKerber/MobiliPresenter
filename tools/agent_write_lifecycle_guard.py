from __future__ import annotations

import copy
import json
from typing import Any

from tools import agent_write_lifecycle as lifecycle, coordination
from tools.agent_tools import trace_collect
from tools.canonical import stable_hash
from tools.coordination_remote import GhApiTransport, GitHubCoordinationAuthority

REPORT_SCHEMA = "AgentWriteLeaseCloseReport 0.1"
STATES = {"NONE", "ACTIVE", "RELEASED", "EXPIRED", "UNKNOWN"}


class AgentWriteLifecycleGuardError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _payload(body: Any, marker: str) -> Any | None:
    prefix = marker + "\n"
    if not isinstance(body, str) or not body.startswith(prefix):
        return None
    raw = body[len(prefix):].strip()
    if raw.startswith("```json") and raw.endswith("```"):
        raw = raw[len("```json"): -len("```")].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _window(comments: list[dict[str, Any]], begin_id: int, close_id: int) -> list[dict[str, Any]]:
    positions = {item.get("id"): index for index, item in enumerate(comments) if isinstance(item, dict)}
    if begin_id not in positions or close_id not in positions or positions[begin_id] >= positions[close_id]:
        raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_WINDOW_INVALID")
    return comments[positions[begin_id] + 1:positions[close_id]]


def _bound_results(window: list[dict[str, Any]], manifest: dict[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    begin = {"runId": manifest["source"]["runId"], "sourceSha": manifest["source"]["sourceSha"], "contextHash": manifest["contextHash"]}
    actor = manifest["actor"]
    found: list[tuple[int, dict[str, Any]]] = []
    for comment in window:
        user = comment.get("user") if isinstance(comment, dict) else None
        if not isinstance(user, dict) or user.get("login") != "github-actions[bot]":
            continue
        value = _payload(comment.get("body"), lifecycle.RESULT_MARKER)
        if not isinstance(value, dict) or value.get("schemaVersion") != lifecycle.RESULT_SCHEMA:
            continue
        try:
            lifecycle.validate_result(value)
        except Exception as exc:
            raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_RESULT_INVALID") from exc
        if value["begin"] != begin or value["actor"] != actor or value["cycleInstanceId"] != manifest["cycleInstanceId"]:
            continue
        comment_id = comment.get("id")
        if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id <= 0:
            raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_RESULT_COMMENT_INVALID")
        found.append((comment_id, value))
    return found

def _request_count(window: list[dict[str, Any]], manifest: dict[str, Any]) -> int:
    begin = {"runId": manifest["source"]["runId"], "sourceSha": manifest["source"]["sourceSha"], "contextHash": manifest["contextHash"]}
    actor = manifest["actor"]
    count = 0
    for comment in window:
        if not isinstance(comment, dict) or comment.get("author_association") != "OWNER":
            continue
        value = _payload(comment.get("body"), lifecycle.REQUEST_MARKER)
        if not isinstance(value, dict):
            continue
        try:
            lifecycle.validate_request(value)
        except Exception:
            continue
        if value["begin"] == begin and value["actor"] == actor:
            count += 1
    return count

def inspect_cycle(
    comments: list[dict[str, Any]], manifest: dict[str, Any], *, close_comment_id: int, transport: Any | None = None
) -> dict[str, Any]:
    carrier = transport or GhApiTransport()
    issue_number = manifest["source"]["issueNumber"]
    del issue_number
    window = _window(comments, manifest["source"]["commentId"], close_comment_id)
    results = _bound_results(window, manifest)
    request_count = _request_count(window, manifest)
    authority = GitHubCoordinationAuthority(transport=carrier)
    observation = authority.observe()
    active = coordination.active_leases(observation.state, observation.authority_now)
    session_id = manifest["actor"]["sessionId"]
    session_leases = [lease for lease in active if isinstance(lease.get("owner"), dict) and lease["owner"].get("session") == session_id]

    state = "NONE"
    blockers: list[str] = []
    latest_binding: dict[str, Any] | None = None
    if results:
        latest_binding = results[-1][1]["binding"]
        if latest_binding["state"] == "RELEASED":
            if session_leases:
                state = "UNKNOWN"
                blockers.append("AGENT_WRITE_LIFECYCLE_RELEASE_READBACK_MISMATCH")
            else:
                state = "RELEASED"
        elif lifecycle.binding_is_expired(latest_binding, observation.authority_now):
            state = "EXPIRED"
            if session_leases:
                state = "UNKNOWN"
                blockers.append("AGENT_WRITE_LIFECYCLE_EXPIRED_BUT_LEASE_ACTIVE")
        else:
            matching = [lease for lease in session_leases if lease.get("leaseId") == latest_binding["leaseId"] and lease.get("resource") == f"branch:{latest_binding['branch']}"]
            if len(matching) == 1 and len(session_leases) == 1:
                state = "ACTIVE"
                blockers.append("AGENT_WRITE_LIFECYCLE_ACTIVE_AT_CLOSE")
            else:
                state = "UNKNOWN"
                blockers.append("AGENT_WRITE_LIFECYCLE_BINDING_AUTHORITY_MISMATCH")
    elif request_count:
        state = "UNKNOWN"
        blockers.append("AGENT_WRITE_LIFECYCLE_REQUEST_WITHOUT_TERMINAL")
    elif session_leases:
        state = "UNKNOWN"
        blockers.append("AGENT_WRITE_LIFECYCLE_UNBOUND_ACTIVE_LEASE")

    core = {
        "schemaVersion": REPORT_SCHEMA,
        "cycleInstanceId": manifest["cycleInstanceId"],
        "actor": copy.deepcopy(manifest["actor"]),
        "state": state,
        "latestBindingHash": latest_binding["bindingHash"] if latest_binding is not None else None,
        "authorityHead": observation.head_sha,
        "authorityNow": observation.authority_now.isoformat().replace("+00:00", "Z"),
        "matchingLeaseIds": sorted(lease["leaseId"] for lease in session_leases),
        "blockers": sorted(set(blockers)),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "reportHash": stable_hash(core)}

def validate_report(value: Any) -> dict[str, Any]:
    fields = {"schemaVersion", "cycleInstanceId", "actor", "state", "latestBindingHash", "authorityHead", "authorityNow", "matchingLeaseIds", "blockers", "readOnly", "semanticAuthority", "authorizesMutation", "reportHash"}
    if not isinstance(value, dict) or set(value) != fields or value.get("schemaVersion") != REPORT_SCHEMA or value.get("state") not in STATES:
        raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_REPORT_INVALID")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "reportHash"}
    if value.get("reportHash") != stable_hash(core):
        raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_REPORT_HASH_MISMATCH")
    return value
