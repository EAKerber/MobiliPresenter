from __future__ import annotations

import copy
from typing import Any


def build_concrete(request: dict[str, Any], context: dict[str, Any], **_: Any) -> dict[str, Any]:
    return {
        "kind": "begin-projection",
        "artifact": "routineInspection",
        "sourceContextHash": context["contextHash"],
    }


def execute(request: dict[str, Any], context: dict[str, Any], **_: Any) -> dict[str, Any]:
    slot = context["routineInspection"]
    if slot.get("status") != "PASS" or not isinstance(slot.get("value"), dict):
        raise RuntimeError("AGENT_TOOL_ROUTINE_INSPECTION_UNAVAILABLE")
    return copy.deepcopy(slot["value"])
