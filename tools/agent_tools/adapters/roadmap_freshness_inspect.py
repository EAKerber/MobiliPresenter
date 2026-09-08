from __future__ import annotations

import re
from typing import Any

from tools import roadmap_freshness

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _sha(value: Any) -> str:
    if not isinstance(value, str) or SHA_RE.fullmatch(value) is None:
        raise RuntimeError("AGENT_TOOL_ROADMAP_FRESHNESS_SHA_INVALID")
    return value


def _input(request: dict[str, Any]) -> dict[str, str]:
    value = request.get("input")
    if not isinstance(value, dict) or set(value) != {"baseSha", "headSha"}:
        raise RuntimeError("AGENT_TOOL_ROADMAP_FRESHNESS_INPUT_INVALID")
    return {
        "baseSha": _sha(value.get("baseSha")),
        "headSha": _sha(value.get("headSha")),
    }


def build_concrete(request: dict[str, Any], context: dict[str, Any], **_: Any) -> dict[str, Any]:
    value = _input(request)
    return {
        "kind": "roadmap-freshness-inspection",
        "baseSha": value["baseSha"],
        "headSha": value["headSha"],
        "coveragePath": roadmap_freshness.COVERAGE_PATH.relative_to(roadmap_freshness.ROOT).as_posix(),
    }


def execute(request: dict[str, Any], context: dict[str, Any], **_: Any) -> dict[str, Any]:
    value = _input(request)
    return roadmap_freshness.command_inspect(
        value["baseSha"],
        value["headSha"],
        roadmap_freshness.COVERAGE_PATH,
    )
