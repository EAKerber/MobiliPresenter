"""Deterministic read-only semantics for CI facts on open pull requests.

This module distinguishes transport observation from the observed CI lifecycle.
It does not decide whether CI should gate a ProjectMachine inspection, close,
promotion, quiescence, or any mutation.
"""
from __future__ import annotations

import copy
from typing import Any

from tools.canonical import stable_hash

SCHEMA = "ProjectCIObservation 0.1"
STATES = {"NOT_APPLICABLE", "GREEN", "PENDING", "FAILED", "UNKNOWN"}
CI_VALUES = {"green", "pending", "failed", "unknown"}
FIELDS = {
    "schemaVersion",
    "state",
    "reasonCodes",
    "items",
    "readOnly",
    "semanticAuthority",
    "authorizesMutation",
    "observationHash",
}
ITEM_FIELDS = {
    "number",
    "headSha",
    "ci",
    "ciObserved",
    "state",
    "reasonCode",
}


class ProjectCIObservationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _positive_int(value: Any, code: str) -> int:
    if type(value) is not int or value <= 0:
        raise ProjectCIObservationError(code)
    return value


def _sha(value: Any, code: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ProjectCIObservationError(code)
    return value


def _item(pr: Any) -> dict[str, Any]:
    if not isinstance(pr, dict):
        raise ProjectCIObservationError("PROJECT_CI_PR_INVALID")
    number = _positive_int(pr.get("number"), "PROJECT_CI_PR_NUMBER_INVALID")
    head_sha = _sha(pr.get("headSha"), "PROJECT_CI_PR_HEAD_INVALID")
    observed = pr.get("ciObserved")
    if not isinstance(observed, bool):
        raise ProjectCIObservationError("PROJECT_CI_OBSERVED_INVALID")
    ci = str(pr.get("ci") or "").lower()
    if ci not in CI_VALUES:
        raise ProjectCIObservationError("PROJECT_CI_STATE_INVALID")

    if not observed:
        state = "UNKNOWN"
        reason = "PR_CI_OBSERVATION_UNAVAILABLE"
    elif ci == "green":
        state = "GREEN"
        reason = "PR_CI_GREEN"
    elif ci == "pending":
        state = "PENDING"
        reason = "PR_CI_PENDING"
    elif ci == "failed":
        state = "FAILED"
        reason = "PR_CI_FAILED"
    else:
        state = "UNKNOWN"
        reason = "PR_CI_STATE_UNKNOWN"

    return {
        "number": number,
        "headSha": head_sha,
        "ci": ci,
        "ciObserved": observed,
        "state": state,
        "reasonCode": reason,
    }


def _summary_state(items: list[dict[str, Any]]) -> str:
    if not items:
        return "NOT_APPLICABLE"
    states = {item["state"] for item in items}
    if "FAILED" in states:
        return "FAILED"
    if "UNKNOWN" in states:
        return "UNKNOWN"
    if "PENDING" in states:
        return "PENDING"
    return "GREEN"


def build(pr_sensor: Any) -> dict[str, Any]:
    """Project one canonical pullRequests sensor into explicit CI semantics."""
    if not isinstance(pr_sensor, dict):
        raise ProjectCIObservationError("PROJECT_CI_SENSOR_INVALID")
    data = pr_sensor.get("data")
    if not isinstance(data, dict):
        raise ProjectCIObservationError("PROJECT_CI_SENSOR_DATA_INVALID")

    if data.get("available") is not True:
        items: list[dict[str, Any]] = []
        state = "UNKNOWN"
        reasons = ["PR_INVENTORY_UNAVAILABLE"]
    else:
        raw_items = data.get("items")
        if not isinstance(raw_items, list):
            raise ProjectCIObservationError("PROJECT_CI_ITEMS_INVALID")
        items = [_item(item) for item in raw_items]
        items.sort(key=lambda item: item["number"])
        numbers = [item["number"] for item in items]
        if numbers != sorted(set(numbers)):
            raise ProjectCIObservationError("PROJECT_CI_PR_DUPLICATE")
        state = _summary_state(items)
        reasons = sorted(set(item["reasonCode"] for item in items))
        if not items:
            reasons = ["NO_OPEN_PRS"]

    core = {
        "schemaVersion": SCHEMA,
        "state": state,
        "reasonCodes": reasons,
        "items": items,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return validate({**core, "observationHash": stable_hash(core)})


def validate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ProjectCIObservationError("PROJECT_CI_FIELDS_INVALID")
    if (
        value.get("schemaVersion") != SCHEMA
        or value.get("state") not in STATES
        or value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise ProjectCIObservationError("PROJECT_CI_BOUNDARY_INVALID")

    reasons = value.get("reasonCodes")
    if (
        not isinstance(reasons, list)
        or not reasons
        or reasons != sorted(set(reasons))
        or any(not isinstance(reason, str) or not reason for reason in reasons)
    ):
        raise ProjectCIObservationError("PROJECT_CI_REASONS_INVALID")

    items = value.get("items")
    if not isinstance(items, list):
        raise ProjectCIObservationError("PROJECT_CI_ITEMS_INVALID")
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or set(item) != ITEM_FIELDS:
            raise ProjectCIObservationError("PROJECT_CI_ITEM_FIELDS_INVALID")
        number = _positive_int(item.get("number"), "PROJECT_CI_PR_NUMBER_INVALID")
        _sha(item.get("headSha"), "PROJECT_CI_PR_HEAD_INVALID")
        if item.get("ci") not in CI_VALUES or not isinstance(item.get("ciObserved"), bool):
            raise ProjectCIObservationError("PROJECT_CI_ITEM_INVALID")
        expected = _item(
            {
                "number": number,
                "headSha": item["headSha"],
                "ci": item["ci"],
                "ciObserved": item["ciObserved"],
            }
        )
        if item != expected:
            raise ProjectCIObservationError("PROJECT_CI_ITEM_MISMATCH")
        normalized.append(copy.deepcopy(item))
    if items != sorted(normalized, key=lambda item: item["number"]):
        raise ProjectCIObservationError("PROJECT_CI_ITEM_ORDER_INVALID")
    numbers = [item["number"] for item in items]
    if numbers != sorted(set(numbers)):
        raise ProjectCIObservationError("PROJECT_CI_PR_DUPLICATE")

    if items:
        expected_state = _summary_state(items)
        expected_reasons = sorted(set(item["reasonCode"] for item in items))
    elif value["state"] == "UNKNOWN":
        expected_state = "UNKNOWN"
        expected_reasons = ["PR_INVENTORY_UNAVAILABLE"]
    else:
        expected_state = "NOT_APPLICABLE"
        expected_reasons = ["NO_OPEN_PRS"]
    if value["state"] != expected_state or reasons != expected_reasons:
        raise ProjectCIObservationError("PROJECT_CI_SUMMARY_MISMATCH")

    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "observationHash"}
    if value.get("observationHash") != stable_hash(core):
        raise ProjectCIObservationError("PROJECT_CI_HASH_MISMATCH")
    return value
