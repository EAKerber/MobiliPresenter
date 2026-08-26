from __future__ import annotations

import copy
import json
from typing import Any

from tools import agent_write_lifecycle as lifecycle, coordination
from tools.canonical import stable_hash
from tools.coordination_remote import GhApiTransport, GitHubCoordinationAuthority

REPORT_SCHEMA = "AgentWriteLeaseCloseReport 0.1"
PROOF_SCHEMA = "AgentWriteLifecycleGuardProof 0.1"
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
        raw = raw[len("```json"):-len("```")].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _json_response(response: Any, code: str) -> Any:
    try:
        return json.loads(response.body)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise AgentWriteLifecycleGuardError(code) from exc


def _comments(transport: Any, issue_number: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for page in range(1, 101):
        value = _json_response(
            transport.request(
                "GET",
                f"repos/{lifecycle.hosted_agent_cycle.REPOSITORY}/issues/{issue_number}/comments?per_page=100&page={page}",
            ),
            "AGENT_WRITE_LIFECYCLE_COMMENTS_INVALID",
        )
        if not isinstance(value, list):
            raise AgentWriteLifecycleGuardError(
                "AGENT_WRITE_LIFECYCLE_COMMENTS_INVALID"
            )
        result.extend(item for item in value if isinstance(item, dict))
        if len(value) < 100:
            return result
    raise AgentWriteLifecycleGuardError(
        "AGENT_WRITE_LIFECYCLE_COMMENTS_UNBOUNDED"
    )


def _before(
    comments: list[dict[str, Any]],
    comment_id: int | None,
) -> list[dict[str, Any]]:
    if comment_id is None:
        return list(comments)
    for index, item in enumerate(comments):
        if isinstance(item, dict) and item.get("id") == comment_id:
            return comments[:index]
    raise AgentWriteLifecycleGuardError(
        "AGENT_WRITE_LIFECYCLE_CUTOFF_INVALID"
    )


def _window(
    comments: list[dict[str, Any]],
    begin_id: int,
    close_id: int,
) -> list[dict[str, Any]]:
    positions = {
        item.get("id"): index
        for index, item in enumerate(comments)
        if isinstance(item, dict)
    }
    if (
        begin_id not in positions
        or close_id not in positions
        or positions[begin_id] >= positions[close_id]
    ):
        raise AgentWriteLifecycleGuardError(
            "AGENT_WRITE_LIFECYCLE_WINDOW_INVALID"
        )
    return comments[positions[begin_id] + 1:positions[close_id]]


def _bound_results(
    window: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> list[tuple[int, dict[str, Any]]]:
    begin = {
        "runId": manifest["source"]["runId"],
        "sourceSha": manifest["source"]["sourceSha"],
        "contextHash": manifest["contextHash"],
    }
    actor = manifest["actor"]
    found: list[tuple[int, dict[str, Any]]] = []
    for comment in window:
        user = comment.get("user") if isinstance(comment, dict) else None
        if not isinstance(user, dict) or user.get("login") != "github-actions[bot]":
            continue
        value = _payload(comment.get("body"), lifecycle.RESULT_MARKER)
        if (
            not isinstance(value, dict)
            or value.get("schemaVersion") != lifecycle.RESULT_SCHEMA
        ):
            continue
        try:
            lifecycle.validate_result(value)
        except Exception as exc:
            raise AgentWriteLifecycleGuardError(
                "AGENT_WRITE_LIFECYCLE_RESULT_INVALID"
            ) from exc
        if (
            value["begin"] != begin
            or value["actor"] != actor
            or value["cycleInstanceId"] != manifest["cycleInstanceId"]
        ):
            continue
        comment_id = comment.get("id")
        if (
            not isinstance(comment_id, int)
            or isinstance(comment_id, bool)
            or comment_id <= 0
        ):
            raise AgentWriteLifecycleGuardError(
                "AGENT_WRITE_LIFECYCLE_RESULT_COMMENT_INVALID"
            )
        found.append((comment_id, value))
    return found


def _request_count(
    window: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> int:
    begin = {
        "runId": manifest["source"]["runId"],
        "sourceSha": manifest["source"]["sourceSha"],
        "contextHash": manifest["contextHash"],
    }
    actor = manifest["actor"]
    count = 0
    for comment in window:
        if (
            not isinstance(comment, dict)
            or comment.get("author_association") != "OWNER"
        ):
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


def _expected_owner(actor: dict[str, Any], branch: str) -> dict[str, Any]:
    return {
        "role": actor["role"],
        "session": actor["sessionId"],
        "branch": branch,
        "pr": None,
    }


def _matching_exact_leases(
    active: list[dict[str, Any]],
    *,
    binding: dict[str, Any],
) -> list[dict[str, Any]]:
    expected_owner = _expected_owner(binding["actor"], binding["branch"])
    resource = f"branch:{binding['branch']}"
    return [
        lease
        for lease in active
        if lease.get("leaseId") == binding["leaseId"]
        and lease.get("resource") == resource
        and lease.get("owner") == expected_owner
    ]


def prove_active_binding(
    plan: dict[str, Any],
    *,
    cycle_instance_id: str,
    issue_number: int,
    before_comment_id: int | None,
    transport: Any | None = None,
) -> dict[str, Any]:
    carrier = transport or GhApiTransport()
    comments = _before(_comments(carrier, issue_number), before_comment_id)

    candidates: list[tuple[int, dict[str, Any]]] = []
    for comment in comments:
        user = comment.get("user") if isinstance(comment, dict) else None
        if not isinstance(user, dict) or user.get("login") != "github-actions[bot]":
            continue
        value = _payload(comment.get("body"), lifecycle.RESULT_MARKER)
        if (
            not isinstance(value, dict)
            or value.get("schemaVersion") != lifecycle.RESULT_SCHEMA
        ):
            continue
        lifecycle.validate_result(value)
        if (
            value["begin"] != plan["begin"]
            or value["actor"] != plan["actor"]
            or value["cycleInstanceId"] != cycle_instance_id
            or value["branch"] != plan["target"].get("branch")
        ):
            continue
        comment_id = comment.get("id")
        if (
            not isinstance(comment_id, int)
            or isinstance(comment_id, bool)
            or comment_id <= 0
        ):
            raise AgentWriteLifecycleGuardError(
                "AGENT_WRITE_LIFECYCLE_RESULT_COMMENT_INVALID"
            )
        candidates.append((comment_id, value))

    if not candidates:
        raise AgentWriteLifecycleGuardError(
            "AGENT_WRITE_LIFECYCLE_BINDING_REQUIRED"
        )

    comment_id, result = candidates[-1]
    binding = result["binding"]
    if binding["state"] != "ACTIVE":
        raise AgentWriteLifecycleGuardError(
            "AGENT_WRITE_LIFECYCLE_NOT_ACTIVE"
        )

    authority = GitHubCoordinationAuthority(transport=carrier)
    observation = authority.observe()
    if lifecycle.binding_is_expired(binding, observation.authority_now):
        raise AgentWriteLifecycleGuardError(
            "AGENT_WRITE_LIFECYCLE_BINDING_EXPIRED"
        )

    active = coordination.active_leases(
        observation.state,
        observation.authority_now,
    )
    matching = _matching_exact_leases(active, binding=binding)
    if len(matching) != 1:
        raise AgentWriteLifecycleGuardError(
            "AGENT_WRITE_LIFECYCLE_BINDING_AUTHORITY_MISMATCH"
        )

    core = {
        "schemaVersion": PROOF_SCHEMA,
        "cycleInstanceId": cycle_instance_id,
        "requestHash": plan["requestHash"],
        "planHash": plan["planHash"],
        "actor": copy.deepcopy(plan["actor"]),
        "branch": binding["branch"],
        "bindingHash": binding["bindingHash"],
        "lifecycleResultHash": result["resultHash"],
        "lifecycleResultCommentId": comment_id,
        "leaseId": binding["leaseId"],
        "authorityHead": observation.head_sha,
        "authorityNow": observation.authority_now.isoformat().replace(
            "+00:00", "Z"
        ),
        "status": "PASS",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "proofHash": stable_hash(core)}


def validate_active_binding_proof(value: Any) -> dict[str, Any]:
    fields = {
        "schemaVersion", "cycleInstanceId", "requestHash", "planHash", "actor",
        "branch", "bindingHash", "lifecycleResultHash",
        "lifecycleResultCommentId", "leaseId", "authorityHead", "authorityNow",
        "status", "readOnly", "semanticAuthority", "authorizesMutation",
        "proofHash",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or value.get("schemaVersion") != PROOF_SCHEMA
    ):
        raise AgentWriteLifecycleGuardError(
            "AGENT_WRITE_LIFECYCLE_PROOF_INVALID"
        )
    if value.get("status") != "PASS" or value.get("readOnly") is not True:
        raise AgentWriteLifecycleGuardError(
            "AGENT_WRITE_LIFECYCLE_PROOF_INVALID"
        )
    if (
        value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise AgentWriteLifecycleGuardError(
            "AGENT_WRITE_LIFECYCLE_PROOF_INVALID"
        )
    for field in (
        "requestHash",
        "planHash",
        "bindingHash",
        "lifecycleResultHash",
        "proofHash",
    ):
        raw = value.get(field)
        if (
            not isinstance(raw, str)
            or len(raw) != 64
            or any(ch not in "0123456789abcdef" for ch in raw)
        ):
            raise AgentWriteLifecycleGuardError(
                "AGENT_WRITE_LIFECYCLE_PROOF_INVALID"
            )
    if (
        not isinstance(value.get("lifecycleResultCommentId"), int)
        or isinstance(value["lifecycleResultCommentId"], bool)
        or value["lifecycleResultCommentId"] <= 0
    ):
        raise AgentWriteLifecycleGuardError(
            "AGENT_WRITE_LIFECYCLE_PROOF_INVALID"
        )

    core = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "proofHash"
    }
    if value.get("proofHash") != stable_hash(core):
        raise AgentWriteLifecycleGuardError(
            "AGENT_WRITE_LIFECYCLE_PROOF_HASH_MISMATCH"
        )
    return value


def inspect_cycle(
    comments: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    close_comment_id: int,
    transport: Any | None = None,
) -> dict[str, Any]:
    carrier = transport or GhApiTransport()
    window = _window(
        comments,
        manifest["source"]["commentId"],
        close_comment_id,
    )
    results = _bound_results(window, manifest)
    request_count = _request_count(window, manifest)

    authority = GitHubCoordinationAuthority(transport=carrier)
    observation = authority.observe()
    active = coordination.active_leases(
        observation.state,
        observation.authority_now,
    )

    state = "NONE"
    blockers: list[str] = []
    latest_binding: dict[str, Any] | None = None
    matching: list[dict[str, Any]] = []

    if results:
        latest_binding = results[-1][1]["binding"]
        matching = _matching_exact_leases(active, binding=latest_binding)

        if latest_binding["state"] == "RELEASED":
            if matching:
                state = "UNKNOWN"
                blockers.append(
                    "AGENT_WRITE_LIFECYCLE_RELEASE_READBACK_MISMATCH"
                )
            else:
                state = "RELEASED"
        elif lifecycle.binding_is_expired(
            latest_binding,
            observation.authority_now,
        ):
            if matching:
                state = "UNKNOWN"
                blockers.append(
                    "AGENT_WRITE_LIFECYCLE_EXPIRED_BUT_LEASE_ACTIVE"
                )
            else:
                state = "EXPIRED"
        elif len(matching) == 1:
            state = "ACTIVE"
            blockers.append("AGENT_WRITE_LIFECYCLE_ACTIVE_AT_CLOSE")
        else:
            state = "UNKNOWN"
            blockers.append(
                "AGENT_WRITE_LIFECYCLE_BINDING_AUTHORITY_MISMATCH"
            )
    elif request_count:
        state = "UNKNOWN"
        blockers.append(
            "AGENT_WRITE_LIFECYCLE_REQUEST_WITHOUT_TERMINAL"
        )

    core = {
        "schemaVersion": REPORT_SCHEMA,
        "cycleInstanceId": manifest["cycleInstanceId"],
        "actor": copy.deepcopy(manifest["actor"]),
        "state": state,
        "latestBindingHash": (
            latest_binding["bindingHash"]
            if latest_binding is not None
            else None
        ),
        "authorityHead": observation.head_sha,
        "authorityNow": observation.authority_now.isoformat().replace(
            "+00:00", "Z"
        ),
        "matchingLeaseIds": sorted(
            lease["leaseId"] for lease in matching
        ),
        "blockers": sorted(set(blockers)),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "reportHash": stable_hash(core)}


def validate_report(value: Any) -> dict[str, Any]:
    fields = {
        "schemaVersion", "cycleInstanceId", "actor", "state",
        "latestBindingHash", "authorityHead", "authorityNow",
        "matchingLeaseIds", "blockers", "readOnly", "semanticAuthority",
        "authorizesMutation", "reportHash",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or value.get("schemaVersion") != REPORT_SCHEMA
        or value.get("state") not in STATES
    ):
        raise AgentWriteLifecycleGuardError(
            "AGENT_WRITE_LIFECYCLE_REPORT_INVALID"
        )

    core = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "reportHash"
    }
    if value.get("reportHash") != stable_hash(core):
        raise AgentWriteLifecycleGuardError(
            "AGENT_WRITE_LIFECYCLE_REPORT_HASH_MISMATCH"
        )
    return value
