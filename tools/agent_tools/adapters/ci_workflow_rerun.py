from __future__ import annotations

import re
from typing import Any

from tools import project_ci_observation
from tools.semantics.branches import parse_branch_name

REPOSITORY = "EAKerber/MobiliPresenter"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _positive_int(value: Any, code: str) -> int:
    if type(value) is not int or value <= 0:
        raise RuntimeError(code)
    return value


def _sha(value: Any) -> str:
    if not isinstance(value, str) or SHA_RE.fullmatch(value) is None:
        raise RuntimeError("AGENT_TOOL_CI_REENTRY_HEAD_INVALID")
    return value


def _run_ids(value: Any) -> list[int]:
    if (
        not isinstance(value, list)
        or not value
        or any(type(item) is not int or item <= 0 for item in value)
        or value != sorted(set(value))
    ):
        raise RuntimeError("AGENT_TOOL_CI_REENTRY_RUN_IDS_INVALID")
    return list(value)


def _input(request: dict[str, Any]) -> dict[str, Any]:
    value = request.get("input")
    if not isinstance(value, dict) or set(value) != {"prNumber", "headSha", "runIds"}:
        raise RuntimeError("AGENT_TOOL_CI_REENTRY_INPUT_INVALID")
    return {
        "prNumber": _positive_int(value.get("prNumber"), "AGENT_TOOL_CI_REENTRY_PR_INVALID"),
        "headSha": _sha(value.get("headSha")),
        "runIds": _run_ids(value.get("runIds")),
    }


def _operations_branch(branch: Any) -> bool:
    if not isinstance(branch, str):
        return False
    try:
        identity = parse_branch_name(branch)
    except RuntimeError:
        return False
    if identity.get("semanticDomain") != "operations":
        return False
    if identity.get("grammar") == "canonical":
        return identity.get("declaredClass") in {"work", "experiment"}
    return identity.get("grammar") == "legacy"


def _observed_pr(context: dict[str, Any], pr_number: int) -> dict[str, Any]:
    machine = context.get("projectMachine")
    sensors = machine.get("sensors") if isinstance(machine, dict) else None
    sensor = sensors.get("pullRequests") if isinstance(sensors, dict) else None
    data = sensor.get("data") if isinstance(sensor, dict) else None
    if not isinstance(data, dict) or data.get("available") is not True:
        raise RuntimeError("AGENT_TOOL_CI_REENTRY_PR_OBSERVATION_UNAVAILABLE")
    items = data.get("items")
    if not isinstance(items, list):
        raise RuntimeError("AGENT_TOOL_CI_REENTRY_PR_OBSERVATION_INVALID")
    matches = [item for item in items if isinstance(item, dict) and item.get("number") == pr_number]
    if len(matches) != 1:
        raise RuntimeError("AGENT_TOOL_CI_REENTRY_PR_NOT_EXACT")
    return matches[0]


def _bind_observation(value: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    observed = _observed_pr(context, value["prNumber"])
    if observed.get("ciObserved") is not True or observed.get("ci") != "reentry_required":
        raise RuntimeError("AGENT_TOOL_CI_REENTRY_NOT_PROVEN")
    if observed.get("headSha") != value["headSha"]:
        raise RuntimeError("AGENT_TOOL_CI_REENTRY_HEAD_MISMATCH")
    runs = observed.get("workflows")
    if not isinstance(runs, list):
        raise RuntimeError("AGENT_TOOL_CI_REENTRY_RUN_OBSERVATION_INVALID")
    include_agent_ops = _operations_branch(observed.get("headRef"))
    run_ids = project_ci_observation.reentry_run_ids(
        runs,
        value["headSha"],
        include_agent_ops=include_agent_ops,
    )
    if not run_ids:
        raise RuntimeError("AGENT_TOOL_CI_REENTRY_NOT_PROVEN")
    if run_ids != value["runIds"]:
        raise RuntimeError("AGENT_TOOL_CI_REENTRY_RUN_SET_MISMATCH")
    return observed


def build_concrete(
    request: dict[str, Any], context: dict[str, Any], **_: Any
) -> dict[str, Any]:
    value = _input(request)
    observed = _bind_observation(value, context)
    return {
        "kind": "github-workflow-rerun-plan",
        "repository": context.get("repository") or REPOSITORY,
        "prNumber": value["prNumber"],
        "headRef": observed.get("headRef"),
        "headSha": value["headSha"],
        "runIds": value["runIds"],
        "requests": [
            {
                "method": "POST",
                "endpoint": f"repos/{REPOSITORY}/actions/runs/{run_id}/rerun",
            }
            for run_id in value["runIds"]
        ],
        "executionStatus": "PLAN_ONLY",
        "requiredExecutionPermission": "actions:write",
        "executionProvider": None,
        "reasonCode": "CI_REENTRY_REQUIRED",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
