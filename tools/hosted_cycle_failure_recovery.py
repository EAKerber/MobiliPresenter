#!/usr/bin/env python3
"""Public recovery carrier composing the stable core with own-Work recovery v0.3.

The 0.1/0.2 implementation lives byte-for-byte in
``hosted_cycle_failure_recovery_core``.  This public module preserves that
surface and adds only the narrow 0.3 certificate for a failed close whose sole
uncovered control delta is the exact Work's own PR chain merged while the exact
cycle held continuous write authority.
"""
from __future__ import annotations

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
    hosted_cycle_external_delta_provider,
    hosted_cycle_handle,
    hosted_cycle_own_work_delta_recovery,
    hosted_issue_bus,
)
from tools import hosted_cycle_failure_recovery_core as _core
from tools.canonical import stable_hash
from tools.coordination_remote import GhApiTransport

HostedCycleFailureRecoveryError = _core.HostedCycleFailureRecoveryError
REPOSITORY = _core.REPOSITORY
BUS_TITLE = _core.BUS_TITLE
REQUEST_MARKER = _core.REQUEST_MARKER
RESULT_MARKER = _core.RESULT_MARKER
REQUEST_SCHEMA = _core.REQUEST_SCHEMA
RESULT_SCHEMA = _core.RESULT_SCHEMA
RESULT_SCHEMA_V02 = _core.RESULT_SCHEMA_V02
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
RESULT_V03_FIELDS = _core.RESULT_FIELDS | RESULT_V03_EXTRA_FIELDS


def __getattr__(name: str) -> Any:
    """Preserve the existing public/private module surface for current callers."""
    return getattr(_core, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_core)))


