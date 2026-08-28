#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import agent_write_lifecycle as lifecycle
from tools import hosted_agent_cycle, hosted_cycle_handle

REPOSITORY = "EAKerber/MobiliPresenter"
BUS_TITLE = hosted_agent_cycle.BUS_TITLE
REQUEST_MARKER = lifecycle.REQUEST_MARKER
REQUEST_MARKER_V02 = "MOBILIPRESENTER_AGENT_WRITE_LEASE_REQUEST_V0_2"
HANDLE_REQUEST_SCHEMA = "HostedAgentWriteLeaseRequest 0.2"
HANDLE_REQUEST_FIELDS = {
    "schemaVersion", "requestId", "handle", "action", "branch",
    "expectedAuthorityHead", "expectedBranchHead", "expectedBindingHash",
    "ttlSeconds", "semanticAuthority", "authorizesMutation",
}


class HostedAgentWriteLeaseError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def validate_handle_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != HANDLE_REQUEST_FIELDS:
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_HANDLE_REQUEST_FIELDS_INVALID")
    if value.get("schemaVersion") != HANDLE_REQUEST_SCHEMA:
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_HANDLE_REQUEST_SCHEMA_UNSUPPORTED")
    request_id = value.get("requestId")
    if not isinstance(request_id, str) or not request_id.strip():
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_REQUEST_ID_INVALID")
    if value.get("action") not in lifecycle.ACTIONS:
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_ACTION_INVALID")
    if not isinstance(value.get("branch"), str) or not value["branch"].strip():
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_BRANCH_INVALID")
    try:
        hosted_cycle_handle.decode_handle(value.get("handle"), repository=REPOSITORY)
    except RuntimeError as exc:
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_HANDLE_INVALID") from exc
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_REQUEST_MUST_NOT_AUTHORIZE")
    return value


