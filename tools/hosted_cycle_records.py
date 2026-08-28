from __future__ import annotations

import copy
import json
from typing import Any

from tools import agent_cycle_identity, hosted_record_vocabulary as markers
from tools.canonical import stable_hash

CURRENT_REPOSITORY = "EAKerber/MobiliPresenter"

AGENT_TOOL_REQUEST_MARKER = markers.AGENT_TOOL_REQUEST_V01
AGENT_TOOL_REQUEST_MARKER_V02 = markers.AGENT_TOOL_REQUEST_V02
AGENT_TOOL_RESULT_MARKER = markers.AGENT_TOOL_RESULT_V01
AGENT_TOOL_DISPATCH_MARKER = markers.AGENT_TOOL_DISPATCH_V01
REMOTE_REQUEST_MARKER = markers.REMOTE_CANONICAL_REQUEST_V01
REMOTE_RESULT_MARKER = markers.REMOTE_CANONICAL_RESULT_V01
WRITE_LEASE_REQUEST_MARKER = markers.AGENT_WRITE_LEASE_REQUEST_V01
WRITE_LEASE_REQUEST_MARKER_V02 = markers.AGENT_WRITE_LEASE_REQUEST_V02
WRITE_LEASE_RESULT_MARKER = markers.AGENT_WRITE_LEASE_RESULT_V01

STRONG = "STRONG"
AMBIENT = "AMBIENT"


class HostedCycleRecordError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def json_after_marker(body: Any, marker: str) -> Any | None:
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


def comment_id(value: Any) -> int | None:
    item = value.get("id") if isinstance(value, dict) else None
    return item if isinstance(item, int) and not isinstance(item, bool) and item > 0 else None


def request_comment_allowed(comment: Any) -> bool:
    return isinstance(comment, dict) and comment.get("author_association") == "OWNER"


def result_comment_allowed(comment: Any) -> bool:
    user = comment.get("user") if isinstance(comment, dict) else None
    return isinstance(user, dict) and user.get("login") == "github-actions[bot]"


def canonical_actor(value: Any) -> dict[str, str] | None:
    try:
        return agent_cycle_identity.canonical_actor(value)
    except RuntimeError:
        return None


def canonical_begin(value: Any) -> dict[str, Any] | None:
    try:
        return agent_cycle_identity.canonical_begin(value)
    except RuntimeError:
        return None


def cycle_instance_id(manifest: dict[str, Any]) -> str:
    if not isinstance(manifest, dict):
        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_MANIFEST_INVALID")
    declared = manifest.get("cycleInstanceId")
    computed: str | None = None
    source = manifest.get("source")
    if isinstance(source, dict) and isinstance(source.get("issueNumber"), int):
        try:
            computed = agent_cycle_identity.hosted_cycle_instance_id(
                source, manifest.get("actor"), manifest.get("contextHash")
            )
        except RuntimeError as exc:
            raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_INSTANCE_INVALID") from exc
    if declared is not None:
        if (
            not isinstance(declared, str)
            or agent_cycle_identity.CYCLE_INSTANCE_RE.fullmatch(declared) is None
        ):
            raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_INSTANCE_INVALID")
        if computed is not None and declared != computed:
            raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_INSTANCE_MISMATCH")
        return declared
    if computed is None:
        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_INSTANCE_INVALID")
    return computed


def window(
    comments: list[dict[str, Any]], begin_comment_id: int, close_comment_id: int
) -> list[dict[str, Any]]:
    positions = {comment_id(item): index for index, item in enumerate(comments)}
    if begin_comment_id not in positions or close_comment_id not in positions:
        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_WINDOW_COMMENT_MISSING")
    if positions[begin_comment_id] >= positions[close_comment_id]:
        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_WINDOW_ORDER_INVALID")
    return comments[positions[begin_comment_id] + 1:positions[close_comment_id]]


def _claims_begin(value: Any, expected: dict[str, Any]) -> bool:
    return isinstance(value, dict) and all(
        value.get(key) == expected[key] for key in agent_cycle_identity.BEGIN_FIELDS
    )


