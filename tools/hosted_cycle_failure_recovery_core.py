#!/usr/bin/env python3
"""Current-carrier recovery certificate for a failed Hosted Agent Cycle close."""
from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import (
    agent_failure,
    agent_write_lifecycle_guard,
    hosted_agent_cycle,
    hosted_cycle_external_delta_provider,
    hosted_cycle_external_delta_recovery,
    hosted_cycle_handle,
    hosted_cycle_records,
    hosted_issue_bus,
)
from tools.canonical import stable_hash
from tools.coordination_remote import GhApiTransport

REPOSITORY = hosted_agent_cycle.REPOSITORY
BUS_TITLE = hosted_agent_cycle.BUS_TITLE
REQUEST_MARKER = "MOBILIPRESENTER_AGENT_CYCLE_RECOVERY_REQUEST_V0_1"
RESULT_MARKER = "MOBILIPRESENTER_AGENT_CYCLE_RECOVERY_V0_1"
REQUEST_SCHEMA = "HostedAgentCycleRecoveryRequest 0.1"
RESULT_SCHEMA = "HostedAgentCycleRecovery 0.1"
RESULT_SCHEMA_V02 = "HostedAgentCycleRecovery 0.2"
REQUEST_FIELDS = {
    "schemaVersion", "requestId", "handle", "closeRequestCommentId",
    "semanticAuthority", "authorizesMutation",
}
RESULT_FIELDS = {
    "schemaVersion", "requestId", "cycleInstanceId", "handleHash",
    "beginRequestCommentId", "closeRequestCommentId", "closeCommandHash",
    "failedCloseResultCommentId", "failedCloseFailureHash",
    "writeLifecycleReportHash", "authorityHead", "state", "reasonCodes",
    "readOnly", "semanticAuthority", "authorizesMutation", "recoveryHash",
}
RESULT_V02_EXTRA_FIELDS = {
    "failedCloseRunId", "failedCloseClosureHash", "failedCloseReceiptHash",
    "nonInterferenceEvidenceHash", "reconciledClosureHash",
    "reconciledReceiptHash",
}
RESULT_V02_FIELDS = RESULT_FIELDS | RESULT_V02_EXTRA_FIELDS
RECOVERABLE_CAUSES = {
    "AGENT_WRITE_LIFECYCLE_UNKNOWN_FAILURE_AT_CLOSE",
    "AGENT_WRITE_LIFECYCLE_UNKNOWN_AT_CLOSE",
}
EXTERNAL_RECOVERABLE_CAUSES = {
    "UNATTRIBUTED_DURABLE_DELTA",
    "HOSTED_AGENT_CLOSE_NOT_PASS",
}
RECOVERY_REASON = "WRITE_AUTHORITY_CANONICALLY_NEUTRALIZED"
EXTERNAL_RECOVERY_REASON = "EXTERNAL_DURABLE_DELTA_RECONCILED"


class HostedCycleFailureRecoveryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _positive(value: Any, code: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise HostedCycleFailureRecoveryError(code)
    return value


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HostedCycleFailureRecoveryError(code)
    return value.strip()


def _hash(value: Any, code: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise HostedCycleFailureRecoveryError(code)
    return value


def _sha(value: Any, code: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) not in {40, 64}
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise HostedCycleFailureRecoveryError(code)
    return value


def _load(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_ARTIFACT_INVALID"
        ) from exc
    if not isinstance(value, dict):
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_ARTIFACT_INVALID"
        )
    return value


def _write(path: str | Path, value: dict[str, Any]) -> None:
    Path(path).write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != REQUEST_FIELDS:
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_REQUEST_INVALID"
        )
    if value.get("schemaVersion") != REQUEST_SCHEMA:
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_REQUEST_INVALID"
        )
    _text(value.get("requestId"), "HOSTED_CYCLE_RECOVERY_REQUEST_INVALID")
    try:
        hosted_cycle_handle.decode_handle(
            value.get("handle"), repository=REPOSITORY
        )
    except RuntimeError as exc:
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_HANDLE_INVALID"
        ) from exc
    _positive(
        value.get("closeRequestCommentId"),
        "HOSTED_CYCLE_RECOVERY_CLOSE_COMMENT_INVALID",
    )
    if (
        value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_REQUEST_MUST_NOT_AUTHORIZE"
        )
    return value


