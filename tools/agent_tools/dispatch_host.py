from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any

from tools import git_observation, hosted_agent_cycle, hosted_agent_tool, remote_canonical_issue
from tools.agent_tools import admission, contracts, mutation_dispatch, policy as tool_policy
from tools.agent_tools.target_policy import validate_target
from tools.canonical import stable_hash
from tools.coordination_remote import GhApiTransport

ATTEMPT_MARKER = "MOBILIPRESENTER_AGENT_TOOL_MUTATION_ATTEMPT_V0_1"
ATTEMPT_SCHEMA = "AgentToolMutationAttempt 0.1"
MUTABLE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class DispatchHostError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _code(exc: BaseException) -> str:
    value = getattr(exc, "code", None)
    if isinstance(value, str) and value:
        return value
    text = str(exc)
    return text.split(":", 1)[0] if text else exc.__class__.__name__


def _positive_int(value: Any, code: str) -> int:
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise DispatchHostError(code)
    return value


def _json_response(response: Any, code: str) -> Any:
    try:
        return json.loads(response.body)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise DispatchHostError(code) from exc


def _json_after_marker(body: Any, marker: str) -> Any | None:
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


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_ARTIFACT_INVALID", str(path)) from exc
    if not isinstance(value, dict):
        raise DispatchHostError("AGENT_TOOL_DISPATCH_ARTIFACT_INVALID", str(path))
    return value


def load_bundle(root: str | Path) -> dict[str, dict[str, Any]]:
    base = Path(root)
    result = {
        "request": _load(base / "agent-tool-request.json"),
        "plan": _load(base / "agent-tool-plan.json"),
        "proofSet": _load(base / "agent-tool-proof-set.json"),
        "dispatch": _load(base / "agent-tool-dispatch.json"),
        "context": _load(base / "agent-tool-begin-context.json"),
        "manifest": _load(base / "agent-tool-begin-manifest.json"),
    }
    outer_path = base / "agent-tool-outer-request.json"
    if outer_path.is_file():
        result["outerRequest"] = _load(outer_path)
    return result


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
            self.mutable_calls.append({"method": method.upper(), "endpoint": endpoint})
        return self.transport.request(
            method,
            endpoint,
            payload=payload,
            include_headers=include_headers,
        )


def _issue(transport: Any, issue_number: int) -> dict[str, Any]:
    value = _json_response(
        transport.request("GET", f"repos/{hosted_agent_tool.REPOSITORY}/issues/{issue_number}"),
        "AGENT_TOOL_DISPATCH_ISSUE_INVALID",
    )
    if not isinstance(value, dict):
        raise DispatchHostError("AGENT_TOOL_DISPATCH_ISSUE_INVALID")
    return value


def _comment(transport: Any, comment_id: int) -> dict[str, Any]:
    value = _json_response(
        transport.request("GET", f"repos/{hosted_agent_tool.REPOSITORY}/issues/comments/{comment_id}"),
        "AGENT_TOOL_DISPATCH_COMMENT_INVALID",
    )
    if not isinstance(value, dict):
        raise DispatchHostError("AGENT_TOOL_DISPATCH_COMMENT_INVALID")
    return value


