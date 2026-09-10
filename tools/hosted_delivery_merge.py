#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import delivery_merge

REQUEST_MARKER = "MOBILIPRESENTER_DELIVERY_MERGE_REQUEST_V0_1"
RESULT_MARKER = "MOBILIPRESENTER_DELIVERY_MERGE_RESULT_V0_1"
BUS_TITLE = "MobiliPresenter Remote Canonical Execution Bus"


def parse_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise delivery_merge.DeliveryMergeError("DELIVERY_MERGE_EVENT_INVALID")
    issue = value.get("issue")
    comment = value.get("comment")
    repository = value.get("repository")
    if not isinstance(issue, dict) or not isinstance(comment, dict) or not isinstance(repository, dict):
        raise delivery_merge.DeliveryMergeError("DELIVERY_MERGE_EVENT_INVALID")
    if issue.get("pull_request") is not None or issue.get("title") != BUS_TITLE:
        raise delivery_merge.DeliveryMergeError("DELIVERY_MERGE_BUS_MISMATCH")
    if comment.get("author_association") != "OWNER":
        raise delivery_merge.DeliveryMergeError("DELIVERY_MERGE_ACTOR_FORBIDDEN")
    if repository.get("full_name") != delivery_merge.REPOSITORY:
        raise delivery_merge.DeliveryMergeError("DELIVERY_MERGE_REPOSITORY_MISMATCH")
    body = comment.get("body")
    prefix = REQUEST_MARKER + "\n"
    if not isinstance(body, str) or not body.startswith(prefix):
        raise delivery_merge.DeliveryMergeError("DELIVERY_MERGE_MARKER_INVALID")
    try:
        request = json.loads(body[len(prefix):].strip())
    except json.JSONDecodeError as exc:
        raise delivery_merge.DeliveryMergeError("DELIVERY_MERGE_JSON_INVALID") from exc
    return delivery_merge.validate_request(request)


def _write(path: str, value: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hosted-delivery-merge")
    parser.add_argument("--event", required=True)
    parser.add_argument("--request-out", required=True)
    parser.add_argument("--dispatch-out", required=True)
    parser.add_argument("--result-out", required=True)
    args = parser.parse_args(argv)

    request: dict[str, Any] | None = None
    try:
        event = json.loads(Path(args.event).read_text(encoding="utf-8"))
        request = parse_event(event)
        _write(args.request_out, request)
        dispatch = delivery_merge.prepare(request)
        _write(args.dispatch_out, dispatch)
        result = delivery_merge.execute(dispatch)
        _write(args.result_out, result)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        result = delivery_merge.failure(exc, request)
        _write(args.result_out, result)
        print(json.dumps(result, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
