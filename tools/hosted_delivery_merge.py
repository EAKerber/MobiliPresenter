from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools import delivery_merge
from tools import hosted_issue_bus
from tools.coordination_remote import GhApiTransport

REQUEST_MARKER = "MOBILIPRESENTER_DELIVERY_MERGE_REQUEST_V0_1"
RESULT_MARKER = "MOBILIPRESENTER_DELIVERY_MERGE_RESULT_V0_1"
BUS_TITLE = "MobiliPresenter Remote Canonical Execution Bus"


def parse_event(value: Any) -> dict[str, Any]:
    try:
        envelope = hosted_issue_bus.validate_event_envelope(
            value,
            repository=delivery_merge.REPOSITORY,
            bus_title=BUS_TITLE,
        )
    except hosted_issue_bus.HostedIssueBusError as exc:
        code = {
            "HOSTED_ISSUE_BUS_EVENT_INVALID": "DELIVERY_MERGE_EVENT_INVALID",
            "HOSTED_ISSUE_BUS_PR_COMMENT_FORBIDDEN": "DELIVERY_MERGE_BUS_MISMATCH",
            "HOSTED_ISSUE_BUS_BUS_MISMATCH": "DELIVERY_MERGE_BUS_MISMATCH",
            "HOSTED_ISSUE_BUS_ACTOR_FORBIDDEN": "DELIVERY_MERGE_ACTOR_FORBIDDEN",
            "HOSTED_ISSUE_BUS_REPOSITORY_MISMATCH": "DELIVERY_MERGE_REPOSITORY_MISMATCH",
            "HOSTED_ISSUE_BUS_BODY_INVALID": "DELIVERY_MERGE_MARKER_INVALID",
        }.get(exc.code, "DELIVERY_MERGE_EVENT_INVALID")
        raise delivery_merge.DeliveryMergeError(code) from exc
    body = envelope["body"]
    prefix = REQUEST_MARKER + "\n"
    if not body.startswith(prefix):
        raise delivery_merge.DeliveryMergeError("DELIVERY_MERGE_MARKER_INVALID")
    try:
        request = json.loads(body[len(prefix):].strip())
    except json.JSONDecodeError as exc:
        raise delivery_merge.DeliveryMergeError("DELIVERY_MERGE_JSON_INVALID") from exc
    return delivery_merge.validate_request(request)


def _write(path: str, value: dict[str, Any]) -> None:
    Path(path).write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run_event_file(
    *,
    event_path: str,
    request_out: str,
    dispatch_out: str,
    result_out: str,
) -> int:
    request: dict[str, Any] | None = None
    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
        request = parse_event(event)
        _write(request_out, request)
        carrier = GhApiTransport()
        dispatch = delivery_merge.prepare(request, transport=carrier)
        _write(dispatch_out, dispatch)
        result = delivery_merge.execute(dispatch, transport=carrier)
        _write(result_out, result)
        return 0
    except Exception as exc:
        result = delivery_merge.failure(exc, request)
        _write(result_out, result)
        return 2
