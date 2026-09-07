#!/usr/bin/env python3
"""Pure preflight for manual RemoteCanonical issue-comment requests.

This module deliberately stops before transport. It validates the exact
RemoteCanonicalCommand and hosted role boundary consumed by the issue adapter,
then renders the comment body an operator may publish. It never repairs,
defaults, publishes, or authorizes a command.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.remote_canonical_execution import (
    RemoteCanonicalExecutionError,
    command_hash,
)
from tools.remote_canonical_issue import REQUEST_MARKER, authorize_role_route

PREFLIGHT_SCHEMA = "RemoteCanonicalRequestPreflight 0.1"


def preflight(command: Any) -> dict[str, Any]:
    """Validate one manual command and render its existing bus envelope."""
    canonical = authorize_role_route(command)
    comment_body = REQUEST_MARKER + "\n" + json.dumps(
        canonical, ensure_ascii=False, indent=2, sort_keys=True
    )
    return {
        "schemaVersion": PREFLIGHT_SCHEMA,
        "command": canonical,
        "commandHash": command_hash(canonical),
        "commentBody": comment_body,
        "transportReady": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def _error_payload(exc: BaseException) -> dict[str, Any]:
    code = getattr(exc, "code", None)
    if not isinstance(code, str) or not code:
        text = str(exc)
        code = text.split(":", 1)[0] if text else exc.__class__.__name__
    return {
        "schemaVersion": PREFLIGHT_SCHEMA,
        "status": "BLOCKED",
        "blockers": [code],
        "detail": str(exc),
        "transportReady": False,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="remote-canonical-preflight")
    parser.add_argument("--command", required=True, help="Path to a RemoteCanonicalCommand JSON file.")
    parser.add_argument(
        "--comment-output",
        help="Optional path for the validated issue-comment body. No network call is made.",
    )
    args = parser.parse_args(argv)
    try:
        command = json.loads(Path(args.command).read_text(encoding="utf-8"))
        result = preflight(command)
        if args.comment_output:
            Path(args.comment_output).write_text(result["commentBody"] + "\n", encoding="utf-8")
    except (RemoteCanonicalExecutionError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps(_error_payload(exc), ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