def _validate_certificate_common(value: dict[str, Any]) -> None:
    if (
        value.get("state") != "RECOVERED"
        or value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_RESULT_INVALID"
        )
    _text(value.get("requestId"), "HOSTED_CYCLE_RECOVERY_RESULT_INVALID")
    cycle_id = value.get("cycleInstanceId")
    if (
        not isinstance(cycle_id, str)
        or hosted_agent_cycle.CYCLE_INSTANCE_RE.fullmatch(cycle_id) is None
    ):
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_RESULT_INVALID"
        )
    for field in (
        "beginRequestCommentId", "closeRequestCommentId",
        "failedCloseResultCommentId",
    ):
        _positive(value.get(field), "HOSTED_CYCLE_RECOVERY_RESULT_INVALID")
    for field in (
        "handleHash", "closeCommandHash", "failedCloseFailureHash",
        "writeLifecycleReportHash", "recoveryHash",
    ):
        _hash(value.get(field), "HOSTED_CYCLE_RECOVERY_RESULT_INVALID")
    _sha(value.get("authorityHead"), "HOSTED_CYCLE_RECOVERY_RESULT_INVALID")
    if not (
        value["beginRequestCommentId"]
        < value["closeRequestCommentId"]
        < value["failedCloseResultCommentId"]
    ):
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_ORDER_INVALID"
        )


def validate_certificate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_RESULT_INVALID"
        )
    schema = value.get("schemaVersion")
    if schema == RESULT_SCHEMA:
        if set(value) != RESULT_FIELDS or value.get("reasonCodes") != [RECOVERY_REASON]:
            raise HostedCycleFailureRecoveryError(
                "HOSTED_CYCLE_RECOVERY_RESULT_INVALID"
            )
    elif schema == RESULT_SCHEMA_V02:
        if (
            set(value) != RESULT_V02_FIELDS
            or value.get("reasonCodes") != [EXTERNAL_RECOVERY_REASON]
        ):
            raise HostedCycleFailureRecoveryError(
                "HOSTED_CYCLE_RECOVERY_RESULT_INVALID"
            )
        _positive(
            value.get("failedCloseRunId"),
            "HOSTED_CYCLE_RECOVERY_RESULT_INVALID",
        )
        for field in (
            "failedCloseClosureHash", "failedCloseReceiptHash",
            "nonInterferenceEvidenceHash", "reconciledClosureHash",
            "reconciledReceiptHash",
        ):
            _hash(value.get(field), "HOSTED_CYCLE_RECOVERY_RESULT_INVALID")
    else:
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_RESULT_INVALID"
        )
    _validate_certificate_common(value)
    core = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "recoveryHash"
    }
    if value["recoveryHash"] != stable_hash(core):
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_HASH_MISMATCH"
        )
    return value


def _request_event(comment: dict[str, Any], issue_number: int) -> dict[str, Any]:
    return {
        "issue": {
            "number": issue_number,
            "title": BUS_TITLE,
            "pull_request": None,
        },
        "comment": {
            "id": hosted_cycle_records.comment_id(comment),
            "body": comment.get("body"),
            "author_association": comment.get("author_association"),
        },
        "repository": {"full_name": REPOSITORY},
    }


def _exact_close(
    comments: list[dict[str, Any]],
    request: dict[str, Any],
    *,
    issue_number: int,
) -> tuple[dict[str, Any], str]:
    close_id = request["closeRequestCommentId"]
    matches = [
        item
        for item in comments
        if hosted_cycle_records.comment_id(item) == close_id
    ]
    if len(matches) != 1 or not hosted_cycle_records.request_comment_allowed(
        matches[0]
    ):
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_CLOSE_REQUEST_INVALID"
        )
    try:
        command, _ = hosted_agent_cycle.parse_event(
            _request_event(matches[0], issue_number)
        )
    except RuntimeError as exc:
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_CLOSE_REQUEST_INVALID"
        ) from exc
    if (
        command.get("action") != "close"
        or command.get("schemaVersion") != hosted_agent_cycle.COMMAND_SCHEMA_V02
        or command.get("handle") != request["handle"]
    ):
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_CLOSE_BINDING_MISMATCH"
        )
    return command, hosted_agent_cycle.transport_command_hash(command)


