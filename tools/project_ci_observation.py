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
STATES = {"NOT_APPLICABLE", "GREEN", "PENDING", "FAILED", "REENTRY_REQUIRED", "UNKNOWN"}
CI_VALUES = {"green", "pending", "failed", "reentry_required", "unknown"}
SUCCESS_CONCLUSIONS = {"success", "neutral", "skipped"}
FAILURE_CONCLUSIONS = {"failure", "cancelled", "timed_out", "startup_failure"}
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
RUN_FIELDS = {
    "name",
    "id",
    "status",
    "conclusion",
    "event",
    "headSha",
    "actor",
    "triggeringActor",
    "sameRepository",
    "runAttempt",
    "jobsObserved",
    "jobCount",
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


def _login(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        login = value.get("login")
        if isinstance(login, str) and login:
            return login
    return None


def normalize_run(
    raw: Any,
    *,
    repository: str,
    jobs_observed: bool = False,
    job_count: int | None = None,
) -> dict[str, Any]:
    """Normalize one GitHub workflow run into the facts needed for CI semantics."""
    if not isinstance(raw, dict):
        raise ProjectCIObservationError("PROJECT_CI_RUN_INVALID")
    if not isinstance(repository, str) or not repository:
        raise ProjectCIObservationError("PROJECT_CI_REPOSITORY_INVALID")
    run_id = _positive_int(raw.get("id"), "PROJECT_CI_RUN_ID_INVALID")
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise ProjectCIObservationError("PROJECT_CI_RUN_NAME_INVALID")
    status = str(raw.get("status") or "").lower()
    conclusion = str(raw.get("conclusion") or "").lower() or None
    event = str(raw.get("event") or "").lower() or None
    head_sha = raw.get("headSha") if isinstance(raw.get("headSha"), str) else raw.get("head_sha")
    if head_sha is not None:
        _sha(head_sha, "PROJECT_CI_RUN_HEAD_INVALID")
    actor = _login(raw.get("actor"))
    triggering = _login(raw.get("triggeringActor")) or _login(raw.get("triggering_actor"))
    same_repository = raw.get("sameRepository")
    if not isinstance(same_repository, bool):
        head_repository = raw.get("head_repository")
        full_name = head_repository.get("full_name") if isinstance(head_repository, dict) else None
        same_repository = full_name == repository if isinstance(full_name, str) else False
    run_attempt = raw.get("runAttempt") if type(raw.get("runAttempt")) is int else raw.get("run_attempt")
    if run_attempt is not None and (type(run_attempt) is not int or run_attempt <= 0):
        raise ProjectCIObservationError("PROJECT_CI_RUN_ATTEMPT_INVALID")
    if not isinstance(jobs_observed, bool):
        raise ProjectCIObservationError("PROJECT_CI_RUN_JOBS_OBSERVED_INVALID")
    if job_count is not None and (type(job_count) is not int or job_count < 0):
        raise ProjectCIObservationError("PROJECT_CI_RUN_JOB_COUNT_INVALID")
    if not jobs_observed:
        job_count = None
    return {
        "name": name,
        "id": run_id,
        "status": status,
        "conclusion": conclusion,
        "event": event,
        "headSha": head_sha,
        "actor": actor,
        "triggeringActor": triggering,
        "sameRepository": same_repository,
        "runAttempt": run_attempt,
        "jobsObserved": jobs_observed,
        "jobCount": job_count,
    }


def _classification_run(raw: Any) -> dict[str, Any]:
    """Accept enriched sensor runs and legacy minimal run fixtures.

    Re-entry is provable only from the enriched shape. Minimal historical callers
    retain success/failure/pending classification but can never prove re-entry.
    """
    if not isinstance(raw, dict):
        raise ProjectCIObservationError("PROJECT_CI_RUN_INVALID")
    if set(raw) == RUN_FIELDS:
        return raw
    name = raw.get("name")
    run_id = raw.get("id")
    if not isinstance(name, str) or not name or type(run_id) is not int or run_id <= 0:
        raise ProjectCIObservationError("PROJECT_CI_RUN_FIELDS_INVALID")
    status = str(raw.get("status") or "").lower()
    conclusion = str(raw.get("conclusion") or "").lower() or None
    return {
        "name": name,
        "id": run_id,
        "status": status,
        "conclusion": conclusion,
        "event": None,
        "headSha": None,
        "actor": None,
        "triggeringActor": None,
        "sameRepository": False,
        "runAttempt": None,
        "jobsObserved": False,
        "jobCount": None,
    }


def _latest_runs(runs: list[dict[str, Any]], *, include_agent_ops: bool) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for raw in runs:
        run = _classification_run(raw)
        name = run["name"]
        if name == "Agent Ops" and not include_agent_ops:
            continue
        latest.setdefault(name, run)
    return list(latest.values())


def _proven_reentry(run: dict[str, Any], head_sha: str) -> bool:
    return (
        run["status"] == "completed"
        and run["conclusion"] == "action_required"
        and run["event"] == "pull_request"
        and run["headSha"] == head_sha
        and run["sameRepository"] is True
        and run["jobsObserved"] is True
        and run["jobCount"] == 0
        and "github-actions[bot]" in {run["actor"], run["triggeringActor"]}
    )


def classify_runs(
    runs: list[dict[str, Any]],
    head_sha: str,
    *,
    include_agent_ops: bool = False,
) -> str:
    """Classify latest exact-head runs while preserving known GitHub CI re-entry."""
    head_sha = _sha(head_sha, "PROJECT_CI_PR_HEAD_INVALID")
    selected = _latest_runs(runs, include_agent_ops=include_agent_ops)
    if not selected:
        return "unknown"
    if any(run["status"] != "completed" for run in selected):
        return "pending"
    conclusions = {run["conclusion"] for run in selected}
    if conclusions <= SUCCESS_CONCLUSIONS:
        return "green"
    if conclusions & FAILURE_CONCLUSIONS:
        return "failed"
    action_required = [run for run in selected if run["conclusion"] == "action_required"]
    if action_required:
        if all(_proven_reentry(run, head_sha) for run in action_required):
            return "reentry_required"
        return "unknown"
    return "unknown"


def reentry_run_ids(
    runs: list[dict[str, Any]], head_sha: str, *, include_agent_ops: bool = False
) -> list[int]:
    if classify_runs(runs, head_sha, include_agent_ops=include_agent_ops) != "reentry_required":
        return []
    return sorted(
        run["id"]
        for run in _latest_runs(runs, include_agent_ops=include_agent_ops)
        if _proven_reentry(run, head_sha)
    )


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
    elif ci == "reentry_required":
        state = "REENTRY_REQUIRED"
        reason = "PR_CI_REENTRY_REQUIRED"
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
    if "REENTRY_REQUIRED" in states:
        return "REENTRY_REQUIRED"
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
