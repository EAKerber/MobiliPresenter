#!/usr/bin/env python3
"""Pure Agent Bus envelope generation for experimental peer recovery.

No Gmail/network/task/Git/lease/continuation side effects are performed here.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any
from tools import peer_recovery
from tools.canonical import stable_hash

HEALTH_SCHEMA = "WorkerHealthEvent 0.1"
RECOVERY_SCHEMA = "PeerRecoveryEvent 0.1"
ERROR_EXIT = 2


def _load(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("PEER_RECOVERY_BUS_INPUT_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("PEER_RECOVERY_BUS_INPUT_INVALID")
    return value


def _failure_band(observation: dict[str, Any]) -> int:
    if observation["failure"] is None:
        return 0
    return min(observation["consecutiveFailureCount"], 3)


def _transition_key(observation: dict[str, Any]) -> str:
    core = {
        "workerId": observation["workerId"],
        "roleId": observation["roleId"],
        "state": observation["state"],
        "failureFingerprint": peer_recovery.failure_fingerprint(observation["failure"]),
        "failureBand": _failure_band(observation),
    }
    return stable_hash(core)


def validate_health_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("WORKER_HEALTH_EVENT_INVALID")
    expected = {
        "schemaVersion", "type", "event_id", "source_worker", "worker_id", "role_id", "state",
        "failure", "failure_fingerprint", "observed_authority_heads", "authority_claim",
        "consecutive_failure_count", "last_known_good", "transition_key", "previous_event_id",
    }
    if set(value) != expected or value.get("schemaVersion") != HEALTH_SCHEMA or value.get("type") != "worker.health":
        raise RuntimeError("WORKER_HEALTH_EVENT_SCHEMA_INVALID")
    if value.get("source_worker") != value.get("worker_id"):
        raise RuntimeError("WORKER_HEALTH_EVENT_SOURCE_MISMATCH")
    if not isinstance(value.get("event_id"), str) or not value["event_id"].startswith("worker.health:"):
        raise RuntimeError("WORKER_HEALTH_EVENT_ID_INVALID")
    if not isinstance(value.get("transition_key"), str) or len(value["transition_key"]) != 64:
        raise RuntimeError("WORKER_HEALTH_EVENT_TRANSITION_INVALID")
    previous = value.get("previous_event_id")
    if previous is not None and (not isinstance(previous, str) or not previous.startswith("worker.health:")):
        raise RuntimeError("WORKER_HEALTH_EVENT_PREVIOUS_INVALID")
    return value


def validate_recovery_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("PEER_RECOVERY_EVENT_INVALID")
    expected = {
        "schemaVersion", "type", "event_id", "source_worker", "target_worker", "role_id", "classification",
        "action", "signal", "reason_code", "plan_hash", "inspection_hash", "recovery_key",
        "recovery_correlation_id", "failure_fingerprint", "observed_authority_heads", "recommended_executor",
        "task_control_allowed", "identity_takeover_allowed", "lease_takeover_allowed", "continuation_takeover_allowed",
    }
    if set(value) != expected or value.get("schemaVersion") != RECOVERY_SCHEMA or value.get("type") != "peer.recovery":
        raise RuntimeError("PEER_RECOVERY_EVENT_SCHEMA_INVALID")
    if not isinstance(value.get("event_id"), str) or not value["event_id"].startswith("peer.recovery:"):
        raise RuntimeError("PEER_RECOVERY_EVENT_ID_INVALID")
    for key in ("plan_hash", "inspection_hash", "recovery_key"):
        raw = value.get(key)
        if not isinstance(raw, str) or len(raw) != 64 or any(c not in "0123456789abcdef" for c in raw):
            raise RuntimeError("PEER_RECOVERY_EVENT_HASH_INVALID")
    for key in ("task_control_allowed", "identity_takeover_allowed", "lease_takeover_allowed", "continuation_takeover_allowed"):
        if value.get(key) is not False:
            raise RuntimeError("PEER_RECOVERY_EVENT_TAKEOVER_FORBIDDEN")
    return value


def build_health_event(raw_observation: dict[str, Any], previous_event: dict[str, Any] | None = None) -> dict[str, Any]:
    observation = peer_recovery.normalize_observation(raw_observation)
    previous = validate_health_event(previous_event) if previous_event is not None else None
    if previous is not None:
        if previous["worker_id"] != observation["workerId"] or previous["role_id"] != observation["roleId"]:
            raise RuntimeError("WORKER_HEALTH_EVENT_PREVIOUS_WORKER_MISMATCH")
    transition_key = _transition_key(observation)
    if previous is not None and previous["transition_key"] == transition_key:
        return {
            "schemaVersion": "WorkerHealthEmission 0.1",
            "shouldEmit": False,
            "event": None,
            "existingEventId": previous["event_id"],
            "transitionKey": transition_key,
        }
    previous_id = previous["event_id"] if previous is not None else None
    identity = {
        "workerId": observation["workerId"],
        "roleId": observation["roleId"],
        "transitionKey": transition_key,
        "previousEventId": previous_id,
    }
    event_id = f"worker.health:{observation['workerId']}:{stable_hash(identity)[:16]}"
    event = {
        "schemaVersion": HEALTH_SCHEMA,
        "type": "worker.health",
        "event_id": event_id,
        "source_worker": observation["workerId"],
        "worker_id": observation["workerId"],
        "role_id": observation["roleId"],
        "state": observation["state"],
        "failure": observation["failure"],
        "failure_fingerprint": peer_recovery.failure_fingerprint(observation["failure"]),
        "observed_authority_heads": observation["authorityHeads"],
        "authority_claim": observation["authoritySource"],
        "consecutive_failure_count": observation["consecutiveFailureCount"],
        "last_known_good": observation["lastKnownGood"],
        "transition_key": transition_key,
        "previous_event_id": previous_id,
    }
    validate_health_event(event)
    return {
        "schemaVersion": "WorkerHealthEmission 0.1",
        "shouldEmit": True,
        "event": event,
        "existingEventId": None,
        "transitionKey": transition_key,
    }


def build_recovery_event(raw_input: dict[str, Any]) -> dict[str, Any]:
    normalized = peer_recovery.normalize_input(raw_input)
    bundle = peer_recovery.build_plan(raw_input)
    plan = bundle["plan"]
    inspection = bundle["inspection"]
    if plan["signal"] == "NONE":
        return {"schemaVersion": "PeerRecoveryEmission 0.1", "shouldEmit": False, "event": None, "plan": plan}
    identity = {
        "sourceWorker": inspection["observerWorkerId"],
        "targetWorker": plan["targetWorkerId"],
        "planHash": plan["planHash"],
        "recoveryKey": plan["recoveryKey"],
    }
    event_id = f"peer.recovery:{inspection['observerWorkerId']}:{stable_hash(identity)[:16]}"
    event = {
        "schemaVersion": RECOVERY_SCHEMA,
        "type": "peer.recovery",
        "event_id": event_id,
        "source_worker": inspection["observerWorkerId"],
        "target_worker": plan["targetWorkerId"],
        "role_id": normalized["roleId"],
        "classification": plan["classification"],
        "action": plan["action"],
        "signal": plan["signal"],
        "reason_code": plan["reasonCode"],
        "plan_hash": plan["planHash"],
        "inspection_hash": plan["inspectionHash"],
        "recovery_key": plan["recoveryKey"],
        "recovery_correlation_id": plan["recoveryCorrelationId"],
        "failure_fingerprint": inspection["failureFingerprint"],
        "observed_authority_heads": normalized["peer"]["authorityHeads"],
        "recommended_executor": plan["recommendedExecutor"],
        "task_control_allowed": False,
        "identity_takeover_allowed": False,
        "lease_takeover_allowed": False,
        "continuation_takeover_allowed": False,
    }
    validate_recovery_event(event)
    return {"schemaVersion": "PeerRecoveryEmission 0.1", "shouldEmit": True, "event": event, "plan": plan}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="peer-recovery-bus")
    sub = parser.add_subparsers(dest="command", required=True)
    health = sub.add_parser("health")
    health.add_argument("--observation", required=True)
    health.add_argument("--previous")
    health.add_argument("--json", action="store_true", dest="as_json")
    recovery = sub.add_parser("recovery")
    recovery.add_argument("--input", required=True)
    recovery.add_argument("--json", action="store_true", dest="as_json")
    validate_health = sub.add_parser("validate-health")
    validate_health.add_argument("--input", required=True)
    validate_health.add_argument("--json", action="store_true", dest="as_json")
    validate_recovery = sub.add_parser("validate-recovery")
    validate_recovery.add_argument("--input", required=True)
    validate_recovery.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        if args.command == "health":
            payload = build_health_event(_load(args.observation), _load(args.previous) if args.previous else None)
        elif args.command == "recovery":
            payload = build_recovery_event(_load(args.input))
        elif args.command == "validate-health":
            payload = {"ok": True, "event": validate_health_event(_load(args.input))}
        else:
            payload = {"ok": True, "event": validate_recovery_event(_load(args.input))}
        print(json.dumps(payload, indent=2 if args.as_json else None, ensure_ascii=False))
        return 0
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