def _exact_failed_close(
    comments: list[dict[str, Any]],
    *,
    close_comment_id: int,
    close_command: dict[str, Any],
    close_command_hash: str,
) -> tuple[int, dict[str, Any], set[str]]:
    found: list[tuple[int, dict[str, Any], set[str]]] = []
    for comment in comments:
        cid = hosted_cycle_records.comment_id(comment)
        if (
            cid is None
            or cid <= close_comment_id
            or not hosted_cycle_records.result_comment_allowed(comment)
        ):
            continue
        value = hosted_cycle_records.json_after_marker(
            comment.get("body"), hosted_agent_cycle.RESULT_MARKER
        )
        if (
            not isinstance(value, dict)
            or value.get("schemaVersion")
            != agent_failure.HOSTED_CYCLE_FAILURE_SCHEMA
        ):
            continue
        try:
            failure = agent_failure.validate_hosted_cycle_failure(value)
        except RuntimeError:
            continue
        if (
            failure.get("requestId") != close_command["requestId"]
            or failure.get("commandHash") != close_command_hash
        ):
            continue
        causes = {
            item["code"]
            for item in failure["failureCore"]["causes"]
            if isinstance(item, dict) and isinstance(item.get("code"), str)
        }
        if not (
            RECOVERABLE_CAUSES.issubset(causes)
            or EXTERNAL_RECOVERABLE_CAUSES.issubset(causes)
        ):
            raise HostedCycleFailureRecoveryError(
                "HOSTED_CYCLE_RECOVERY_FAILURE_NOT_SUPPORTED"
            )
        found.append((cid, failure, causes))
    if len(found) != 1:
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_FAILURE_AMBIGUOUS"
        )
    return found[0]


def _context_work(context: dict[str, Any]) -> dict[str, Any]:
    work_ref = context.get("workRef")
    work_id = work_ref.get("workId") if isinstance(work_ref, dict) else None
    sensors = context.get("projectMachine", {}).get("sensors", {})
    continuation = sensors.get("continuations", {}) if isinstance(sensors, dict) else {}
    items = continuation.get("data", {}).get("items", []) if isinstance(continuation, dict) else []
    matches = [
        item for item in items
        if isinstance(item, dict) and item.get("id") == work_id
    ]
    if not isinstance(work_id, str) or len(matches) != 1:
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_WORK_UNAVAILABLE"
        )
    return copy.deepcopy(matches[0])


def _external_control_interval(closure: dict[str, Any]) -> tuple[str, str]:
    try:
        delta = closure["receipt"]["delta"]["durableChanges"]
        uncovered = closure["receipt"]["aggregateReadback"]["uncoveredDurableChanges"]
    except (KeyError, TypeError) as exc:
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_ARTIFACT_INVALID"
        ) from exc
    for index, change in enumerate(delta):
        if not isinstance(change, dict):
            continue
        change_id = f"{change.get('kind')}:{change.get('name') or 'project-state'}:{index}"
        if (
            change_id in uncovered
            and change.get("kind") == "source-head"
            and change.get("name") == "control"
            and change.get("branch") == "main"
        ):
            before = change.get("before")
            after = change.get("after")
            if isinstance(before, str) and isinstance(after, str):
                return before, after
    raise HostedCycleFailureRecoveryError(
        "HOSTED_CYCLE_RECOVERY_EXTERNAL_DELTA_UNAVAILABLE"
    )


