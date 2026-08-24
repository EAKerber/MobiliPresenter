from __future__ import annotations

import copy
from typing import Any


def build_concrete(request: dict[str, Any], context: dict[str, Any], **_: Any) -> dict[str, Any]:
    return {
        "kind": "begin-projection",
        "artifact": "projectMachine",
        "sourceContextHash": context["contextHash"],
    }


def execute(request: dict[str, Any], context: dict[str, Any], **_: Any) -> dict[str, Any]:
    return copy.deepcopy(context["projectMachine"])
