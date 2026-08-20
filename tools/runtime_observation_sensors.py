#!/usr/bin/env python3
"""Pure projection of external RuntimeObservationBundle facts into Project sensors."""
from __future__ import annotations

from typing import Any

from tools import continuation, coordination, project_sensors, project_state, runtime_observations
from tools.semantics.observation import ObservationStatus


def _sha(value: Any, code: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
        raise RuntimeError(code)
    return value


def _control(state: dict[str, Any], obs: dict[str, Any]) -> dict[str, Any]:
    branch = project_state.operational_view(state)["git"]["controlBranch"]
    authority = {"kind": "git-ref", "branch": branch}
    raw = obs.get("data") if isinstance(obs.get("data"), dict) else {}
    status = str(obs.get("status") or "").upper()
    try:
        if set(raw) != {"branch", "sha"}:
            raise RuntimeError("CONTROL_OBSERVATION_FIELDS_INVALID")
        if raw.get("branch") != branch:
            raise RuntimeError("CONTROL_BRANCH_MISMATCH")
        sha = _sha(raw.get("sha"), "CONTROL_HEAD_INVALID", nullable=status != ObservationStatus.PASS.value)
        return project_sensors.sensor(
            status,
            code=None if status == ObservationStatus.PASS.value else obs.get("code"),
            data={"branch": branch, "sha": sha, "mode": "remote"},
            authority=authority,
        )
    except RuntimeError as exc:
        return project_sensors.sensor("FAIL", code=str(exc).split(":", 1)[0], data={"branch": branch, "sha": None, "mode": "remote"}, authority=authority)


def _workflow(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"name", "status", "conclusion", "id"}:
        raise RuntimeError("PR_WORKFLOW_EVIDENCE_INVALID")
    if value.get("name") is not None and not isinstance(value.get("name"), str):
        raise RuntimeError("PR_WORKFLOW_EVIDENCE_INVALID")
    if value.get("status") is not None and not isinstance(value.get("status"), str):
        raise RuntimeError("PR_WORKFLOW_EVIDENCE_INVALID")
    if value.get("conclusion") is not None and not isinstance(value.get("conclusion"), str):
        raise RuntimeError("PR_WORKFLOW_EVIDENCE_INVALID")
    if value.get("id") is not None and (type(value.get("id")) is not int or value.get("id") <= 0):
        raise RuntimeError("PR_WORKFLOW_EVIDENCE_INVALID")
    return {key: value.get(key) for key in ("name", "status", "conclusion", "id")}


def _pr(value: Any) -> dict[str, Any]:
    fields = {"number", "draft", "headRef", "headSha", "baseRef", "ci", "ciObserved", "workflows"}
    if not isinstance(value, dict) or set(value) != fields:
        raise RuntimeError("PR_OBSERVATION_ITEM_INVALID")
    number = value.get("number")
    if type(number) is not int or number <= 0:
        raise RuntimeError("PR_OBSERVATION_NUMBER_INVALID")
    if not isinstance(value.get("draft"), bool):
        raise RuntimeError("PR_OBSERVATION_DRAFT_INVALID")
    for key in ("headRef", "baseRef"):
        if not isinstance(value.get(key), str) or not value[key]:
            raise RuntimeError("PR_OBSERVATION_REF_INVALID")
    head_sha = _sha(value.get("headSha"), "PR_OBSERVATION_HEAD_INVALID")
    ci = str(value.get("ci") or "").lower()
    if ci not in {"green", "pending", "failed", "unknown"}:
        raise RuntimeError("PR_OBSERVATION_CI_INVALID")
    if not isinstance(value.get("ciObserved"), bool) or not isinstance(value.get("workflows"), list):
        raise RuntimeError("PR_OBSERVATION_CI_EVIDENCE_INVALID")
    return {
        "number": number,
        "draft": value["draft"],
        "headRef": value["headRef"],
        "headSha": head_sha,
        "baseRef": value["baseRef"],
        "ci": ci,
        "ciObserved": value["ciObserved"],
        "workflows": [_workflow(item) for item in value["workflows"]],
    }


def _pull_requests(obs: dict[str, Any]) -> dict[str, Any]:
    authority = {"kind": "github", "resource": "pull-requests"}
    raw = obs.get("data") if isinstance(obs.get("data"), dict) else {}
    status = str(obs.get("status") or "").upper()
    try:
        if set(raw) != {"items"} or not isinstance(raw.get("items"), list):
            raise RuntimeError("PR_OBSERVATION_FIELDS_INVALID")
        if status != ObservationStatus.PASS.value:
            if raw["items"]:
                raise RuntimeError("PR_UNKNOWN_ITEMS_INVALID")
            return project_sensors.sensor(status, code=obs.get("code"), data={"available": False, "reason": obs.get("code"), "items": []}, authority=authority)
        items = [_pr(item) for item in raw["items"]]
        numbers = [item["number"] for item in items]
        if len(numbers) != len(set(numbers)):
            raise RuntimeError("PR_OBSERVATION_DUPLICATE")
        items.sort(key=lambda item: item["number"])
        return project_sensors.sensor("PASS", data={"available": True, "items": items}, authority=authority)
    except RuntimeError as exc:
        return project_sensors.sensor("FAIL", code=str(exc).split(":", 1)[0], data={"available": False, "reason": "INVALID_OBSERVED_EVIDENCE", "items": []}, authority=authority)


def _continuation_item(value: dict[str, Any]) -> dict[str, Any]:
    view = continuation.operational_view(value)
    return {**view, "sourceSchemaVersion": value["schemaVersion"], "stateHash": continuation.state_hash(value)}


def _continuations(obs: dict[str, Any]) -> dict[str, Any]:
    branch = "coordination/continuations"
    authority = {"kind": "git-authority", "branch": branch}
    raw = obs.get("data") if isinstance(obs.get("data"), dict) else {}
    status = str(obs.get("status") or "").upper()
    try:
        if set(raw) != {"authorityBranch", "authorityHead", "items"}:
            raise RuntimeError("CONTINUATION_OBSERVATION_FIELDS_INVALID")
        if raw.get("authorityBranch") != branch:
            raise RuntimeError("CONTINUATION_AUTHORITY_BRANCH_MISMATCH")
        head = _sha(raw.get("authorityHead"), "CONTINUATION_AUTHORITY_HEAD_INVALID", nullable=status != ObservationStatus.PASS.value)
        if not isinstance(raw.get("items"), list):
            raise RuntimeError("CONTINUATION_OBSERVATION_ITEMS_INVALID")
        if status != ObservationStatus.PASS.value:
            if raw["items"]:
                raise RuntimeError("CONTINUATION_UNKNOWN_ITEMS_INVALID")
            return project_sensors.sensor(status, code=obs.get("code"), data={"available": False, "reason": obs.get("code"), "authorityBranch": branch, "authorityHead": head, "items": [], "mode": "external-observation"}, authority=authority)
        by_id: dict[str, dict[str, Any]] = {}
        for value in raw["items"]:
            if not isinstance(value, dict):
                raise RuntimeError("CONTINUATION_OBSERVATION_ITEM_INVALID")
            cid = value.get("id")
            if not isinstance(cid, str) or not cid or cid in by_id:
                raise RuntimeError("CONTINUATION_OBSERVATION_ID_INVALID")
            errors = continuation.validate_current(value, cid)
            if errors:
                raise RuntimeError(errors[0])
            by_id[cid] = value
        items = [_continuation_item(by_id[cid]) for cid in sorted(by_id)]
        return project_sensors.sensor("PASS", data={"available": True, "authorityBranch": branch, "authorityHead": head, "items": items, "mode": "live-authority"}, authority=authority)
    except RuntimeError as exc:
        return project_sensors.sensor("FAIL", code=str(exc).split(":", 1)[0], data={"available": False, "reason": "INVALID_OBSERVED_EVIDENCE", "authorityBranch": branch, "authorityHead": None, "items": [], "mode": "external-observation"}, authority=authority)


def _coordination(obs: dict[str, Any]) -> dict[str, Any]:
    branch = "coordination/leases"
    authority = {"kind": "git-authority", "branch": branch}
    raw = obs.get("data") if isinstance(obs.get("data"), dict) else {}
    status = str(obs.get("status") or "").upper()
    try:
        if set(raw) != {"authorityBranch", "authorityHead", "state", "trustedRemoteTime"}:
            raise RuntimeError("COORDINATION_OBSERVATION_FIELDS_INVALID")
        if raw.get("authorityBranch") != branch:
            raise RuntimeError("COORDINATION_AUTHORITY_BRANCH_MISMATCH")
        head = _sha(raw.get("authorityHead"), "COORDINATION_AUTHORITY_HEAD_INVALID", nullable=status != ObservationStatus.PASS.value)
        state = raw.get("state")
        if state is not None:
            coordination.validate_state(state)
        elif status == ObservationStatus.PASS.value:
            raise RuntimeError("COORDINATION_STATE_MISSING")
        if status != ObservationStatus.PASS.value:
            return project_sensors.sensor(status, code=obs.get("code"), data={"available": False, "reason": obs.get("code"), "authorityBranch": branch, "authorityHead": head, "intents": [], "leases": []}, authority=authority)
        authority_now = raw.get("trustedRemoteTime")
        if authority_now is None:
            return project_sensors.sensor("UNKNOWN", code="TRUSTED_REMOTE_TIME_UNAVAILABLE", data={"available": False, "reason": "TRUSTED_REMOTE_TIME_UNAVAILABLE", "authorityBranch": branch, "authorityHead": head, "intents": [], "leases": []}, authority=authority)
        current = coordination.compact_expired(state, authority_now)
        return project_sensors.sensor("PASS", data={"available": True, "authorityBranch": branch, "authorityHead": head, "intents": current["intents"], "leases": current["leases"]}, authority=authority)
    except RuntimeError as exc:
        return project_sensors.sensor("FAIL", code=getattr(exc, "code", str(exc).split(":", 1)[0]), data={"available": False, "reason": "INVALID_OBSERVED_EVIDENCE", "authorityBranch": branch, "authorityHead": None, "intents": [], "leases": []}, authority=authority)


def observe_bundle(state: dict[str, Any], bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Project a validated closed bundle without any transport fallback."""
    value = runtime_observations.validate_bundle(bundle)
    view = project_state.operational_view(state)
    if value["repository"] != view["project"]["repository"]:
        raise RuntimeError("RUNTIME_OBSERVATION_REPOSITORY_MISMATCH")
    observations = value["observations"]
    return {
        "control": _control(state, observations["control"]),
        "pullRequests": _pull_requests(observations["pullRequests"]),
        "coordination": _coordination(observations["coordination"]),
        "continuations": _continuations(observations["continuations"]),
    }