def _claims_actor(value: Any, expected: dict[str, Any]) -> bool:
    return isinstance(value, dict) and all(
        value.get(key) == expected[key] for key in agent_cycle_identity.ACTOR_FIELDS
    )


def _claims_begin_actor(payload: Any, begin: dict[str, Any], actor: dict[str, Any]) -> bool:
    return (
        isinstance(payload, dict)
        and _claims_begin(payload.get("begin"), begin)
        and _claims_actor(payload.get("actor"), actor)
    )


def _handle_claims_manifest(handle: Any, manifest: dict[str, Any], cycle_id: str) -> bool:
    if not isinstance(handle, dict):
        return False
    context = handle.get("context")
    actor = handle.get("actor")
    if not isinstance(context, dict):
        return False
    if handle.get("cycleInstanceId") != cycle_id:
        return False
    declared_cycle = manifest.get("cycleId")
    if declared_cycle is not None and handle.get("cycleId") != declared_cycle:
        return False
    return (
        context.get("contextHash") == manifest.get("contextHash")
        and _claims_actor(actor, manifest.get("actor") or {})
    )


def _record(
    *, kind: str, comment: dict[str, Any], marker: str, binding: str,
    payload: dict[str, Any], normalized: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cid = comment_id(comment)
    if cid is None:
        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_COMMENT_INVALID")
    return {
        "kind": kind,
        "commentId": cid,
        "marker": marker,
        "binding": binding,
        "payload": copy.deepcopy(payload),
        "normalized": copy.deepcopy(normalized if normalized is not None else payload),
    }


def _validate_strong_tool_v01(
    payload: dict[str, Any], begin: dict[str, Any], actor: dict[str, Any]
) -> dict[str, Any]:
    from tools.agent_tools import contracts

    try:
        value = contracts.validate_request(payload)
    except RuntimeError as exc:
        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_TOOL_REQUEST_INVALID") from exc
    if value["begin"] != begin or value["actor"] != actor:
        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_TOOL_REQUEST_BINDING_MISMATCH")
    return value


def _validate_strong_tool_v02(
    payload: dict[str, Any], manifest: dict[str, Any], begin: dict[str, Any], actor: dict[str, Any]
) -> dict[str, Any]:
    from tools import hosted_handle_requests

    try:
        hosted_handle_requests.validate_tool(payload, repository=CURRENT_REPOSITORY)
        if not hosted_handle_requests.matches_manifest(
            payload.get("handle"), manifest, repository=CURRENT_REPOSITORY
        ):
            raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_TOOL_HANDLE_BINDING_MISMATCH")
        return hosted_handle_requests.build_tool_inner(payload, begin=begin, actor=actor)
    except HostedCycleRecordError:
        raise
    except RuntimeError as exc:
        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_TOOL_REQUEST_INVALID") from exc


def _validate_strong_lease_v01(
    payload: dict[str, Any], begin: dict[str, Any], actor: dict[str, Any]
) -> dict[str, Any]:
    from tools import agent_write_lifecycle as lifecycle

    try:
        value = lifecycle.validate_request(payload)
    except RuntimeError as exc:
        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_LEASE_REQUEST_INVALID") from exc
    if value["begin"] != begin or value["actor"] != actor:
        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_LEASE_REQUEST_BINDING_MISMATCH")
    return value


def _validate_strong_lease_v02(
    payload: dict[str, Any], manifest: dict[str, Any], begin: dict[str, Any], actor: dict[str, Any]
) -> dict[str, Any]:
    from tools import agent_write_lifecycle as lifecycle, hosted_handle_requests

    try:
        hosted_handle_requests.validate_write_lease(payload, repository=CURRENT_REPOSITORY)
        if not hosted_handle_requests.matches_manifest(
            payload.get("handle"), manifest, repository=CURRENT_REPOSITORY
        ):
            raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_LEASE_HANDLE_BINDING_MISMATCH")
        value = hosted_handle_requests.build_write_lease_inner(payload, begin=begin, actor=actor)
        return lifecycle.validate_request(value)
    except HostedCycleRecordError:
        raise
    except RuntimeError as exc:
        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_LEASE_REQUEST_INVALID") from exc


def collect(
    comments: list[dict[str, Any]], manifest: dict[str, Any], *, close_comment_id: int,
) -> dict[str, Any]:
    if not isinstance(comments, list) or not isinstance(manifest, dict):
        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_INPUT_INVALID")
    try:
        begin = agent_cycle_identity.begin_from_manifest(manifest)
        actor = copy.deepcopy(agent_cycle_identity.canonical_actor(manifest.get("actor")))
    except RuntimeError as exc:
        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_MANIFEST_INVALID") from exc
    cycle_id = cycle_instance_id(manifest)
    source = manifest.get("source")
    if not isinstance(source, dict):
        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_MANIFEST_INVALID")
    begin_comment_id = source.get("commentId")
    if not isinstance(begin_comment_id, int) or isinstance(begin_comment_id, bool) or begin_comment_id <= 0:
        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_MANIFEST_INVALID")
    current_window = window(comments, begin_comment_id, close_comment_id)

    records: list[dict[str, Any]] = []
    pending_remote_results: list[tuple[dict[str, Any], dict[str, Any]]] = []
    ambient_remote_hashes: set[str] = set()
    strong_command_hashes: set[str] = set()

    for comment in current_window:
        if not isinstance(comment, dict):
            continue
        body = comment.get("body")

        if request_comment_allowed(comment):
            payload = json_after_marker(body, AGENT_TOOL_REQUEST_MARKER)
            if isinstance(payload, dict) and _claims_begin_actor(payload, begin, actor):
                records.append(_record(
                    kind="agent-tool-request", comment=comment,
                    marker=AGENT_TOOL_REQUEST_MARKER, binding=STRONG,
                    payload=payload,
                    normalized=_validate_strong_tool_v01(payload, begin, actor),
                ))
                continue

            outer = json_after_marker(body, AGENT_TOOL_REQUEST_MARKER_V02)
            if isinstance(outer, dict) and _handle_claims_manifest(outer.get("handle"), manifest, cycle_id):
                records.append(_record(
                    kind="agent-tool-request", comment=comment,
                    marker=AGENT_TOOL_REQUEST_MARKER_V02, binding=STRONG,
                    payload=outer,
                    normalized=_validate_strong_tool_v02(outer, manifest, begin, actor),
                ))
                continue

            lease_payload = json_after_marker(body, WRITE_LEASE_REQUEST_MARKER)
            if isinstance(lease_payload, dict) and _claims_begin_actor(lease_payload, begin, actor):
                records.append(_record(
                    kind="write-lease-request", comment=comment,
                    marker=WRITE_LEASE_REQUEST_MARKER, binding=STRONG,
                    payload=lease_payload,
                    normalized=_validate_strong_lease_v01(lease_payload, begin, actor),
                ))
                continue

            lease_outer = json_after_marker(body, WRITE_LEASE_REQUEST_MARKER_V02)
            if isinstance(lease_outer, dict) and _handle_claims_manifest(lease_outer.get("handle"), manifest, cycle_id):
                records.append(_record(
                    kind="write-lease-request", comment=comment,
                    marker=WRITE_LEASE_REQUEST_MARKER_V02, binding=STRONG,
                    payload=lease_outer,
                    normalized=_validate_strong_lease_v02(lease_outer, manifest, begin, actor),
                ))
                continue

            remote_payload = json_after_marker(body, REMOTE_REQUEST_MARKER)
            if isinstance(remote_payload, dict) and _claims_actor(remote_payload.get("actor"), actor):
                from tools import remote_canonical_execution

                try:
                    normalized = remote_canonical_execution.validate_command(remote_payload)
                except RuntimeError:
                    normalized = remote_payload
                ambient_remote_hashes.add(stable_hash(remote_payload))
                records.append(_record(
                    kind="remote-request", comment=comment,
                    marker=REMOTE_REQUEST_MARKER, binding=AMBIENT,
                    payload=remote_payload, normalized=normalized,
                ))
                continue

        if result_comment_allowed(comment):
            dispatch_payload = json_after_marker(body, AGENT_TOOL_DISPATCH_MARKER)
            if isinstance(dispatch_payload, dict):
                declared_instance = dispatch_payload.get("cycleInstanceId")
                if declared_instance == cycle_id or (
                    declared_instance is None and _claims_begin_actor(dispatch_payload, begin, actor)
                ):
                    from tools.agent_tools import mutation_dispatch

                    try:
                        mutation_dispatch.validate_dispatch(dispatch_payload)
                    except RuntimeError as exc:
                        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_TOOL_DISPATCH_INVALID") from exc
                    if (
                        dispatch_payload.get("cycleInstanceId") != cycle_id
                        or dispatch_payload.get("begin") != begin
                        or dispatch_payload.get("actor") != actor
                    ):
                        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_TOOL_DISPATCH_BINDING_MISMATCH")
                    strong_command_hashes.add(dispatch_payload["commandHash"])
                    records.append(_record(
                        kind="agent-tool-dispatch", comment=comment,
                        marker=AGENT_TOOL_DISPATCH_MARKER, binding=STRONG,
                        payload=dispatch_payload,
                    ))
                continue

            tool_result = json_after_marker(body, AGENT_TOOL_RESULT_MARKER)
            if isinstance(tool_result, dict) and _claims_begin_actor(tool_result, begin, actor):
                records.append(_record(
                    kind="agent-tool-result", comment=comment,
                    marker=AGENT_TOOL_RESULT_MARKER, binding=STRONG,
                    payload=tool_result,
                ))
                continue

            lease_result = json_after_marker(body, WRITE_LEASE_RESULT_MARKER)
            if isinstance(lease_result, dict):
                declared_instance = lease_result.get("cycleInstanceId")
                if declared_instance == cycle_id or (
                    declared_instance is None and _claims_begin_actor(lease_result, begin, actor)
                ):
                    from tools import agent_write_lifecycle as lifecycle

                    try:
                        normalized = lifecycle.validate_result(lease_result)
                    except RuntimeError as exc:
                        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_LEASE_RESULT_INVALID") from exc
                    if (
                        normalized.get("cycleInstanceId") != cycle_id
                        or normalized.get("begin") != begin
                        or normalized.get("actor") != actor
                    ):
                        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_LEASE_RESULT_BINDING_MISMATCH")
                    records.append(_record(
                        kind="write-lease-result", comment=comment,
                        marker=WRITE_LEASE_RESULT_MARKER, binding=STRONG,
                        payload=lease_result, normalized=normalized,
                    ))
                continue

            remote_result = json_after_marker(body, REMOTE_RESULT_MARKER)
            if isinstance(remote_result, dict):
                pending_remote_results.append((comment, remote_result))

    # Binding and semantic validity are distinct. A remote result can have
    # strong lineage to a cycle-owned dispatch while still be incomplete or
    # malformed for a particular consumer. The scanner classifies lineage only;
    # receipt consumers perform the full RemoteCanonical receipt validation.
    for comment, payload in pending_remote_results:
        digest = payload.get("commandHash")
        if not isinstance(digest, str) or len(digest) != 64:
            continue
        if digest in strong_command_hashes:
            records.append(_record(
                kind="remote-result", comment=comment,
                marker=REMOTE_RESULT_MARKER, binding=STRONG,
                payload=payload,
            ))
        elif digest in ambient_remote_hashes:
            records.append(_record(
                kind="remote-result", comment=comment,
                marker=REMOTE_RESULT_MARKER, binding=AMBIENT,
                payload=payload,
            ))

    records.sort(key=lambda item: item["commentId"])
    return {
        "cycleInstanceId": cycle_id,
        "begin": begin,
        "actor": actor,
        "beginCommentId": begin_comment_id,
        "closeCommentId": close_comment_id,
        "records": records,
    }


def records_of(
    view: dict[str, Any], kind: str, *, binding: str | None = None,
) -> list[dict[str, Any]]:
    records = view.get("records") if isinstance(view, dict) else None
    if not isinstance(records, list):
        raise HostedCycleRecordError("HOSTED_CYCLE_RECORD_VIEW_INVALID")
    result = [item for item in records if isinstance(item, dict) and item.get("kind") == kind]
    if binding is not None:
        result = [item for item in result if item.get("binding") == binding]
    return result
