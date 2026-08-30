from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from tools import agent_write_lifecycle as lifecycle
from tools import coordination, hosted_agent_cycle, hosted_agent_write_lease, hosted_cycle_records, remote_canonical_issue
from tools.agent_tools import contracts, policy as tool_policy
from tools.coordination_remote import GhApiTransport, GitHubCoordinationAuthority

MUTABLE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
PREDECESSOR_WAITING = "PREDECESSOR_WAITING"
PREDECESSOR_UNKNOWN = "PREDECESSOR_UNKNOWN"


class AgentWriteLifecycleHostError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


class MutationTrackingTransport:
    def __init__(self, transport: Any) -> None:
        self.transport = transport
        self.mutable_calls: list[dict[str, str]] = []

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        payload: Any = None,
        include_headers: bool = False,
    ) -> Any:
        if method.upper() in MUTABLE_METHODS:
            self.mutable_calls.append(
                {"method": method.upper(), "endpoint": endpoint}
            )
        return self.transport.request(
            method,
            endpoint,
            payload=payload,
            include_headers=include_headers,
        )


def _load(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_ARTIFACT_INVALID"
        ) from exc
    if not isinstance(value, dict):
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_ARTIFACT_INVALID"
        )
    return value


def load_bundle(root: str | Path) -> dict[str, dict[str, Any]]:
    base = Path(root)
    result = {
        "request": _load(base / "agent-write-lease-request.json"),
        "dispatch": _load(base / "agent-write-lease-dispatch.json"),
        "context": _load(base / "agent-write-lease-begin-context.json"),
        "manifest": _load(base / "agent-write-lease-begin-manifest.json"),
    }
    outer_path = base / "agent-write-lease-outer-request.json"
    if outer_path.is_file():
        result["outerRequest"] = _load(outer_path)
    return result


def _json_response(response: Any, code: str) -> Any:
    try:
        return json.loads(response.body)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise AgentWriteLifecycleHostError(code) from exc


def _comment(transport: Any, comment_id: int) -> dict[str, Any]:
    value = _json_response(
        transport.request(
            "GET",
            f"repos/{hosted_agent_cycle.REPOSITORY}/issues/comments/{comment_id}",
        ),
        "AGENT_WRITE_LIFECYCLE_COMMENT_INVALID",
    )
    if not isinstance(value, dict):
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_COMMENT_INVALID"
        )
    return value


def _comments(transport: Any, issue_number: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for page in range(1, 101):
        value = _json_response(
            transport.request(
                "GET",
                f"repos/{hosted_agent_cycle.REPOSITORY}/issues/{issue_number}/comments?per_page=100&page={page}",
            ),
            "AGENT_WRITE_LIFECYCLE_COMMENTS_INVALID",
        )
        if not isinstance(value, list):
            raise AgentWriteLifecycleHostError(
                "AGENT_WRITE_LIFECYCLE_COMMENTS_INVALID"
            )
        result.extend(item for item in value if isinstance(item, dict))
        if len(value) < 100:
            return result
    raise AgentWriteLifecycleHostError(
        "AGENT_WRITE_LIFECYCLE_COMMENTS_UNBOUNDED"
    )


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


def _validate_request_readback(
    request: dict[str, Any],
    dispatch: dict[str, Any],
    *,
    manifest: dict[str, Any],
    context: dict[str, Any],
    transport: Any,
    outer_request: dict[str, Any] | None,
) -> None:
    comment = _comment(transport, dispatch["source"]["requestCommentId"])
    if comment.get("author_association") != "OWNER":
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_REQUEST_ACTOR_FORBIDDEN"
        )
    body = comment.get("body")
    if outer_request is None:
        if _payload(body, lifecycle.REQUEST_MARKER) != request:
            raise AgentWriteLifecycleHostError(
                "AGENT_WRITE_LIFECYCLE_REQUEST_READBACK_MISMATCH"
            )
        return
    observed = _payload(body, hosted_agent_write_lease.REQUEST_MARKER_V02)
    if observed != outer_request:
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_OUTER_REQUEST_READBACK_MISMATCH"
        )
    try:
        derived = hosted_agent_write_lease.derive_handle_request(
            outer_request, manifest, context
        )
    except RuntimeError as exc:
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_OUTER_REQUEST_INVALID"
        ) from exc
    if derived != request:
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_DERIVED_REQUEST_MISMATCH"
        )


