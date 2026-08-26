#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import agent_write_lifecycle as lifecycle
from tools import hosted_agent_cycle

REPOSITORY = "EAKerber/MobiliPresenter"
BUS_TITLE = hosted_agent_cycle.BUS_TITLE


class HostedAgentWriteLeaseError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


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
    prefix = lifecycle.REQUEST_MARKER + "\n"
    if not isinstance(body, str) or not body.startswith(prefix):
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_MARKER_INVALID")
    try:
        request = json.loads(body[len(prefix):].strip())
    except json.JSONDecodeError as exc:
        raise HostedAgentWriteLeaseError("HOSTED_AGENT_WRITE_LEASE_JSON_INVALID") from exc
    lifecycle.validate_request(request)
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
            _emit(args.github_output, "begin_run_id", str(request["begin"]["runId"]))
            _emit(args.github_output, "begin_source_sha", request["begin"]["sourceSha"])
            return 0
        if args.action == "failure":
            request = _load(args.request) if args.request else None
            payload = lifecycle.build_failure(request, status="BLOCKED", blockers=[args.error])
            _write(args.result, payload)
            print(json.dumps(payload, ensure_ascii=False))
            return 2

        request = _load(args.request)
        meta = _load(args.meta)
        root = Path(args.begin_dir)
        manifest = _load(root / "manifest.json")
        context = _load(root / "context.json")
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