def _external_reconciliation(
    *,
    context: dict[str, Any],
    comments: list[dict[str, Any]],
    close_comment_id: int,
    failure: dict[str, Any],
    transport: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates = hosted_cycle_external_delta_provider.close_run_candidates(
        comments,
        close_comment_id=close_comment_id,
        transport=transport,
    )
    qualified: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for candidate in candidates:
        try:
            with tempfile.TemporaryDirectory(prefix="mobilipresenter-close-recovery-") as tmp:
                root = hosted_cycle_external_delta_provider.download_close_artifact(
                    candidate,
                    destination=tmp,
                )
                artifact_result = _load(root / "result.json")
                try:
                    artifact_failure = agent_failure.validate_hosted_cycle_failure(
                        artifact_result
                    )
                except RuntimeError:
                    continue
                if artifact_failure != failure:
                    continue
                closure = _load(root / "closure.json")
                work = _context_work(context)
                work_ref = context.get("workRef") or {}
                work_id = work_ref.get("workId")
                continuation_before = (
                    context.get("baseline", {})
                    .get("sourceHeads", {})
                    .get("continuation", {})
                    .get("sha")
                )
                if not isinstance(work_id, str) or not isinstance(continuation_before, str):
                    continue
                continuation_after, changed_paths = (
                    hosted_cycle_external_delta_provider.continuation_readback(
                        before_sha=continuation_before,
                        work_id=work_id,
                        transport=transport,
                    )
                )
                control_before, control_after = _external_control_interval(closure)
                pulls = hosted_cycle_external_delta_provider.merged_pull_request_chain(
                    before_sha=control_before,
                    after_sha=control_after,
                    work_branch=work.get("branch"),
                    work_pr_number=work.get("prNumber"),
                    transport=transport,
                )
                reconciled = (
                    hosted_cycle_external_delta_recovery.reconcile_failed_closure(
                        before_context=context,
                        failed_closure=closure,
                        comments=comments,
                        close_comment_id=close_comment_id,
                        continuation_after_sha=continuation_after,
                        continuation_changed_paths=changed_paths,
                        merged_pull_requests=pulls,
                    )
                )
                qualified.append((candidate, reconciled))
        except (
            HostedCycleFailureRecoveryError,
            hosted_cycle_external_delta_provider.HostedCycleExternalDeltaProviderError,
            hosted_cycle_external_delta_recovery.HostedCycleExternalDeltaRecoveryError,
        ):
            continue
    if len(qualified) != 1:
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_EXTERNAL_DELTA_AMBIGUOUS"
        )
    return qualified[0]


def recover(
    request: dict[str, Any],
    *,
    context: dict[str, Any],
    manifest: dict[str, Any],
    comments: list[dict[str, Any]],
    transport: Any | None = None,
) -> dict[str, Any]:
    request = validate_request(request)
    if transport is None:
        raise HostedCycleFailureRecoveryError("BLOCKED_EXECUTION_SURFACE")
    try:
        bound = hosted_cycle_handle.bind(
            request["handle"],
            context=context,
            manifest=manifest,
            repository=REPOSITORY,
        )
    except RuntimeError as exc:
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_BEGIN_BINDING_MISMATCH"
        ) from exc

    locator = bound["locator"]
    close_command, close_hash = _exact_close(
        comments,
        request,
        issue_number=locator["issueNumber"],
    )
    failure_comment_id, failure, causes = _exact_failed_close(
        comments,
        close_comment_id=request["closeRequestCommentId"],
        close_command=close_command,
        close_command_hash=close_hash,
    )
    report = agent_write_lifecycle_guard.inspect_cycle(
        comments,
        manifest,
        close_comment_id=request["closeRequestCommentId"],
        transport=transport,
    )
    agent_write_lifecycle_guard.validate_report(report)
    if report["state"] != "RELEASED" or report["blockers"]:
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_RESIDUAL_AUTHORITY_NOT_CLEAN"
        )

    common = {
        "requestId": request["requestId"],
        "cycleInstanceId": manifest["cycleInstanceId"],
        "handleHash": request["handle"]["handleHash"],
        "beginRequestCommentId": locator["beginCommentId"],
        "closeRequestCommentId": request["closeRequestCommentId"],
        "closeCommandHash": close_hash,
        "failedCloseResultCommentId": failure_comment_id,
        "failedCloseFailureHash": failure["failureHash"],
        "writeLifecycleReportHash": report["reportHash"],
        "authorityHead": report["authorityHead"],
        "state": "RECOVERED",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }

    if RECOVERABLE_CAUSES.issubset(causes):
        core = {
            "schemaVersion": RESULT_SCHEMA,
            **common,
            "reasonCodes": [RECOVERY_REASON],
        }
    else:
        candidate, reconciliation = _external_reconciliation(
            context=context,
            comments=comments,
            close_comment_id=request["closeRequestCommentId"],
            failure=failure,
            transport=transport,
        )
        proof = reconciliation["nonInterferenceEvidence"]
        reconciled = reconciliation["reconciledClosure"]
        failed_closure_hash = reconciled.get("closureHash")
        # The reconciled closure is a new read-only derivation; bind the original
        # historical closure separately from its receipt retained in the proof.
        with tempfile.TemporaryDirectory(prefix="mobilipresenter-close-bind-") as tmp:
            root = hosted_cycle_external_delta_provider.download_close_artifact(
                candidate,
                destination=tmp,
            )
            original_closure = _load(root / "closure.json")
        core = {
            "schemaVersion": RESULT_SCHEMA_V02,
            **common,
            "reasonCodes": [EXTERNAL_RECOVERY_REASON],
            "failedCloseRunId": candidate["runId"],
            "failedCloseClosureHash": original_closure["closureHash"],
            "failedCloseReceiptHash": original_closure["receipt"]["receiptHash"],
            "nonInterferenceEvidenceHash": proof["evidenceHash"],
            "reconciledClosureHash": failed_closure_hash,
            "reconciledReceiptHash": reconciled["receipt"]["receiptHash"],
        }
    return validate_certificate(
        {**core, "recoveryHash": stable_hash(core)}
    )