def _validate_bundle(
    bundle: dict[str, dict[str, Any]],
    *,
    host_sha: str,
    hosted_run_id: int,
    transport: Any,
) -> dict[str, dict[str, Any]]:
    request = lifecycle.validate_request(bundle["request"])
    dispatch = lifecycle.validate_dispatch(bundle["dispatch"])
    manifest = bundle["manifest"]
    context = bundle["context"]
    lifecycle.validate_begin_binding(request, manifest, context)
    if dispatch["requestHash"] != lifecycle.request_hash(request):
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_REQUEST_HASH_MISMATCH"
        )
    if (
        dispatch["source"]["semanticHostSha"] != host_sha
        or dispatch["source"]["hostedRunId"] != hosted_run_id
    ):
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_HOST_BINDING_MISMATCH"
        )

    _validate_request_readback(
        request,
        dispatch,
        manifest=manifest,
        context=context,
        transport=transport,
        outer_request=bundle.get("outerRequest"),
    )

    current = lifecycle.prepare_dispatch(
        request,
        manifest,
        context,
        issue_number=dispatch["source"]["issueNumber"],
        request_comment_id=dispatch["source"]["requestCommentId"],
        hosted_run_id=dispatch["source"]["hostedRunId"],
        transport=transport,
    )
    if current != dispatch:
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_DISPATCH_DRIFT"
        )
    return bundle


def _terminal_matches(
    value: Any,
    dispatch: dict[str, Any],
) -> bool:
    return (
        isinstance(value, dict)
        and value.get("schemaVersion")
        in {lifecycle.RESULT_SCHEMA, lifecycle.FAILURE_SCHEMA}
        and value.get("requestHash") == dispatch["requestHash"]
        and value.get("begin") == dispatch["begin"]
        and value.get("actor") == dispatch["actor"]
        and value.get("branch") == dispatch["branch"]
    )


def _mutation_tool_is_executable(
    request: dict[str, Any],
    context: dict[str, Any],
) -> bool:
    try:
        catalog = tool_policy.load_policy()
        tool = catalog["tools"].get(request["toolId"])
        if not isinstance(tool, dict) or tool.get("effectClass") != "shared-durable-mutation":
            return False
        role_policy = tool["roles"].get(request["actor"]["role"])
        if not isinstance(role_policy, dict):
            return False
        semantic = context.get("semanticContext")
        if not isinstance(semantic, dict):
            raise AgentWriteLifecycleHostError(
                "AGENT_WRITE_LIFECYCLE_PREDECESSOR_CONTEXT_INVALID"
            )
        return (
            tool_policy.effective_mode(
                tool,
                role_policy,
                semantic.get("declaredIntent"),
            )
            == "mutation-execute"
        )
    except AgentWriteLifecycleHostError:
        raise
    except RuntimeError as exc:
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_PREDECESSOR_POLICY_INVALID"
        ) from exc