def derive_handle_request(
    outer: dict[str, Any], manifest: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    outer = validate_handle_request(outer)
    hosted_agent_cycle.validate_begin_manifest(manifest, context)
    try:
        binding = hosted_cycle_handle.bind(
            outer["handle"], context=context, manifest=manifest, repository=REPOSITORY
        )
    except RuntimeError as exc:
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_HANDLE_BINDING_MISMATCH") from exc
    request = {
        "schemaVersion": lifecycle.REQUEST_SCHEMA,
        "requestId": outer["requestId"],
        "action": outer["action"],
        "begin": copy.deepcopy(binding["begin"]),
        "actor": copy.deepcopy(binding["actor"]),
        "branch": outer["branch"],
        "expectedAuthorityHead": outer["expectedAuthorityHead"],
        "expectedBranchHead": outer["expectedBranchHead"],
        "expectedBindingHash": outer["expectedBindingHash"],
        "ttlSeconds": outer["ttlSeconds"],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return lifecycle.validate_request(request)


def parse_event(value: Any) -> tuple[dict[str, Any], dict[str, int]]:
    if not isinstance(value, dict):
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_EVENT_INVALID")
    issue = value.get("issue")
    comment = value.get("comment")
    repository = value.get("repository")
    if not isinstance(issue, dict) or not isinstance(comment, dict) or not isinstance(repository, dict):
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_EVENT_INVALID")
    if issue.get("pull_request") is not None or issue.get("title") != BUS_TITLE:
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_BUS_MISMATCH")
    if comment.get("author_association") != "OWNER":
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_ACTOR_FORBIDDEN")
    if repository.get("full_name") != REPOSITORY:
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_REPOSITORY_MISMATCH")
    body = comment.get("body")
    if not isinstance(body, str):
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_MARKER_INVALID")
    marker = next(
        (item for item in (REQUEST_MARKER, REQUEST_MARKER_V02) if body.startswith(item + "\n")),
        None,
    )
    if marker is None:
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_MARKER_INVALID")
    try:
        request = json.loads(body[len(marker) + 1:].strip())
    except json.JSONDecodeError as exc:
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_JSON_INVALID") from exc
    if marker == REQUEST_MARKER_V02:
        validate_handle_request(request)
    else:
        lifecycle.validate_request(request)
    if (marker == REQUEST_MARKER_V02) != (request.get("schemaVersion") == HANDLE_REQUEST_SCHEMA):
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_MARKER_SCHEMA_MISMATCH")
    issue_number = issue.get("number")
    comment_id = comment.get("id")
    if not isinstance(issue_number, int) or isinstance(issue_number, bool) or issue_number <= 0:
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_EVENT_IDENTITY_INVALID")
    if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id <= 0:
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_EVENT_IDENTITY_INVALID")
    return request, {"issueNumber": issue_number, "commentId": comment_id}


def prepare(
    request: dict[str, Any],
    manifest: dict[str, Any],
    context: dict[str, Any],
    *,
    meta: dict[str, int],
    hosted_run_id: int | str | None = None,
    transport: Any | None = None,
) -> dict[str, Any]:
    run_id = hosted_run_id if hosted_run_id is not None else os.environ.get("GITHUB_RUN_ID")
    if isinstance(run_id, str) and run_id.isdigit():
        run_id = int(run_id)
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_RUN_ID_INVALID")
    return lifecycle.prepare_dispatch(
        request,
        manifest,
        context,
        issue_number=meta["issueNumber"],
        request_comment_id=meta["commentId"],
        hosted_run_id=run_id,
        transport=transport,
    )


def _load(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_ARTIFACT_INVALID") from exc
    if not isinstance(value, dict):
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_ARTIFACT_INVALID")
    return value


def _write(path: str | Path, value: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _emit(path: str, key: str, value: str) -> None:
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(f"{key}={value}\n")


def _failure(exc: BaseException, request: dict[str, Any] | None) -> dict[str, Any]:
    code = getattr(exc, "code", None)
    if not isinstance(code, str) or not code:
        text = str(exc)
        code = text.split(":", 1)[0] if text else exc.__class__.__name__
    try:
        return lifecycle.build_failure(request, status="BLOCKED", blockers=[code])
    except Exception:
        return {
            "schemaVersion": lifecycle.FAILURE_SCHEMA,
            "requestId": request.get("requestId") if isinstance(request, dict) else None,
            "requestHash": None,
            "action": request.get("action") if isinstance(request, dict) else None,
            "begin": request.get("begin") if isinstance(request, dict) else None,
            "actor": request.get("actor") if isinstance(request, dict) else None,
            "branch": request.get("branch") if isinstance(request, dict) else None,
            "authorityHead": None,
            "status": "BLOCKED",
            "blockers": [code],
            "semanticAuthority": False,
            "authorizesMutation": False,
            "failureHash": "",
        }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="hosted-agent-write-lease")
    sub = parser.add_subparsers(dest="action", required=True)

    parse = sub.add_parser("parse-event")
    parse.add_argument("--event", required=True)
    parse.add_argument("--request-out", required=True)
    parse.add_argument("--meta-out", required=True)
    parse.add_argument("--github-output", required=True)

    prepare_cmd = sub.add_parser("prepare")
    prepare_cmd.add_argument("--request", required=True)
    prepare_cmd.add_argument("--meta", required=True)
    prepare_cmd.add_argument("--begin-dir", required=True)
    prepare_cmd.add_argument("--dispatch", required=True)

    failure = sub.add_parser("failure")
    failure.add_argument("--error", required=True)
    failure.add_argument("--request")
    failure.add_argument("--result", required=True)

    args = parser.parse_args(argv)
    request: dict[str, Any] | None = None
    try:
        if args.action == "parse-event":
            event = _load(args.event)
            request, meta = parse_event(event)
            _write(args.request_out, request)
            _write(args.meta_out, meta)
            if request.get("schemaVersion") == HANDLE_REQUEST_SCHEMA:
                _, locator = hosted_cycle_handle.decode_handle(request["handle"], repository=REPOSITORY)
                _emit(args.github_output, "begin_run_id", str(locator["runId"]))
                _emit(args.github_output, "begin_source_sha", locator["sourceSha"])
            else:
                _emit(args.github_output, "begin_run_id", str(request["begin"]["runId"]))
                _emit(args.github_output, "begin_source_sha", request["begin"]["sourceSha"])
            return 0
        if args.action == "failure":
            request = _load(args.request) if args.request else None
            if isinstance(request, dict) and request.get("schemaVersion") == HANDLE_REQUEST_SCHEMA:
                payload = _failure(HostedAgentWriteLeaseError(args.error), request)
            else:
                payload = lifecycle.build_failure(request, status="BLOCKED", blockers=[args.error])
            _write(args.result, payload)
            print(json.dumps(payload, ensure_ascii=False))
            return 2

        request = _load(args.request)
        meta = _load(args.meta)
        root = Path(args.begin_dir)
        manifest = _load(root / "manifest.json")
        context = _load(root / "context.json")
        if request.get("schemaVersion") == HANDLE_REQUEST_SCHEMA:
            outer = copy.deepcopy(request)
            _write(Path(args.request).with_name("agent-write-lease-outer-request.json"), outer)
            request = derive_handle_request(outer, manifest, context)
            _write(args.request, request)
        dispatch = prepare(request, manifest, context, meta=meta)
        _write(args.dispatch, dispatch)
        print(json.dumps(dispatch, ensure_ascii=False))
        return 0
    except Exception as exc:
        if getattr(args, "result", None):
            payload = _failure(exc, request)
            _write(args.result, payload)
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