def validate_certificate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schemaVersion") != RESULT_SCHEMA_V03:
        return _core.validate_certificate(value)
    if (
        set(value) != RESULT_V03_FIELDS
        or value.get("reasonCodes") != [OWN_WORK_RECOVERY_REASON]
    ):
        raise HostedCycleFailureRecoveryError("HOSTED_CYCLE_RECOVERY_RESULT_INVALID")
    _core._validate_certificate_common(value)
    _core._positive(value.get("failedCloseRunId"), "HOSTED_CYCLE_RECOVERY_RESULT_INVALID")
    for field in (
        "failedCloseClosureHash",
        "failedCloseReceiptHash",
        "ownWorkIntegrationProofHash",
        "reconciledClosureHash",
        "reconciledReceiptHash",
    ):
        _core._hash(value.get(field), "HOSTED_CYCLE_RECOVERY_RESULT_INVALID")
    hashes = value.get("mergeEvidenceHashes")
    if (
        not isinstance(hashes, list)
        or not hashes
        or hashes != sorted(set(hashes))
    ):
        raise HostedCycleFailureRecoveryError("HOSTED_CYCLE_RECOVERY_RESULT_INVALID")
    for digest in hashes:
        _core._hash(digest, "HOSTED_CYCLE_RECOVERY_RESULT_INVALID")
    body = {key: copy.deepcopy(item) for key, item in value.items() if key != "recoveryHash"}
    if value.get("recoveryHash") != stable_hash(body):
        raise HostedCycleFailureRecoveryError("HOSTED_CYCLE_RECOVERY_HASH_MISMATCH")
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
    qualified: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for candidate in candidates:
        try:
            with tempfile.TemporaryDirectory(prefix="mobilipresenter-own-work-recovery-") as tmp:
                root = hosted_cycle_external_delta_provider.download_close_artifact(
                    candidate,
                    destination=tmp,
                )
                artifact_result = _core._load(root / "result.json")
                try:
                    artifact_failure = agent_failure.validate_hosted_cycle_failure(artifact_result)
                except RuntimeError:
                    continue
                if artifact_failure != failure:
                    continue
                closure = _core._load(root / "closure.json")
                reconciliation = hosted_cycle_own_work_delta_recovery.reconcile_failed_closure(
                    before_context=context,
                    cycle_instance_id=manifest["cycleInstanceId"],
                    failed_closure=closure,
                    comments=comments,
                    close_comment_id=close_comment_id,
                    transport=transport,
                )
                qualified.append((candidate, reconciliation, copy.deepcopy(closure)))
        except (
            hosted_cycle_external_delta_provider.HostedCycleExternalDeltaProviderError,
            hosted_cycle_own_work_delta_recovery.HostedCycleOwnWorkDeltaRecoveryError,
        ):
            continue
    if len(qualified) != 1:
        raise HostedCycleFailureRecoveryError(
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
        return _core.recover(
            request,
            context=context,
            manifest=manifest,
            comments=comments,
            transport=transport,
        )
    except HostedCycleFailureRecoveryError as exc:
        if exc.code != "HOSTED_CYCLE_RECOVERY_EXTERNAL_DELTA_AMBIGUOUS":
            raise

    request = _core.validate_request(request)
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
    close_command, close_hash = _core._exact_close(
        comments,
        request,
        issue_number=locator["issueNumber"],
    )
    failure_comment_id, failure, causes = _core._exact_failed_close(
        comments,
        close_comment_id=request["closeRequestCommentId"],
        close_command=close_command,
        close_command_hash=close_hash,
    )
    if not _core.EXTERNAL_RECOVERABLE_CAUSES.issubset(causes):
        raise HostedCycleFailureRecoveryError("HOSTED_CYCLE_RECOVERY_FAILURE_NOT_SUPPORTED")

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
    body = {
        "schemaVersion": RESULT_SCHEMA_V03,
        **common,
        "reasonCodes": [OWN_WORK_RECOVERY_REASON],
        "failedCloseRunId": candidate["runId"],
        "failedCloseClosureHash": original_closure["closureHash"],
        "failedCloseReceiptHash": original_closure["receipt"]["receiptHash"],
        "ownWorkIntegrationProofHash": proof["proofHash"],
        "mergeEvidenceHashes": sorted(item["evidenceHash"] for item in merge_evidence),
        "reconciledClosureHash": reconciled["closureHash"],
        "reconciledReceiptHash": reconciled["receipt"]["receiptHash"],
    }
    return validate_certificate({**body, "recoveryHash": stable_hash(body)})


def publish(
    value: dict[str, Any],
    *,
    issue_number: int,
    transport: Any | None = None,
) -> int:
    if transport is None:
        raise HostedCycleFailureRecoveryError("BLOCKED_EXECUTION_SURFACE")
    certificate = validate_certificate(value)
    body = (
        RESULT_MARKER
        + "\n```json\n"
        + json.dumps(certificate, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n```"
    )
    return hosted_issue_bus.post_comment(
        transport,
        repository=REPOSITORY,
        issue_number=issue_number,
        body=body,
    )


def main(argv: list[str] | None = None) -> int:
    args = _core._parser().parse_args(argv)
    transport = GhApiTransport()
    if args.command_name == "parse-event":
        request, meta = _core.parse_event(_core._load(args.event))
        _core._write(args.request, request)
        _core._write(args.meta, meta)
        _, locator = hosted_cycle_handle.decode_handle(request["handle"], repository=REPOSITORY)
        _core._emit(args.github_output, "begin_run_id", str(locator["runId"]))
        _core._emit(args.github_output, "begin_artifact_name", locator["artifactName"])
        return 0
    if args.command_name == "recover":
        request = _core._load(args.request)
        root = Path(args.begin_dir)
        context = _core._load(root / "context.json")
        manifest = _core._load(root / "manifest.json")
        _, locator = hosted_cycle_handle.decode_handle(request["handle"], repository=REPOSITORY)
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
        _core._write(args.result, value)
        return 0
    if args.command_name == "publish":
        meta = _core._load(args.meta)
        publish(
            _core._load(args.result),
            issue_number=_core._positive(
                meta.get("issueNumber"),
                "HOSTED_CYCLE_RECOVERY_EVENT_INVALID",
            ),
            transport=transport,
        )
        return 0
    raise HostedCycleFailureRecoveryError("HOSTED_CYCLE_RECOVERY_COMMAND_UNSUPPORTED")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        HostedCycleFailureRecoveryError,
        hosted_cycle_own_work_delta_recovery.HostedCycleOwnWorkDeltaRecoveryError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
