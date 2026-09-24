#!/usr/bin/env python3
"""Thin caller-side renderer for the in-house governed mutation counter.

The client owns no authority and performs no transport side effect. It only
canonicalizes the four semantic caller inputs into the existing E4 service
request and renders the exact issue-comment body consumed by the hosted bus.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import governed_mutation_service as service


class GovernedMutationClientError(RuntimeError):
    pass


def _changes(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise GovernedMutationClientError("GOVERNED_MUTATION_CLIENT_CHANGES_REQUIRED")
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise GovernedMutationClientError("GOVERNED_MUTATION_CLIENT_CHANGE_INVALID")
        normalized.append(copy.deepcopy(item))
    normalized.sort(key=lambda item: item["path"])
    return normalized


def build_request(
    *,
    work_id: str,
    branch: str,
    changes: list[dict[str, Any]],
    message: str,
) -> dict[str, Any]:
    value = {
        "schemaVersion": service.REQUEST_SCHEMA,
        "workId": work_id,
        "branch": branch,
        "changes": _changes(changes),
        "message": message,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return service.validate_request(value)


def render_comment(request: dict[str, Any]) -> str:
    value = service.validate_request(copy.deepcopy(request))
    return service.REQUEST_MARKER + "\n" + json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def build_comment(
    *,
    work_id: str,
    branch: str,
    changes: list[dict[str, Any]],
    message: str,
) -> str:
    return render_comment(
        build_request(
            work_id=work_id,
            branch=branch,
            changes=changes,
            message=message,
        )
    )


def _load_changes(*, inline: str | None, path: str | None) -> list[dict[str, Any]]:
    if (inline is None) == (path is None):
        raise GovernedMutationClientError(
            "GOVERNED_MUTATION_CLIENT_CHANGES_SOURCE_REQUIRED"
        )
    try:
        value = json.loads(inline) if inline is not None else json.loads(
            Path(path).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernedMutationClientError(
            "GOVERNED_MUTATION_CLIENT_CHANGES_JSON_INVALID"
        ) from exc
    return _changes(value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a governed mutation service request comment"
    )
    parser.add_argument("--work-id", required=True)
    parser.add_argument("--branch", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--changes-json")
    source.add_argument("--changes-file")
    parser.add_argument("--message", required=True)
    parser.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Print the canonical service request instead of the bus comment",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        request = build_request(
            work_id=args.work_id,
            branch=args.branch,
            changes=_load_changes(
                inline=args.changes_json, path=args.changes_file
            ),
            message=args.message,
        )
        if args.as_json:
            print(json.dumps(request, indent=2, ensure_ascii=False, sort_keys=True))
        else:
            print(render_comment(request))
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
