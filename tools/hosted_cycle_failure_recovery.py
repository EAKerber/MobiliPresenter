#!/usr/bin/env python3
"""Recovery facade extending the legacy carrier with own-Work integration proof.

The legacy implementation is preserved byte-for-byte in
`hosted_cycle_failure_recovery_legacy.py`. This facade delegates every existing
0.1/0.2 path to it and adds only the narrow 0.3 certificate used when the sole
uncovered durable delta is a chain of the Work's own PRs merged while the exact
cycle held valid write authority.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from tools.hosted_cycle_failure_recovery_legacy import *  # noqa: F401,F403
from tools import (
    agent_failure,
    agent_write_lifecycle_guard,
    hosted_cycle_external_delta_provider,
    hosted_cycle_handle,
    hosted_cycle_own_work_delta_recovery,
    hosted_issue_bus,
)
from tools import hosted_cycle_failure_recovery_legacy as _legacy
from tools.canonical import stable_hash
from tools.coordination_remote import GhApiTransport

RESULT_SCHEMA_V03 = "HostedAgentCycleRecovery 0.3"
OWN_WORK_RECOVERY_REASON = "OWN_WORK_DURABLE_DELTA_RECONCILED"
RESULT_V03_EXTRA_FIELDS = {
    "failedCloseRunId",
    "failedCloseClosureHash",
    "failedCloseReceiptHash",
    "ownWorkIntegrationProofHash",
    "mergeEvidenceHashes",
    "reconciledClosureHash",
    "reconciledReceiptHash",
}
RESULT_V03_FIELDS = _legacy.RESULT_FIELDS | RESULT_V03_EXTRA_FIELDS


def validate_certificate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schemaVersion") != RESULT_SCHEMA_V03:
        return _legacy.validate_certificate(value)
    if (
        set(value) != RESULT_V03_FIELDS
        or value.get("reasonCodes") != [OWN_WORK_RECOVERY_REASON]
    ):
        raise _legacy.HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_RESULT_INVALID"
        )
    _legacy._validate_certificate_common(value)
    _legacy._positive(
        value.get("failedCloseRunId"),
        "HOSTED_CYCLE_RECOVERY_RESULT_INVALID",
    )
    for field in (
        "failedCloseClosureHash",
        "failedCloseReceiptHash",
        "ownWorkIntegrationProofHash",
        "reconciledClosureHash",
        "reconciledReceiptHash",
    ):
        _legacy._hash(value.get(field), "HOSTED_CYCLE_RECOVERY_RESULT_INVALID")
    hashes = value.get("mergeEvidenceHashes")
    if (
        not isinstance(hashes, list)
        or not hashes
        or hashes != sorted(set(hashes))
    ):
        raise _legacy.HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_RESULT_INVALID"
        )
    for digest in hashes:
        _legacy._hash(digest, "HOSTED_CYCLE_RECOVERY_RESULT_INVALID")
    core = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "recoveryHash"
    }
    if value.get("recoveryHash") != stable_hash(core):
        raise _legacy.HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_HASH_MISMATCH"
        )
    return value


def _own_work_reconciliation(
    *,
    context: dict[str, Any],
    manifest: dict[str, Any],
    comments: list[dict[str, Any]],
    close_comment_id: int,
    failure: dict[str, Any],
    transport: Any,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    candidates = hosted_cycle_external_delta_provider.close_run_candidates(
        comments,
        close_comment_id=close_comment_id,
        transport=transport,
    )
    qualified: list[
        tuple[dict[str, Any], dict[str, Any], dict[str, Any]]
    ] = []
    for candidate in candidates:
        try:
            with tempfile.TemporaryDirectory(
                prefix="mobilipresenter-own-work-recovery-"
            ) as tmp:
                root = hosted_cycle_external_delta_provider.download_close_artifact(
                    candidate,
                    destination=tmp,
                )
                artifact_result = _legacy._load(root / "result.json")
                try:
                    artifact_failure = agent_failure.validate_hosted_cycle_failure(
                        artifact_result
                    )
                except RuntimeError:
                    continue
                if artifact_failure != failure:
                    continue
                closure = _legacy._load(root / "closure.json")
                reconciled = (
                    hosted_cycle_own_work_delta_recovery.reconcile_failed_closure(
                        before_context=context,
                        cycle_instance_id=manifest["cycleInstanceId"],
                        failed_closure=closure,
                        comments=comments,
                        close_comment_id=close_comment_id,
                        transport=transport,
                    )
                )
                qualified.append(
                    (candidate, reconciled, copy.deepcopy(closure))
                )
        except (
            hosted_cycle_external_delta_provider.HostedCycleExternalDeltaProviderError,
            hosted_cycle_own_work_delta_recovery.HostedCycleOwnWorkDeltaRecoveryError,
        ):
            continue
    if len(qualified) != 1:
        raise _legacy.HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_OWN_WORK_DELTA_AMBIGUOUS"
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
    try:
        return _legacy.recover(
            request,
            context=context,
            manifest=manifest,
            comments=comments,
            transport=transport,
        )
    except _legacy.HostedCycleFailureRecoveryError as exc:
        if exc.code != "HOSTED_CYCLE_RECOVERY_EXTERNAL_DELTA_AMBIGUOUS":
            raise

    request = _legacy.validate_request(request)
    if transport is None:
        raise _legacy.HostedCycleFailureRecoveryError(
            "BLOCKED_EXECUTION_SURFACE"
        )
    try:
        bound = hosted_cycle_handle.bind(
            request["handle"],
            context=context,
            manifest=manifest,
            repository=_legacy.REPOSITORY,
        )
    except RuntimeError as exc:
        raise _legacy.HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_BEGIN_BINDING_MISMATCH"
        ) from exc
    locator = bound["locator"]
    close_command, close_hash = _legacy._exact_close(
        comments,
        request,
        issue_number=locator["issueNumber"],
    )
    failure_comment_id, failure, causes = _legacy._exact_failed_close(
        comments,
        close_comment_id=request["closeRequestCommentId"],
        close_command=close_command,
        close_command_hash=close_hash,
    )
    if not _legacy.EXTERNAL_RECOVERABLE_CAUSES.issubset(causes):
        raise _legacy.HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_FAILURE_NOT_SUPPORTED"
        )
    report = agent_write_lifecycle_guard.inspect_cycle(
        comments,
        manifest,
        close_comment_id=request["closeRequestCommentId"],
        transport=transport,
    )
    agent_write_lifecycle_guard.validate_report(report)
    if report["state"] != "RELEASED" or report["blockers"]:
        raise _legacy.HostedCycleFailureRecoveryError(
            "HOSTED_CYCLE_RECOVERY_RESIDUAL_AUTHORITY_NOT_CLEAN"
        )

    candidate, reconciliation, original_closure = _own_work_reconciliation(
        context=context,
        manifest=manifest,
        comments=comments,
        close_comment_id=request["closeRequestCommentId"],
        failure=failure,
        transport=transport,
    )
    proof = reconciliation["ownWorkIntegrationProof"]
    merge_evidence = reconciliation["mergeEvidence"]
    reconciled = reconciliation["reconciledClosure"]
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
    core = {
        "schemaVersion": RESULT_SCHEMA_V03,
        **common,
        "reasonCodes": [OWN_WORK_RECOVERY_REASON],
        "failedCloseRunId": candidate["runId"],
        "failedCloseClosureHash": original_closure["closureHash"],
        "failedCloseReceiptHash": original_closure["receipt"]["receiptHash"],
        "ownWorkIntegrationProofHash": proof["proofHash"],
        "mergeEvidenceHashes": sorted(
            item["evidenceHash"] for item in merge_evidence
        ),
        "reconciledClosureHash": reconciled["closureHash"],
        "reconciledReceiptHash": reconciled["receipt"]["receiptHash"],
    }
    return validate_certificate(
        {**core, "recoveryHash": stable_hash(core)}
    )


def publish(
    value: dict[str, Any],
    *,
    issue_number: int,
    transport: Any | None = None,
) -> int:
    if transport is None:
        raise _legacy.HostedCycleFailureRecoveryError(
            "BLOCKED_EXECUTION_SURFACE"
        )
    certificate = validate_certificate(value)
    body = (
        _legacy.RESULT_MARKER
        + "\n```json\n"
        + json.dumps(certificate, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n```"
    )
    return hosted_issue_bus.post_comment(
        transport,
        repository=_legacy.REPOSITORY,
        issue_number=issue_number,
        body=body,
    )


def main(argv: list[str] | None = None) -> int:
    args = _legacy._parser().parse_args(argv)
    transport = GhApiTransport()
    if args.command_name == "parse-event":
        request, meta = _legacy.parse_event(_legacy._load(args.event))
        _legacy._write(args.request, request)
        _legacy._write(args.meta, meta)
        _, locator = hosted_cycle_handle.decode_handle(
            request["handle"], repository=_legacy.REPOSITORY
        )
        _legacy._emit(
            args.github_output, "begin_run_id", str(locator["runId"])
        )
        _legacy._emit(
            args.github_output,
            "begin_artifact_name",
            locator["artifactName"],
        )
        return 0
    if args.command_name == "recover":
        request = _legacy._load(args.request)
        root = Path(args.begin_dir)
        context = _legacy._load(root / "context.json")
        manifest = _legacy._load(root / "manifest.json")
        _, locator = hosted_cycle_handle.decode_handle(
            request["handle"], repository=_legacy.REPOSITORY
        )
        comments = hosted_issue_bus.list_comments(
            transport,
            repository=_legacy.REPOSITORY,
            issue_number=locator["issueNumber"],
        )
        value = recover(
            request,
            context=context,
            manifest=manifest,
            comments=comments,
            transport=transport,
        )
        _legacy._write(args.result, value)
        return 0
    if args.command_name == "publish":
        meta = _legacy._load(args.meta)
        publish(
            _legacy._load(args.result),
            issue_number=_legacy._positive(
                meta.get("issueNumber"),
                "HOSTED_CYCLE_RECOVERY_EVENT_INVALID",
            ),
            transport=transport,
        )
        return 0
    raise _legacy.HostedCycleFailureRecoveryError(
        "HOSTED_CYCLE_RECOVERY_COMMAND_UNSUPPORTED"
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        _legacy.HostedCycleFailureRecoveryError,
        hosted_cycle_own_work_delta_recovery.HostedCycleOwnWorkDeltaRecoveryError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