def _mutation_predecessor_fence(
    comments: list[dict[str, Any]],
    bundle: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    dispatch = bundle["dispatch"]
    request = bundle["request"]
    manifest = bundle["manifest"]
    context = bundle["context"]
    if dispatch["action"] != "release":
        return {"state": "CLEAR", "predecessorRequestCommentIds": []}

    request_comment_id = dispatch["source"]["requestCommentId"]
    try:
        view = hosted_cycle_records.collect(
            comments,
            manifest,
            close_comment_id=request_comment_id,
        )
    except hosted_cycle_records.HostedCycleRecordError as exc:
        raise AgentWriteLifecycleHostError(exc.code) from exc

    predecessors: list[dict[str, Any]] = []
    for item in hosted_cycle_records.records_of(
        view,
        "agent-tool-request",
        binding=hosted_cycle_records.STRONG,
    ):
        candidate = item["normalized"]
        if candidate["target"].get("branch") != dispatch["branch"]:
            continue
        if not _mutation_tool_is_executable(candidate, context):
            continue
        predecessors.append(
            {
                "commentId": item["commentId"],
                "requestHash": contracts.request_hash(candidate),
            }
        )

    if not predecessors:
        return {"state": "CLEAR", "predecessorRequestCommentIds": []}

    results: dict[str, dict[str, Any]] = {}
    for comment in comments:
        if not hosted_cycle_records.result_comment_allowed(comment):
            continue
        payload = _payload(
            comment.get("body"),
            hosted_cycle_records.AGENT_TOOL_RESULT_MARKER,
        )
        if not isinstance(payload, dict):
            continue
        digest = payload.get("requestHash")
        if not isinstance(digest, str):
            continue
        if digest not in {item["requestHash"] for item in predecessors}:
            continue
        if (
            payload.get("begin") != dispatch["begin"]
            or payload.get("actor") != dispatch["actor"]
        ):
            raise AgentWriteLifecycleHostError(
                "AGENT_WRITE_LIFECYCLE_PREDECESSOR_RESULT_BINDING_MISMATCH"
            )
        if digest in results:
            raise AgentWriteLifecycleHostError(
                "AGENT_WRITE_LIFECYCLE_PREDECESSOR_RESULT_DUPLICATE"
            )
        results[digest] = payload

    waiting: list[int] = []
    unknown: list[int] = []
    for predecessor in predecessors:
        result = results.get(predecessor["requestHash"])
        if result is None:
            waiting.append(predecessor["commentId"])
            continue
        status = result.get("status")
        if status in {"PASS", "BLOCKED"}:
            continue
        if status == "UNKNOWN":
            unknown.append(predecessor["commentId"])
            continue
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_PREDECESSOR_RESULT_INVALID"
        )

    predecessor_ids = sorted(item["commentId"] for item in predecessors)
    if unknown:
        failure = lifecycle.build_failure(
            request,
            status="UNKNOWN",
            blockers=["AGENT_WRITE_LIFECYCLE_MUTATION_PREDECESSOR_UNKNOWN"],
            authority_head=dispatch["authorityHead"],
        )
        return {
            "state": PREDECESSOR_UNKNOWN,
            "terminal": failure,
            "predecessorRequestCommentIds": predecessor_ids,
            "unknownPredecessorRequestCommentIds": sorted(unknown),
        }
    if waiting:
        return {
            "state": PREDECESSOR_WAITING,
            "predecessorRequestCommentIds": predecessor_ids,
            "waitingPredecessorRequestCommentIds": sorted(waiting),
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
    return {
        "state": "CLEAR",
        "predecessorRequestCommentIds": predecessor_ids,
    }


def inspect_protocol(
    bundle: dict[str, dict[str, Any]],
    *,
    host_sha: str,
    hosted_run_id: int,
    run_id: int,
    transport: Any | None = None,
) -> dict[str, Any]:
    carrier = transport or GhApiTransport()
    _validate_bundle(
        bundle,
        host_sha=host_sha,
        hosted_run_id=hosted_run_id,
        transport=carrier,
    )
    dispatch = bundle["dispatch"]
    terminals: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    comments = _comments(
        carrier,
        dispatch["source"]["issueNumber"],
    )

    for comment in comments:
        user = comment.get("user")
        if (
            not isinstance(user, dict)
            or user.get("login") != "github-actions[bot]"
        ):
            continue
        terminal = _payload(
            comment.get("body"),
            lifecycle.RESULT_MARKER,
        )
        if _terminal_matches(terminal, dispatch):
            terminals.append(terminal)
        attempt = _payload(
            comment.get("body"),
            lifecycle.ATTEMPT_MARKER,
        )
        if (
            isinstance(attempt, dict)
            and attempt.get("requestHash") == dispatch["requestHash"]
        ):
            record = lifecycle.validate_attempt_record(attempt)
            if record["hostSha"] != dispatch["source"]["semanticHostSha"]:
                raise AgentWriteLifecycleHostError(
                    "AGENT_WRITE_LIFECYCLE_ATTEMPT_MISMATCH"
                )
            attempts.append(record)

    if len(terminals) > 1:
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_TERMINAL_DUPLICATE"
        )
    if len(attempts) > 1:
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_ATTEMPT_DUPLICATE"
        )
    if terminals:
        return {
            "state": "TERMINAL_EXISTS",
            "terminal": terminals[0],
        }
    if attempts:
        failure = lifecycle.build_failure(
            bundle["request"],
            status="UNKNOWN",
            blockers=[
                "AGENT_WRITE_LIFECYCLE_PRIOR_ATTEMPT_WITHOUT_TERMINAL"
            ],
            authority_head=dispatch["authorityHead"],
        )
        return {
            "state": "PRIOR_ATTEMPT_UNKNOWN",
            "terminal": failure,
        }

    predecessor = _mutation_predecessor_fence(comments, bundle)
    if predecessor["state"] != "CLEAR":
        return predecessor

    return {
        "state": "CLEAR",
        "attempt": lifecycle.build_attempt(
            dispatch,
            run_id=run_id,
            host_sha=host_sha,
        ),
        "predecessorRequestCommentIds": predecessor[
            "predecessorRequestCommentIds"
        ],
    }


def _expected_owner(dispatch: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": dispatch["actor"]["role"],
        "session": dispatch["actor"]["sessionId"],
        "branch": dispatch["branch"],
        "pr": None,
    }


def _active_bound_lease(
    observation: Any,
    dispatch: dict[str, Any],
) -> dict[str, Any] | None:
    resource = f"branch:{dispatch['branch']}"
    owner = _expected_owner(dispatch)
    active = coordination.active_leases(
        observation.state,
        observation.authority_now,
    )
    action = dispatch["action"]

    if action == "acquire":
        matches = [
            lease
            for lease in active
            if lease.get("resource") == resource
            and lease.get("owner") == owner
        ]
        if len(matches) != 1:
            raise AgentWriteLifecycleHostError(
                "AGENT_WRITE_LIFECYCLE_ACTIVE_READBACK_MISMATCH"
            )
        return matches[0]

    matches = [
        lease
        for lease in active
        if lease.get("leaseId") == dispatch["previousLeaseId"]
        and lease.get("resource") == resource
        and lease.get("owner") == owner
    ]
    if action == "release":
        if matches:
            raise AgentWriteLifecycleHostError(
                "AGENT_WRITE_LIFECYCLE_RELEASE_READBACK_MISMATCH"
            )
        return None

    if len(matches) != 1:
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_ACTIVE_READBACK_MISMATCH"
        )
    return matches[0]