def parse_event(event: Any) -> tuple[dict[str, Any], dict[str, int]]:
    if not isinstance(event, dict):
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_EVENT_INVALID"
        )
    issue = event.get("issue")
    comment = event.get("comment")
    repository = event.get("repository")
    if (
        not isinstance(issue, dict)
        or not isinstance(comment, dict)
        or not isinstance(repository, dict)
        or issue.get("title") != BUS_TITLE
        or issue.get("pull_request") is not None
        or comment.get("author_association") != "OWNER"
        or repository.get("full_name") != REPOSITORY
    ):
        raise HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_EVENT_INVALID"
        )
    value = hosted_cycle_records.json_after_marker(
        comment.get("body"), REQUEST_MARKER
    )
    request = validate_request(value)
    _, locator = hosted_cycle_handle.decode_handle(
        request["handle"], repository=REPOSITORY
    )
    return request, {
        "issueNumber": _positive(
            issue.get("number"), "HOSTED_CYCLE_RECOVERY_EVENT_INVALID"
        ),
        "commentId": _positive(
            comment.get("id"), "HOSTED_CYCLE_RECOVERY_EVENT_INVALID"
        ),
        "beginRunId": locator["runId"],
    }


def publish(
    value: dict[str, Any],
    *,
    issue_number: int,
    transport: Any | None = None,
) -> int:
    if transport is None:
        raise HostedCycleFailureRecoveryError("BLOCKED_EXECUTION_SURFACE")
    cert = validate_certificate(value)
    body = (
        RESULT_MARKER
        + "\n" + "```json\n"
        + json.dumps(cert, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n" + "```"
    )
    return hosted_issue_bus.post_comment(
        transport,
        repository=REPOSITORY,
        issue_number=issue_number,
        body=body,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command_name", required=True)
    event = sub.add_parser("parse-event")
    event.add_argument("--event", required=True)
    event.add_argument("--request", required=True)
    event.add_argument("--meta", required=True)
    event.add_argument("--github-output")
    run = sub.add_parser("recover")
    run.add_argument("--request", required=True)
    run.add_argument("--begin-dir", required=True)
    run.add_argument("--result", required=True)
    publish_cmd = sub.add_parser("publish")
    publish_cmd.add_argument("--meta", required=True)
    publish_cmd.add_argument("--result", required=True)
    return parser


def _emit(path: str | None, key: str, value: str) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(f"{key}={value}\n")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    transport = GhApiTransport()
    if args.command_name == "parse-event":
        request, meta = parse_event(_load(args.event))
        _write(args.request, request)
        _write(args.meta, meta)
        _, locator = hosted_cycle_handle.decode_handle(
            request["handle"], repository=REPOSITORY
        )
        _emit(args.github_output, "begin_run_id", str(locator["runId"]))
        _emit(args.github_output, "begin_artifact_name", locator["artifactName"])
        return 0
    if args.command_name == "recover":
        request = _load(args.request)
        root = Path(args.begin_dir)
        context = _load(root / "context.json")
        manifest = _load(root / "manifest.json")
        _, locator = hosted_cycle_handle.decode_handle(
            request["handle"], repository=REPOSITORY
        )
        comments = hosted_issue_bus.list_comments(
            transport,
            repository=REPOSITORY,
            issue_number=locator["issueNumber"],
        )
        value = recover(
            request,
            context=context,
            manifest=manifest,
            comments=comments,
            transport=transport,
        )
        _write(args.result, value)
        return 0
    if args.command_name == "publish":
        meta = _load(args.meta)
        publish(
            _load(args.result),
            issue_number=_positive(
                meta.get("issueNumber"),
                "HOSTED_CYCLE_RECOVERY_EVENT_INVALID",
            ),
            transport=transport,
        )
        return 0
    raise HostedCycleFailureRecoveryError(
        "HOSTED_CYCLE_RECOVERY_COMMAND_UNSUPPORTED"
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HostedCycleFailureRecoveryError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