def _comments(transport: Any, issue_number: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    page = 1
    while True:
        value = _json_response(
            transport.request(
                "GET",
                f"repos/{hosted_agent_tool.REPOSITORY}/issues/{issue_number}/comments?per_page=100&page={page}",
            ),
            "AGENT_TOOL_DISPATCH_COMMENTS_INVALID",
        )
        if not isinstance(value, list):
            raise DispatchHostError("AGENT_TOOL_DISPATCH_COMMENTS_INVALID")
        batch = [item for item in value if isinstance(item, dict)]
        result.extend(batch)
        if len(value) < 100:
            return result
        page += 1
        if page > 100:
            raise DispatchHostError("AGENT_TOOL_DISPATCH_COMMENTS_UNBOUNDED")


def _validate_original_request(
    request: dict[str, Any],
    dispatch: dict[str, Any],
    *,
    transport: Any,
    outer_request: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    issue_number = dispatch["source"]["issueNumber"]
    comment_id = dispatch["source"]["requestCommentId"]
    issue = _issue(transport, issue_number)
    if issue.get("pull_request") is not None or issue.get("title") != hosted_agent_tool.BUS_TITLE:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_BUS_MISMATCH")
    comment = _comment(transport, comment_id)
    if comment.get("author_association") != "OWNER":
        raise DispatchHostError("AGENT_TOOL_DISPATCH_REQUEST_ACTOR_FORBIDDEN")
    body = comment.get("body")
    if outer_request is None:
        observed = _json_after_marker(body, hosted_agent_tool.REQUEST_MARKER)
        if observed != request:
            raise DispatchHostError("AGENT_TOOL_DISPATCH_REQUEST_READBACK_MISMATCH")
        return
    if manifest is None or context is None:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_OUTER_CONTEXT_REQUIRED")
    observed = _json_after_marker(body, hosted_agent_tool.REQUEST_MARKER_V02)
    if observed != outer_request:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_OUTER_REQUEST_READBACK_MISMATCH")
    try:
        hosted_agent_tool.validate_handle_request(outer_request)
        derived = hosted_agent_tool.derive_handle_request(outer_request, manifest, context)
    except RuntimeError as exc:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_OUTER_REQUEST_INVALID") from exc
    if derived != request:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_DERIVED_REQUEST_MISMATCH")


def _validate_current_policy(
    plan: dict[str, Any], context: dict[str, Any]
) -> None:
    catalog = tool_policy.load_policy()
    semantic = context.get("semanticContext")
    if not isinstance(semantic, dict):
        raise DispatchHostError("AGENT_TOOL_DISPATCH_CONTEXT_INVALID")
    role = plan["actor"]["role"]
    intent = semantic.get("declaredIntent")
    if semantic.get("role") != role:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_CONTEXT_ROLE_MISMATCH")
    tool = catalog["tools"].get(plan["toolId"])
    if not isinstance(tool, dict):
        raise DispatchHostError("AGENT_TOOL_DISPATCH_TOOL_NOT_CURRENT")
    role_policy = tool["roles"].get(role)
    if not isinstance(role_policy, dict) or intent not in role_policy["allowedIntents"]:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_CURRENT_POLICY_FORBIDDEN")
    if tool_policy.effective_mode(tool, role_policy, intent) != "mutation-execute":
        raise DispatchHostError("AGENT_TOOL_DISPATCH_CURRENT_MODE_FORBIDDEN")
    if (
        plan["effectClass"] != tool["effectClass"]
        or plan["adapter"] != tool["adapter"]
        or plan["guards"] != role_policy["guards"]
        or plan["requiredCapabilities"] != role_policy["requiredCapabilities"]
        or plan["targetPolicy"] != role_policy["targetPolicy"]
    ):
        raise DispatchHostError("AGENT_TOOL_DISPATCH_CURRENT_POLICY_MISMATCH")
    validate_target(
        catalog["targetPolicies"][role_policy["targetPolicy"]],
        plan["target"],
        plan["input"],
    )


def _lifecycle_context(
    dispatch: dict[str, Any], *, before_comment_id: int | None
) -> dict[str, Any]:
    return {
        "cycleInstanceId": dispatch["cycleInstanceId"],
        "issueNumber": dispatch["source"]["issueNumber"],
        "beforeCommentId": before_comment_id,
    }


def validate_bundle(
    bundle: dict[str, dict[str, Any]],
    *,
    host_sha: str,
    hosted_run_id: int,
    transport: Any | None = None,
) -> dict[str, dict[str, Any]]:
    carrier = transport or GhApiTransport()
    if not isinstance(host_sha, str) or not SHA_RE.fullmatch(host_sha):
        raise DispatchHostError("AGENT_TOOL_DISPATCH_HOST_SHA_INVALID")
    hosted_run_id = _positive_int(
        hosted_run_id, "AGENT_TOOL_DISPATCH_HOSTED_RUN_ID_INVALID"
    )
    request = contracts.validate_request(bundle["request"])
    plan = contracts.validate_plan(bundle["plan"])
    proof_set = admission.guard_proofs.validate_proof_set(bundle["proofSet"], plan=plan)
    dispatch = mutation_dispatch.validate_dispatch(
        bundle["dispatch"], plan=plan, proof_set=proof_set
    )
    context = bundle["context"]
    manifest = bundle["manifest"]
    hosted_agent_tool.validate_begin_binding(request, manifest, context)
    if contracts.request_hash(request) != dispatch["requestHash"]:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_REQUEST_HASH_MISMATCH")
    if manifest.get("cycleInstanceId") != dispatch["cycleInstanceId"]:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_CYCLE_MISMATCH")
    lifecycle_proof = proof_set["proofs"].get("agent-write-lifecycle-bound")
    if not isinstance(lifecycle_proof, dict) or lifecycle_proof.get("cycleInstanceId") != dispatch["cycleInstanceId"]:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_LIFECYCLE_PROOF_MISMATCH")
    if dispatch["source"]["semanticHostSha"] != host_sha:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_SEMANTIC_HOST_DRIFT")
    if dispatch["source"]["hostedRunId"] != hosted_run_id:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_HOSTED_RUN_MISMATCH")
    _validate_original_request(
        request,
        dispatch,
        transport=carrier,
        outer_request=bundle.get("outerRequest"),
        manifest=manifest,
        context=context,
    )
    _validate_current_policy(plan, context)
    return bundle


def _terminal_matches(payload: Any, dispatch: dict[str, Any]) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("requestHash") == dispatch["requestHash"]
        and payload.get("begin") == dispatch["begin"]
        and payload.get("actor") == dispatch["actor"]
    )


def build_attempt(dispatch: dict[str, Any], *, host_sha: str, run_id: int) -> dict[str, Any]:
    mutation_dispatch.validate_dispatch(dispatch)
    if dispatch["source"]["semanticHostSha"] != host_sha:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_SEMANTIC_HOST_DRIFT")
    core = {
        "schemaVersion": ATTEMPT_SCHEMA,
        "dispatchHash": dispatch["dispatchHash"],
        "requestHash": dispatch["requestHash"],
        "hostSha": host_sha,
        "runId": _positive_int(run_id, "AGENT_TOOL_DISPATCH_RUN_ID_INVALID"),
        "status": "STARTED",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "attemptHash": stable_hash(core)}


def validate_attempt_record(value: Any) -> dict[str, Any]:
    fields = {
        "schemaVersion", "dispatchHash", "requestHash", "hostSha", "runId", "status",
        "semanticAuthority", "authorizesMutation", "attemptHash",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_ATTEMPT_INVALID")
    if value.get("schemaVersion") != ATTEMPT_SCHEMA or value.get("status") != "STARTED":
        raise DispatchHostError("AGENT_TOOL_DISPATCH_ATTEMPT_INVALID")
    for field in ("dispatchHash", "requestHash", "attemptHash"):
        item = value.get(field)
        if not isinstance(item, str) or HASH_RE.fullmatch(item) is None:
            raise DispatchHostError("AGENT_TOOL_DISPATCH_ATTEMPT_INVALID")
    if not isinstance(value.get("hostSha"), str) or SHA_RE.fullmatch(value["hostSha"]) is None:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_ATTEMPT_INVALID")
    _positive_int(value.get("runId"), "AGENT_TOOL_DISPATCH_ATTEMPT_INVALID")
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_ATTEMPT_MUST_NOT_AUTHORIZE")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "attemptHash"}
    if value.get("attemptHash") != stable_hash(core):
        raise DispatchHostError("AGENT_TOOL_DISPATCH_ATTEMPT_HASH_MISMATCH")
    return value


def validate_attempt(value: Any, dispatch: dict[str, Any]) -> dict[str, Any]:
    record = validate_attempt_record(value)
    if (
        record["dispatchHash"] != dispatch["dispatchHash"]
        or record["requestHash"] != dispatch["requestHash"]
        or record["hostSha"] != dispatch["source"]["semanticHostSha"]
    ):
        raise DispatchHostError("AGENT_TOOL_DISPATCH_ATTEMPT_MISMATCH")
    return record


def _hosted_terminal(
    request: dict[str, Any], plan: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    core = {
        "schemaVersion": hosted_agent_tool.RESULT_SCHEMA,
        "requestId": request["requestId"],
        "requestHash": contracts.request_hash(request),
        "begin": copy.deepcopy(request["begin"]),
        "actor": copy.deepcopy(request["actor"]),
        "toolId": request["toolId"],
        "plan": copy.deepcopy(plan),
        "result": copy.deepcopy(result),
        "status": result["status"],
        "blockers": copy.deepcopy(result["blockers"]),
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "hostedResultHash": stable_hash(core)}


def inspect_protocol(
    bundle: dict[str, dict[str, Any]],
    *,
    host_sha: str,
    hosted_run_id: int,
    run_id: int,
    transport: Any | None = None,
) -> dict[str, Any]:
    carrier = transport or GhApiTransport()
    validate_bundle(
        bundle,
        host_sha=host_sha,
        hosted_run_id=hosted_run_id,
        transport=carrier,
    )
    dispatch = bundle["dispatch"]
    comments = _comments(carrier, dispatch["source"]["issueNumber"])
    terminals: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for comment in comments:
        user = comment.get("user") if isinstance(comment, dict) else None
        if not isinstance(user, dict) or user.get("login") != "github-actions[bot]":
            continue
        terminal = _json_after_marker(comment.get("body"), hosted_agent_tool.RESULT_MARKER)
        if _terminal_matches(terminal, dispatch):
            terminals.append(terminal)
        attempt = _json_after_marker(comment.get("body"), ATTEMPT_MARKER)
        if isinstance(attempt, dict) and attempt.get("requestHash") == dispatch["requestHash"]:
            record = validate_attempt_record(attempt)
            if record["hostSha"] != dispatch["source"]["semanticHostSha"]:
                raise DispatchHostError("AGENT_TOOL_DISPATCH_ATTEMPT_MISMATCH")
            attempts.append(record)
    if len(terminals) > 1:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_TERMINAL_DUPLICATE")
    if len(attempts) > 1:
        raise DispatchHostError("AGENT_TOOL_DISPATCH_ATTEMPT_DUPLICATE")
    if terminals:
        return {
            "state": "TERMINAL_EXISTS",
            "terminal": terminals[0],
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
    if attempts:
        observed_head = _observe_branch_head(bundle["plan"], carrier)
        result = mutation_dispatch.build_execution_result(
            bundle["plan"],
            dispatch,
            status="UNKNOWN",
            blockers=["AGENT_TOOL_MUTATION_PRIOR_ATTEMPT_WITHOUT_TERMINAL"],
            mutable_call_count=0,
            observed_branch_head=observed_head,
        )
        return {
            "state": "PRIOR_ATTEMPT_UNKNOWN",
            "terminal": _hosted_terminal(bundle["request"], bundle["plan"], result),
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
    preflight = admission.collect_guard_proofs(
        bundle["plan"],
        transport=carrier,
        lifecycle_context=_lifecycle_context(dispatch, before_comment_id=None),
    )
    admission.assert_execution_admitted(bundle["plan"], preflight)
    return {
        "state": "CLEAR",
        "attempt": build_attempt(dispatch, host_sha=host_sha, run_id=run_id),
        "preflightProofSetHash": preflight["proofSetHash"],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def _observe_branch_head(plan: dict[str, Any], transport: Any) -> str | None:
    try:
        if "path" in plan["target"]:
            observed = git_observation.observe_file(
                plan["target"]["branch"], plan["target"]["path"], transport=transport
            )
        else:
            observed = git_observation.observe_branch(
                plan["target"]["branch"], transport=transport
            )
    except Exception:
        return None
    value = observed.get("branchHead") if isinstance(observed, dict) else None
    return value if isinstance(value, str) else None


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
    validate_bundle(
        bundle,
        host_sha=host_sha,
        hosted_run_id=hosted_run_id,
        transport=base,
    )
    dispatch = bundle["dispatch"]
    attempt_comment = _comment(
        base, _positive_int(attempt_comment_id, "AGENT_TOOL_DISPATCH_ATTEMPT_COMMENT_INVALID")
    )
    user = attempt_comment.get("user")
    attempt = _json_after_marker(attempt_comment.get("body"), ATTEMPT_MARKER)
    if not isinstance(user, dict) or user.get("login") != "github-actions[bot]" or not isinstance(attempt, dict):
        raise DispatchHostError("AGENT_TOOL_DISPATCH_ATTEMPT_COMMENT_INVALID")
    validate_attempt(attempt, dispatch)
    if attempt["runId"] != _positive_int(run_id, "AGENT_TOOL_DISPATCH_RUN_ID_INVALID"):
        raise DispatchHostError("AGENT_TOOL_DISPATCH_ATTEMPT_RUN_MISMATCH")

    tracked = MutationTrackingTransport(base)
    execution_proofs: dict[str, Any] | None = None
    receipt: dict[str, Any] | None = None
    observed_head: str | None = None
    try:
        execution_proofs = admission.collect_guard_proofs(
            bundle["plan"],
            transport=tracked,
            lifecycle_context=_lifecycle_context(dispatch, before_comment_id=None),
        )
        admission.assert_execution_admitted(bundle["plan"], execution_proofs)
        source = {
            "workflow": "agent-tool-mutation-dispatch",
            "sourceSha": host_sha,
            "runId": str(_positive_int(run_id, "AGENT_TOOL_DISPATCH_RUN_ID_INVALID")),
            "issueNumber": dispatch["source"]["issueNumber"],
            "commentId": _positive_int(
                attempt_comment_id, "AGENT_TOOL_DISPATCH_ATTEMPT_COMMENT_INVALID"
            ),
        }
        receipt = remote_canonical_issue.execute_command(
            dispatch["command"], source=source, transport=tracked
        )
        observed_head = receipt["aggregateReadback"].get("branchHead")
        result = mutation_dispatch.build_execution_result(
            bundle["plan"],
            dispatch,
            status="PASS",
            blockers=[],
            execution_proof_set=execution_proofs,
            receipt=receipt,
            mutable_call_count=len(tracked.mutable_calls),
            observed_branch_head=observed_head,
        )
    except Exception as exc:
        observed_head = _observe_branch_head(bundle["plan"], tracked)
        expected_head = dispatch["command"]["expected"].get("branchHead")
        if not tracked.mutable_calls or observed_head == expected_head:
            status = "BLOCKED"
        else:
            status = "UNKNOWN"
        result = mutation_dispatch.build_execution_result(
            bundle["plan"],
            dispatch,
            status=status,
            blockers=[_code(exc)],
            execution_proof_set=execution_proofs,
            mutable_call_count=len(tracked.mutable_calls),
            observed_branch_head=observed_head,
        )
    return _hosted_terminal(bundle["request"], bundle["plan"], result)


def _write(path: str | Path, value: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="agent-tool-dispatch-host")
    sub = parser.add_subparsers(dest="action", required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--artifact-dir", required=True)
    inspect.add_argument("--host-sha", required=True)
    inspect.add_argument("--hosted-run-id", required=True)
    inspect.add_argument("--run-id", required=True)
    inspect.add_argument("--output", required=True)
    execute = sub.add_parser("execute")
    execute.add_argument("--artifact-dir", required=True)
    execute.add_argument("--host-sha", required=True)
    execute.add_argument("--hosted-run-id", required=True)
    execute.add_argument("--run-id", required=True)
    execute.add_argument("--attempt-comment-id", required=True)
    execute.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    bundle = load_bundle(args.artifact_dir)
    hosted_run_id = _positive_int(
        args.hosted_run_id, "AGENT_TOOL_DISPATCH_HOSTED_RUN_ID_INVALID"
    )
    if args.action == "inspect":
        value = inspect_protocol(
            bundle,
            host_sha=args.host_sha,
            hosted_run_id=hosted_run_id,
            run_id=_positive_int(args.run_id, "AGENT_TOOL_DISPATCH_RUN_ID_INVALID"),
        )
    else:
        value = execute_dispatch(
            bundle,
            host_sha=args.host_sha,
            hosted_run_id=hosted_run_id,
            run_id=_positive_int(args.run_id, "AGENT_TOOL_DISPATCH_RUN_ID_INVALID"),
            attempt_comment_id=_positive_int(
                args.attempt_comment_id, "AGENT_TOOL_DISPATCH_ATTEMPT_COMMENT_INVALID"
            ),
        )
    _write(args.output, value)
    print(json.dumps(value, ensure_ascii=False))
    if args.action == "execute" and value.get("status") != "PASS":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