def execute_dispatch(
    bundle: dict[str, dict[str, Any]],
    *,
    host_sha: str,
    hosted_run_id: int,
    run_id: int,
    attempt_comment_id: int,
    transport: Any | None = None,
) -> dict[str, Any]:
    base = transport or GhApiTransport()
    _validate_bundle(
        bundle,
        host_sha=host_sha,
        hosted_run_id=hosted_run_id,
        transport=base,
    )
    dispatch = bundle["dispatch"]

    attempt_comment = _comment(base, attempt_comment_id)
    user = attempt_comment.get("user")
    attempt = _payload(
        attempt_comment.get("body"),
        lifecycle.ATTEMPT_MARKER,
    )
    if (
        not isinstance(user, dict)
        or user.get("login") != "github-actions[bot]"
        or not isinstance(attempt, dict)
    ):
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_ATTEMPT_COMMENT_INVALID"
        )
    try:
        lifecycle.validate_attempt(attempt, dispatch)
    except RuntimeError as exc:
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_ATTEMPT_MISMATCH"
        ) from exc
    if attempt["runId"] != run_id:
        raise AgentWriteLifecycleHostError(
            "AGENT_WRITE_LIFECYCLE_ATTEMPT_MISMATCH"
        )

    tracked = MutationTrackingTransport(base)
    try:
        _validate_bundle(
            bundle,
            host_sha=host_sha,
            hosted_run_id=hosted_run_id,
            transport=tracked,
        )
        receipt = remote_canonical_issue.execute_command(
            dispatch["command"],
            source={
                "workflow": "agent-write-lease-dispatch",
                "sourceSha": host_sha,
                "runId": str(run_id),
                "issueNumber": dispatch["source"]["issueNumber"],
                "commentId": attempt_comment_id,
            },
            transport=tracked,
        )
        authority = GitHubCoordinationAuthority(
            transport=tracked
        )
        observation = authority.observe()
        active_lease = _active_bound_lease(
            observation,
            dispatch,
        )
        binding = lifecycle.build_binding(
            dispatch,
            authority_head_after=observation.head_sha,
            active_lease=active_lease,
            receipt_hash=receipt["receiptHash"],
        )
        return lifecycle.build_success_result(
            bundle["request"],
            dispatch,
            receipt=receipt,
            binding=binding,
        )
    except Exception as exc:
        code = getattr(exc, "code", None)
        if not isinstance(code, str) or not code:
            text = str(exc)
            code = (
                text.split(":", 1)[0]
                if text
                else exc.__class__.__name__
            )
        authority_head = None
        try:
            authority_head = GitHubCoordinationAuthority(
                transport=base
            ).observe().head_sha
        except Exception:
            pass
        return lifecycle.build_failure(
            bundle["request"],
            status=(
                "UNKNOWN"
                if tracked.mutable_calls
                else "BLOCKED"
            ),
            blockers=[code],
            authority_head=authority_head,
        )


def _write(
    path: str | Path,
    value: dict[str, Any],
) -> None:
    Path(path).write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="agent-write-lifecycle-host"
    )
    sub = parser.add_subparsers(
        dest="action",
        required=True,
    )
    for name in ("inspect", "execute"):
        item = sub.add_parser(name)
        item.add_argument("--artifact-dir", required=True)
        item.add_argument("--host-sha", required=True)
        item.add_argument(
            "--hosted-run-id",
            required=True,
            type=int,
        )
        item.add_argument(
            "--run-id",
            required=True,
            type=int,
        )
        item.add_argument("--output", required=True)
        if name == "execute":
            item.add_argument(
                "--attempt-comment-id",
                required=True,
                type=int,
            )

    args = parser.parse_args(argv)
    bundle = load_bundle(args.artifact_dir)
    if args.action == "inspect":
        value = inspect_protocol(
            bundle,
            host_sha=args.host_sha,
            hosted_run_id=args.hosted_run_id,
            run_id=args.run_id,
        )
    else:
        value = execute_dispatch(
            bundle,
            host_sha=args.host_sha,
            hosted_run_id=args.hosted_run_id,
            run_id=args.run_id,
            attempt_comment_id=args.attempt_comment_id,
        )
    _write(args.output, value)
    print(json.dumps(value, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
