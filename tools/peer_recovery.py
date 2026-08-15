#!/usr/bin/env python3
"""Pure deterministic peer health/recovery inspection and planning.

This module intentionally performs no network access, Git mutation, Gmail access,
lease/continuation mutation, or Scheduled Task control. Runtime adapters normalize
observations and execute any later authorized action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

OBS_SCHEMA = "WorkerObservation 0.1"
REPRO_SCHEMA = "PeerReproduction 0.1"
INPUT_SCHEMA = "PeerRecoveryInput 0.1"
INSPECTION_SCHEMA = "PeerRecoveryInspection 0.1"
PLAN_SCHEMA = "PeerRecoveryPlan 0.1"
ERROR_EXIT = 2

STATES = {"HEALTHY", "DEGRADED", "SILENT_UNKNOWN", "PAUSING_UNAVAILABLE"}
ACTIONS = {"NOOP", "OBSERVE", "REPRODUCE", "REPAIR_SHARED", "REQUEST_RETRY", "QUARANTINE", "NEEDS_HUMAN"}
SIGNALS = {"NONE", "RECOVERY_READY", "RETRY_RECOMMENDED", "NEEDS_HUMAN"}
AUTHORITY_SOURCES = {"git-observed", "transport-claimed", "unavailable"}
FAILURE_SOURCES = {"runtime-observed", "agent-bus", "manual"}
REMEDIATION_SCOPES = {"peer-runtime", "shared-gitops"}
AUTHORITY_BASES = {"canonical-policy", "none"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
TOKEN_RE = re.compile(r"^[A-Z0-9][A-Z0-9_.-]*$")
WORKER_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise RuntimeError(code)


def require_token(value: Any, code: str) -> str:
    require(isinstance(value, str) and bool(TOKEN_RE.fullmatch(value)), code)
    return value


def require_worker(value: Any, code: str) -> str:
    require(isinstance(value, str) and bool(WORKER_RE.fullmatch(value)), code)
    return value


def normalize_heads(value: Any) -> dict[str, str | None]:
    require(isinstance(value, dict), "PEER_RECOVERY_AUTHORITY_HEADS_INVALID")
    require(set(value) == {"control", "coordination", "continuation"}, "PEER_RECOVERY_AUTHORITY_HEAD_FIELDS_INVALID")
    out: dict[str, str | None] = {}
    for key in ("control", "coordination", "continuation"):
        raw = value.get(key)
        require(raw is None or (isinstance(raw, str) and bool(SHA_RE.fullmatch(raw))), f"PEER_RECOVERY_{key.upper()}_HEAD_INVALID")
        out[key] = raw
    return out


def normalize_failure(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    require(isinstance(value, dict), "PEER_RECOVERY_FAILURE_INVALID")
    require(set(value) == {"code", "surface", "operation"}, "PEER_RECOVERY_FAILURE_FIELDS_INVALID")
    return {
        "code": require_token(value.get("code"), "PEER_RECOVERY_FAILURE_CODE_INVALID"),
        "surface": require_token(value.get("surface"), "PEER_RECOVERY_FAILURE_SURFACE_INVALID"),
        "operation": require_token(value.get("operation"), "PEER_RECOVERY_FAILURE_OPERATION_INVALID"),
    }


def failure_fingerprint(value: dict[str, str] | None) -> str | None:
    if value is None:
        return None
    return stable_hash({"code": value["code"], "surface": value["surface"], "operation": value["operation"]})


def normalize_events(value: Any) -> list[dict[str, Any]]:
    require(isinstance(value, list), "PEER_RECOVERY_EVENTS_INVALID")
    by_id: dict[str, dict[str, Any]] = {}
    for raw in value:
        require(isinstance(raw, dict), "PEER_RECOVERY_EVENT_INVALID")
        require(set(raw) == {"eventId", "source", "structured"}, "PEER_RECOVERY_EVENT_FIELDS_INVALID")
        event_id = raw.get("eventId")
        source = raw.get("source")
        structured = raw.get("structured")
        require(isinstance(event_id, str) and bool(event_id.strip()), "PEER_RECOVERY_EVENT_ID_INVALID")
        require(source in FAILURE_SOURCES, "PEER_RECOVERY_EVENT_SOURCE_INVALID")
        require(type(structured) is bool, "PEER_RECOVERY_EVENT_STRUCTURED_INVALID")
        normalized = {"eventId": event_id.strip(), "source": source, "structured": structured}
        existing = by_id.get(normalized["eventId"])
        require(existing is None or existing == normalized, "PEER_RECOVERY_EVENT_ID_CONFLICT")
        by_id[normalized["eventId"]] = normalized
    return [by_id[key] for key in sorted(by_id)]


def normalize_last_known_good(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    require(isinstance(value, dict), "PEER_RECOVERY_LAST_GOOD_INVALID")
    require(set(value) == {"authorityHeads", "inspectionHash", "planHash"}, "PEER_RECOVERY_LAST_GOOD_FIELDS_INVALID")
    heads = normalize_heads(value.get("authorityHeads"))
    inspection_hash = value.get("inspectionHash")
    plan_hash = value.get("planHash")
    for raw, code in ((inspection_hash, "PEER_RECOVERY_LAST_GOOD_INSPECTION_HASH_INVALID"), (plan_hash, "PEER_RECOVERY_LAST_GOOD_PLAN_HASH_INVALID")):
        require(raw is None or (isinstance(raw, str) and len(raw) == 64 and all(c in "0123456789abcdef" for c in raw)), code)
    return {"authorityHeads": heads, "inspectionHash": inspection_hash, "planHash": plan_hash}


def normalize_observation(value: Any) -> dict[str, Any]:
    require(isinstance(value, dict), "PEER_RECOVERY_OBSERVATION_INVALID")
    expected = {
        "schemaVersion", "workerId", "roleId", "state", "authoritySource", "authorityHeads",
        "failure", "failureSource", "consecutiveFailureCount", "lastKnownGood", "events",
    }
    require(set(value) == expected, "PEER_RECOVERY_OBSERVATION_FIELDS_INVALID")
    require(value.get("schemaVersion") == OBS_SCHEMA, "PEER_RECOVERY_OBSERVATION_SCHEMA_UNSUPPORTED")
    worker_id = require_worker(value.get("workerId"), "PEER_RECOVERY_WORKER_ID_INVALID")
    role_id = require_worker(value.get("roleId"), "PEER_RECOVERY_ROLE_ID_INVALID")
    state = value.get("state")
    require(state in STATES, "PEER_RECOVERY_STATE_INVALID")
    authority_source = value.get("authoritySource")
    require(authority_source in AUTHORITY_SOURCES, "PEER_RECOVERY_AUTHORITY_SOURCE_INVALID")
    heads = normalize_heads(value.get("authorityHeads"))
    failure = normalize_failure(value.get("failure"))
    failure_source = value.get("failureSource")
    require(failure_source is None or failure_source in FAILURE_SOURCES, "PEER_RECOVERY_FAILURE_SOURCE_INVALID")
    require((failure is None) == (failure_source is None), "PEER_RECOVERY_FAILURE_SOURCE_MISMATCH")
    count = value.get("consecutiveFailureCount")
    require(type(count) is int and count >= 0, "PEER_RECOVERY_FAILURE_COUNT_INVALID")
    if failure is None:
        require(count == 0, "PEER_RECOVERY_FAILURE_COUNT_WITHOUT_FAILURE")
    return {
        "schemaVersion": OBS_SCHEMA,
        "workerId": worker_id,
        "roleId": role_id,
        "state": state,
        "authoritySource": authority_source,
        "authorityHeads": heads,
        "failure": failure,
        "failureSource": failure_source,
        "consecutiveFailureCount": count,
        "lastKnownGood": normalize_last_known_good(value.get("lastKnownGood")),
        "events": normalize_events(value.get("events")),
    }


def normalize_remediation(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    require(isinstance(value, dict), "PEER_RECOVERY_REMEDIATION_INVALID")
    require(set(value) == {"code", "scope", "validated", "authorityBasis"}, "PEER_RECOVERY_REMEDIATION_FIELDS_INVALID")
    scope = value.get("scope")
    basis = value.get("authorityBasis")
    require(scope in REMEDIATION_SCOPES, "PEER_RECOVERY_REMEDIATION_SCOPE_INVALID")
    require(type(value.get("validated")) is bool, "PEER_RECOVERY_REMEDIATION_VALIDATED_INVALID")
    require(basis in AUTHORITY_BASES, "PEER_RECOVERY_REMEDIATION_AUTHORITY_BASIS_INVALID")
    if scope == "shared-gitops":
        require(basis == "canonical-policy", "PEER_RECOVERY_SHARED_REPAIR_REQUIRES_CANONICAL_POLICY")
    else:
        require(basis == "none", "PEER_RECOVERY_PEER_RUNTIME_REPAIR_MUST_NOT_CLAIM_GIT_AUTHORITY")
    return {
        "code": require_token(value.get("code"), "PEER_RECOVERY_REMEDIATION_CODE_INVALID"),
        "scope": scope,
        "validated": value["validated"],
        "authorityBasis": basis,
    }


def normalize_reproduction(value: Any, observer_worker_id: str) -> dict[str, Any]:
    require(isinstance(value, dict), "PEER_RECOVERY_REPRODUCTION_INVALID")
    expected = {"schemaVersion", "attempted", "actorWorkerId", "mode", "surface", "outcome", "failure", "sideEffects", "remediation"}
    require(set(value) == expected, "PEER_RECOVERY_REPRODUCTION_FIELDS_INVALID")
    require(value.get("schemaVersion") == REPRO_SCHEMA, "PEER_RECOVERY_REPRODUCTION_SCHEMA_UNSUPPORTED")
    attempted = value.get("attempted")
    require(type(attempted) is bool, "PEER_RECOVERY_REPRODUCTION_ATTEMPTED_INVALID")
    actor = require_worker(value.get("actorWorkerId"), "PEER_RECOVERY_REPRODUCTION_ACTOR_INVALID")
    require(actor == observer_worker_id, "PEER_RECOVERY_REPRODUCTION_ACTOR_MUST_BE_OBSERVER")
    require(value.get("mode") == "read-only", "PEER_RECOVERY_REPRODUCTION_MUST_BE_READ_ONLY")
    require(value.get("sideEffects") is False, "PEER_RECOVERY_REPRODUCTION_SIDE_EFFECTS_FORBIDDEN")
    outcome = value.get("outcome")
    require(outcome in {"PASS", "FAIL", "NOT_ATTEMPTED"}, "PEER_RECOVERY_REPRODUCTION_OUTCOME_INVALID")
    surface = value.get("surface")
    require(surface is None or (isinstance(surface, str) and bool(TOKEN_RE.fullmatch(surface))), "PEER_RECOVERY_REPRODUCTION_SURFACE_INVALID")
    failure = normalize_failure(value.get("failure"))
    if attempted:
        require(outcome in {"PASS", "FAIL"}, "PEER_RECOVERY_REPRODUCTION_ATTEMPTED_OUTCOME_INVALID")
        require(surface is not None, "PEER_RECOVERY_REPRODUCTION_SURFACE_REQUIRED")
    else:
        require(outcome == "NOT_ATTEMPTED", "PEER_RECOVERY_REPRODUCTION_NOT_ATTEMPTED_MISMATCH")
        require(failure is None, "PEER_RECOVERY_REPRODUCTION_FAILURE_WITHOUT_ATTEMPT")
    if outcome == "FAIL":
        require(failure is not None, "PEER_RECOVERY_REPRODUCTION_FAILURE_REQUIRED")
    if outcome != "FAIL":
        require(failure is None, "PEER_RECOVERY_REPRODUCTION_FAILURE_UNEXPECTED")
    return {
        "schemaVersion": REPRO_SCHEMA,
        "attempted": attempted,
        "actorWorkerId": actor,
        "mode": "read-only",
        "surface": surface,
        "outcome": outcome,
        "failure": failure,
        "sideEffects": False,
        "remediation": normalize_remediation(value.get("remediation")),
    }


def normalize_context(value: Any) -> dict[str, Any]:
    require(isinstance(value, dict), "PEER_RECOVERY_CONTEXT_INVALID")
    require(set(value) == {"correlationId", "attemptCount"}, "PEER_RECOVERY_CONTEXT_FIELDS_INVALID")
    correlation = value.get("correlationId")
    require(isinstance(correlation, str) and bool(correlation.strip()), "PEER_RECOVERY_CORRELATION_ID_INVALID")
    count = value.get("attemptCount")
    require(type(count) is int and count >= 0, "PEER_RECOVERY_ATTEMPT_COUNT_INVALID")
    return {"correlationId": correlation.strip(), "attemptCount": count}


def normalize_input(value: Any) -> dict[str, Any]:
    require(isinstance(value, dict), "PEER_RECOVERY_INPUT_INVALID")
    require(set(value) == {"schemaVersion", "roleId", "observer", "peer", "reproduction", "recoveryContext"}, "PEER_RECOVERY_INPUT_FIELDS_INVALID")
    require(value.get("schemaVersion") == INPUT_SCHEMA, "PEER_RECOVERY_INPUT_SCHEMA_UNSUPPORTED")
    role_id = require_worker(value.get("roleId"), "PEER_RECOVERY_ROLE_ID_INVALID")
    observer = normalize_observation(value.get("observer"))
    peer = normalize_observation(value.get("peer"))
    require(observer["roleId"] == role_id and peer["roleId"] == role_id, "PEER_RECOVERY_ROLE_MISMATCH")
    require(observer["workerId"] != peer["workerId"], "PEER_RECOVERY_PEER_MUST_BE_DISTINCT")
    reproduction = normalize_reproduction(value.get("reproduction"), observer["workerId"])
    return {
        "schemaVersion": INPUT_SCHEMA,
        "roleId": role_id,
        "observer": observer,
        "peer": peer,
        "reproduction": reproduction,
        "recoveryContext": normalize_context(value.get("recoveryContext")),
    }


def compare_heads(observer: dict[str, Any], peer: dict[str, Any]) -> tuple[str, bool]:
    if observer["authoritySource"] != "git-observed" or peer["authoritySource"] != "git-observed":
        return "UNVERIFIABLE", False
    observer_heads = observer["authorityHeads"]
    peer_heads = peer["authorityHeads"]
    if any(observer_heads[key] is None or peer_heads[key] is None for key in observer_heads):
        return "UNVERIFIABLE", False
    if observer_heads == peer_heads:
        return "SAME", True
    return "DIFFERENT", False


def build_inspection(raw: dict[str, Any]) -> dict[str, Any]:
    value = normalize_input(raw)
    observer, peer, reproduction = value["observer"], value["peer"], value["reproduction"]
    head_comparison, comparable = compare_heads(observer, peer)
    peer_fp = failure_fingerprint(peer["failure"])
    repro_fp = failure_fingerprint(reproduction["failure"])

    if peer["state"] == "HEALTHY" and peer["failure"] is None:
        classification = "PEER_HEALTHY"
    elif peer["state"] in {"SILENT_UNKNOWN", "PAUSING_UNAVAILABLE"} and peer["failure"] is None:
        classification = "PEER_UNAVAILABLE"
    elif head_comparison == "UNVERIFIABLE":
        classification = "AUTHORITY_UNVERIFIABLE"
    elif head_comparison == "DIFFERENT":
        classification = "AUTHORITY_DIVERGENCE"
    elif peer["failure"] is None:
        classification = "PEER_SIGNAL_ONLY"
    elif value["recoveryContext"]["attemptCount"] >= 1:
        classification = "RECOVERY_LOOP_RISK"
    elif not reproduction["attempted"]:
        classification = "PEER_FAILURE_UNREPRODUCED"
    elif reproduction["surface"] != peer["failure"]["surface"]:
        classification = "REPRODUCTION_SURFACE_MISMATCH"
    elif reproduction["outcome"] == "PASS":
        classification = "PEER_RUNTIME_ASYMMETRY"
    elif reproduction["outcome"] == "FAIL" and repro_fp == peer_fp:
        classification = "SHARED_SURFACE_FAILURE"
    else:
        classification = "NONMATCHING_REPRODUCTION_FAILURE"

    body = {
        "schemaVersion": INSPECTION_SCHEMA,
        "roleId": value["roleId"],
        "observerWorkerId": observer["workerId"],
        "peerWorkerId": peer["workerId"],
        "peerState": peer["state"],
        "headComparison": head_comparison,
        "authoritiesComparable": comparable,
        "failureFingerprint": peer_fp,
        "reproductionFailureFingerprint": repro_fp,
        "classification": classification,
        "consecutiveFailureCount": peer["consecutiveFailureCount"],
        "eventIds": sorted({event["eventId"] for event in peer["events"]}),
        "recoveryCorrelationId": value["recoveryContext"]["correlationId"],
        "recoveryAttemptCount": value["recoveryContext"]["attemptCount"],
        "readOnly": True,
        "semanticAuthority": False,
        "taskControlAuthority": False,
        "identityTakeoverAuthority": False,
        "leaseTakeoverAuthority": False,
        "continuationTakeoverAuthority": False,
    }
    return {**body, "inspectionHash": stable_hash(body), "_normalizedInput": value}


def build_plan(raw: dict[str, Any]) -> dict[str, Any]:
    inspection = build_inspection(raw)
    value = inspection.pop("_normalizedInput")
    classification = inspection["classification"]
    peer = value["peer"]
    reproduction = value["reproduction"]
    remediation = reproduction["remediation"]

    action = "NEEDS_HUMAN"
    signal = "NEEDS_HUMAN"
    target_worker: str | None = None
    executor = "none"
    reason = classification

    if classification == "PEER_HEALTHY":
        action, signal = "NOOP", "NONE"
    elif classification == "PEER_UNAVAILABLE":
        action, signal = "OBSERVE", "NONE"
    elif classification in {"AUTHORITY_UNVERIFIABLE", "AUTHORITY_DIVERGENCE"}:
        action, signal = "QUARANTINE", "NEEDS_HUMAN"
    elif classification in {"PEER_SIGNAL_ONLY", "PEER_FAILURE_UNREPRODUCED", "REPRODUCTION_SURFACE_MISMATCH"}:
        action, signal = "REPRODUCE", "NONE"
        target_worker = value["observer"]["workerId"]
        executor = "observer"
    elif classification == "PEER_RUNTIME_ASYMMETRY":
        action = "REQUEST_RETRY"
        target_worker = peer["workerId"]
        executor = "peer"
        if remediation is not None and remediation["scope"] == "peer-runtime" and remediation["validated"]:
            signal = "RECOVERY_READY"
            reason = remediation["code"]
        else:
            signal = "RETRY_RECOMMENDED"
    elif classification == "SHARED_SURFACE_FAILURE":
        if remediation is not None and remediation["scope"] == "shared-gitops" and remediation["validated"] and remediation["authorityBasis"] == "canonical-policy":
            action, signal = "REPAIR_SHARED", "RECOVERY_READY"
            executor = "observer"
            reason = remediation["code"]
        else:
            action, signal = "NEEDS_HUMAN", "NEEDS_HUMAN"
    elif classification in {"NONMATCHING_REPRODUCTION_FAILURE", "RECOVERY_LOOP_RISK"}:
        action, signal = "NEEDS_HUMAN", "NEEDS_HUMAN"

    require(action in ACTIONS and signal in SIGNALS, "PEER_RECOVERY_INTERNAL_PLAN_INVALID")
    recovery_key = stable_hash({
        "roleId": value["roleId"],
        "peerWorkerId": peer["workerId"],
        "failureFingerprint": inspection["failureFingerprint"],
        "authorityHeads": peer["authorityHeads"] if peer["authoritySource"] == "git-observed" else None,
    })
    body = {
        "schemaVersion": PLAN_SCHEMA,
        "inspectionHash": inspection["inspectionHash"],
        "classification": classification,
        "action": action,
        "signal": signal,
        "reasonCode": reason,
        "targetWorkerId": target_worker,
        "recommendedExecutor": executor,
        "recoveryKey": recovery_key,
        "recoveryCorrelationId": value["recoveryContext"]["correlationId"],
        "requiredPreconditions": {
            "sameAuthorityHeads": action in {"REPRODUCE", "REPAIR_SHARED", "REQUEST_RETRY"},
            "revalidateBeforeExecution": action in {"REPAIR_SHARED", "REQUEST_RETRY"},
            "readOnlyReproduction": action == "REPRODUCE",
        },
        "boundaries": {
            "taskControlAllowed": False,
            "identityTakeoverAllowed": False,
            "leaseTakeoverAllowed": False,
            "continuationTakeoverAllowed": False,
            "emailIsAuthority": False,
        },
        "readOnly": True,
        "gitSideEffects": False,
        "transportSideEffects": False,
        "semanticAuthority": False,
    }
    return {"inspection": inspection, "plan": {**body, "planHash": stable_hash(body)}}


def load_json(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("PEER_RECOVERY_INPUT_INVALID") from exc
    require(isinstance(value, dict), "PEER_RECOVERY_INPUT_INVALID")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="peer-recovery", description="Deterministic read-only peer recovery planner")
    parser.add_argument("--input", required=True)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        payload = build_plan(load_json(args.input))
        print(json.dumps(payload, indent=2 if args.as_json else None, ensure_ascii=False))
        return 0
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
