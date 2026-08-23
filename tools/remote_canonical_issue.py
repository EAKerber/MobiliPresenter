#!/usr/bin/env python3
"""GitHub issue-comment transport adapter for Remote Canonical Execution 0.1."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.canonical import stable_hash
from tools.remote_canonical_execution import (
    RemoteCanonicalExecutionError,
    execute_command,
    validate_command,
)

REQUEST_MARKER = "MOBILIPRESENTER_REMOTE_CANONICAL_REQUEST_V0_1"
RESULT_MARKER = "MOBILIPRESENTER_REMOTE_CANONICAL_RESULT_V0_1"
BUS_TITLE = "MobiliPresenter Remote Canonical Execution Bus"
FAILURE_SCHEMA = "RemoteCanonicalExecutionFailure 0.1"


def parse_event(value: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict):
        raise RemoteCanonicalExecutionError("REMOTE_TRANSPORT_EVENT_INVALID")
    issue = value.get("issue")
    comment = value.get("comment")
    repository = value.get("repository")
    if not isinstance(issue, dict) or not isinstance(comment, dict) or not isinstance(repository, dict):
        raise RemoteCanonicalExecutionError("REMOTE_TRANSPORT_EVENT_INVALID")
    if issue.get("pull_request") is not None:
        raise RemoteCanonicalExecutionError("REMOTE_TRANSPORT_PR_COMMENT_FORBIDDEN")
    if issue.get("title") != BUS_TITLE:
        raise RemoteCanonicalExecutionError("REMOTE_TRANSPORT_BUS_MISMATCH")
    if comment.get("author_association") != "OWNER":
        raise RemoteCanonicalExecutionError("REMOTE_TRANSPORT_ACTOR_FORBIDDEN")
    if repository.get("full_name") != "EAKerber/MobiliPresenter":
        raise RemoteCanonicalExecutionError("REMOTE_TRANSPORT_REPOSITORY_MISMATCH")
    body = comment.get("body")
    if not isinstance(body, str):
        raise RemoteCanonicalExecutionError("REMOTE_TRANSPORT_BODY_INVALID")
    prefix = REQUEST_MARKER + "\n"
    if not body.startswith(prefix):
        raise RemoteCanonicalExecutionError("REMOTE_TRANSPORT_MARKER_INVALID")
    raw = body[len(prefix):].strip()
    try:
        command = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RemoteCanonicalExecutionError("REMOTE_TRANSPORT_JSON_INVALID") from exc
    command = validate_command(command)
    issue_number = issue.get("number")
    comment_id = comment.get("id")
    if (
        not isinstance(issue_number, int)
        or isinstance(issue_number, bool)
        or issue_number <= 0
        or not isinstance(comment_id, int)
        or isinstance(comment_id, bool)
        or comment_id <= 0
    ):
        raise RemoteCanonicalExecutionError("REMOTE_TRANSPORT_IDENTITY_INVALID")
    event_meta = {
        "issueNumber": issue_number,
        "commentId": comment_id,
    }
    return command, event_meta


def build_source(event_meta: dict[str, Any]) -> dict[str, Any]:
    source_sha = os.environ.get("GITHUB_SHA", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    return {
        "workflow": "remote-canonical-execution",
        "sourceSha": source_sha,
        "runId": run_id,
        "issueNumber": event_meta["issueNumber"],
        "commentId": event_meta["commentId"],
    }


def failure_payload(exc: BaseException, command: dict[str, Any] | None = None) -> dict[str, Any]:
    code = getattr(exc, "code", None)
    if not isinstance(code, str) or not code:
        text = str(exc)
        code = text.split(":", 1)[0] if text else exc.__class__.__name__
    core = {
        "schemaVersion": FAILURE_SCHEMA,
        "executionId": command.get("executionId") if isinstance(command, dict) else None,
        "commandHash": stable_hash(command) if isinstance(command, dict) else None,
        "status": "BLOCKED",
        "blockers": [code],
        "detail": str(exc),
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "failureHash": stable_hash(core)}


def _write(path: str, payload: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="remote-canonical-issue")
    parser.add_argument("--event", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    command: dict[str, Any] | None = None
    try:
        event = json.loads(Path(args.event).read_text(encoding="utf-8"))
        command, event_meta = parse_event(event)
        receipt = execute_command(command, source=build_source(event_meta))
        _write(args.output, receipt)
        print(json.dumps(receipt, ensure_ascii=False))
        return 0
    except (RemoteCanonicalExecutionError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        payload = failure_payload(exc, command)
        _write(args.output, payload)
        print(json.dumps(payload, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
