#!/usr/bin/env python3
"""Compose and validate a read-only factual inspection of MobiliPresenter."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import agent, project_sensors

SCHEMA_VERSION = "ProjectMachineInspection 0.1"
REPOSITORY = "EAKerber/MobiliPresenter"
SCOPES = {"local", "base", "live"}
STATUSES = {"PASS", "UNKNOWN", "FAIL"}
ERROR_EXIT = 2
UNKNOWN_EXIT = 1


def stable_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sensor_status(value: Any) -> str:
    if not isinstance(value, dict):
        return "FAIL"
    status = str(value.get("status") or "UNKNOWN").upper()
    return status if status in STATUSES else "FAIL"


def aggregate_trust(sensors: dict[str, dict[str, Any]]) -> dict[str, Any]:
    failed: list[str] = []
    unknown: list[str] = []
    for name, value in sensors.items():
        if value.get("required") is not True:
            continue
        status = _sensor_status(value)
        if status == "FAIL":
            failed.append(name)
        elif status == "UNKNOWN":
            unknown.append(name)
    status = "FAIL" if failed else ("UNKNOWN" if unknown else "PASS")
    return {
        "status": status,
        "ok": status != "FAIL",
        "complete": status == "PASS",
        "failedSensors": sorted(failed),
        "unknownSensors": sorted(unknown),
    }


def source_heads(sensors: dict[str, dict[str, Any]]) -> dict[str, Any]:
    git_data = sensors.get("git", {}).get("data") or {}
    observed = git_data.get("observed") if isinstance(git_data, dict) else {}
    control = sensors.get("control", {}).get("data") or {}
    coordination = sensors.get("coordination", {}).get("data") or {}
    continuations = sensors.get("continuations", {}).get("data") or {}
    return {
        "inspection": {
            "branch": observed.get("branch") if isinstance(observed, dict) else None,
            "sha": observed.get("head") if isinstance(observed, dict) else None,
        },
        "control": {
            "branch": control.get("branch") if isinstance(control, dict) else None,
            "sha": control.get("sha") if isinstance(control, dict) else None,
        },
        "coordination": {
            "branch": coordination.get("authorityBranch") if isinstance(coordination, dict) else None,
            "sha": coordination.get("authorityHead") if isinstance(coordination, dict) else None,
        },
        "continuation": {
            "branch": continuations.get("authorityBranch") if isinstance(continuations, dict) else None,
            "sha": continuations.get("authorityHead") if isinstance(continuations, dict) else None,
        },
    }


def observations(sensors: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    continuation_data = sensors.get("continuations", {}).get("data") or {}
    items = continuation_data.get("items", []) if isinstance(continuation_data, dict) else []
    terminal = [item for item in items if isinstance(item, dict) and item.get("status") == "DONE"]
    if terminal:
        out.append({
            "severity": "INFO",
            "code": "TERMINAL_CONTINUATION_RESIDUE",
            "subject": "coordination/continuations",
            "count": len(terminal),
            "ids": sorted(str(item.get("id")) for item in terminal),
        })

    pr_data = sensors.get("pullRequests", {}).get("data") or {}
    prs = pr_data.get("items", []) if isinstance(pr_data, dict) else []
    unclassified = [item for item in prs if isinstance(item, dict) and item.get("classification") == "unclassified"]
    if unclassified:
        out.append({
            "severity": "WARN",
            "code": "UNCLASSIFIED_OPEN_PR",
            "subject": "github",
            "count": len(unclassified),
            "prNumbers": sorted(int(item["number"]) for item in unclassified if isinstance(item.get("number"), int)),
        })
    return out


def project_summary(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "stateHash": stable_hash(state),
        "phase": state["development"]["phase"],
        "checkpoint": state["development"]["checkpoint"],
        "nextTransition": state["development"]["nextTransition"],
        "activeDevelopmentBranch": state["git"].get("activeDevelopmentBranch"),
        "developmentPrNumber": state["development"].get("prNumber"),
        "blockers": state["development"].get("blockers") or [],
    }


def build_inspection(state: dict[str, Any], sensors: dict[str, dict[str, Any]], *, scope: str) -> dict[str, Any]:
    if scope not in SCOPES:
        raise RuntimeError("PROJECT_MACHINE_SCOPE_INVALID")
    body = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": state["project"]["repository"],
        "scope": scope,
        "sourceHeads": source_heads(sensors),
        "project": project_summary(state),
        "sensors": sensors,
        "trust": aggregate_trust(sensors),
        "observations": observations(sensors),
        "readOnly": True,
        "semanticAuthority": False,
    }
    return {**body, "inspectionHash": stable_hash(body)}


def _load_state() -> dict[str, Any]:
    state = agent.load_json(agent.STATE_PATH)
    errors = agent.validate_state_shape(state)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    return state


def inspect_local() -> dict[str, Any]:
    state = _load_state()
    sensors = project_sensors.observe_local_core(state)
    sensors["control"] = project_sensors.observe_control_head(state, live=False)
    sensors["capabilities"] = project_sensors.observe_capabilities()
    sensors["pullRequests"] = project_sensors.observe_pull_requests(state, live=False)
    sensors["coordination"] = project_sensors.observe_coordination(live=False)
    sensors["continuations"] = project_sensors.observe_continuations_local()
    sensors["development"] = project_sensors.observe_development(state, sensors["pullRequests"], live=False)
    return build_inspection(state, sensors, scope="local")


def inspect_base() -> dict[str, Any]:
    """Remote base inspection that deliberately does not depend on live continuations."""
    state = _load_state()
    sensors = project_sensors.observe_local_core(state)
    sensors["control"] = project_sensors.observe_control_head(state, live=True)
    sensors["capabilities"] = project_sensors.observe_capabilities()
    sensors["pullRequests"] = project_sensors.observe_pull_requests(state, live=True)
    sensors["coordination"] = project_sensors.observe_coordination(live=True)
    sensors["continuations"] = project_sensors.observe_continuations_local()
    sensors["development"] = project_sensors.observe_development(state, sensors["pullRequests"], live=True)
    return build_inspection(state, sensors, scope="base")


def inspect_live() -> dict[str, Any]:
    state = _load_state()
    sensors = project_sensors.observe_local_core(state)
    sensors["control"] = project_sensors.observe_control_head(state, live=True)
    sensors["capabilities"] = project_sensors.observe_capabilities()
    sensors["pullRequests"] = project_sensors.observe_pull_requests(state, live=True)
    sensors["coordination"] = project_sensors.observe_coordination(live=True)
    sensors["continuations"] = project_sensors.observe_continuations_live()
    sensors["development"] = project_sensors.observe_development(state, sensors["pullRequests"], live=True)
    return build_inspection(state, sensors, scope="live")


def _require_sha_or_none(value: Any, code: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise RuntimeError(code)


def validate_inspection(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("PROJECT_MACHINE_INPUT_INVALID")
    if value.get("schemaVersion") != SCHEMA_VERSION:
        raise RuntimeError("PROJECT_MACHINE_SCHEMA_UNSUPPORTED")
    if value.get("repository") != REPOSITORY:
        raise RuntimeError("PROJECT_MACHINE_REPOSITORY_MISMATCH")
    if value.get("scope") not in SCOPES:
        raise RuntimeError("PROJECT_MACHINE_SCOPE_INVALID")
    if value.get("readOnly") is not True:
        raise RuntimeError("PROJECT_MACHINE_NOT_READ_ONLY")
    if value.get("semanticAuthority") is not False:
        raise RuntimeError("PROJECT_MACHINE_SEMANTIC_AUTHORITY_INVALID")

    sensors = value.get("sensors")
    if not isinstance(sensors, dict) or not sensors:
        raise RuntimeError("PROJECT_MACHINE_SENSORS_INVALID")
    for name, item in sensors.items():
        if not isinstance(name, str) or not isinstance(item, dict):
            raise RuntimeError("PROJECT_MACHINE_SENSOR_INVALID")
        raw_status = str(item.get("status") or "").upper()
        if raw_status not in STATUSES:
            raise RuntimeError("PROJECT_MACHINE_SENSOR_STATUS_INVALID")
        if not isinstance(item.get("required"), bool):
            raise RuntimeError("PROJECT_MACHINE_SENSOR_REQUIRED_INVALID")

    trust = value.get("trust")
    expected_trust = aggregate_trust(sensors)
    if trust != expected_trust:
        raise RuntimeError("PROJECT_MACHINE_TRUST_MISMATCH")

    heads = value.get("sourceHeads")
    if not isinstance(heads, dict):
        raise RuntimeError("PROJECT_MACHINE_SOURCE_HEADS_INVALID")
    if heads != source_heads(sensors):
        raise RuntimeError("PROJECT_MACHINE_SOURCE_HEADS_MISMATCH")
    for name in ("inspection", "control", "coordination", "continuation"):
        head = heads.get(name)
        if not isinstance(head, dict):
            raise RuntimeError("PROJECT_MACHINE_SOURCE_HEAD_INVALID")
        _require_sha_or_none(head.get("sha"), f"PROJECT_MACHINE_{name.upper()}_HEAD_INVALID")

    if value.get("observations") != observations(sensors):
        raise RuntimeError("PROJECT_MACHINE_OBSERVATIONS_MISMATCH")

    supplied_hash = value.get("inspectionHash")
    body = {key: item for key, item in value.items() if key != "inspectionHash"}
    expected_hash = stable_hash(body)
    if not isinstance(supplied_hash, str) or supplied_hash != expected_hash:
        raise RuntimeError("PROJECT_MACHINE_HASH_MISMATCH")

    return {"ok": True, "inspectionHash": supplied_hash, "trust": trust, "scope": value["scope"], "sourceHeads": heads}


def load_json(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("PROJECT_MACHINE_INPUT_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("PROJECT_MACHINE_INPUT_INVALID")
    return value


def _print_human(payload: dict[str, Any]) -> None:
    trust = payload["trust"]
    project = payload["project"]
    print("PROJECT MACHINE INSPECTION")
    print(f"  scope: {payload['scope']}")
    print(f"  trust: {trust['status']}")
    print(f"  phase: {project['phase']}")
    print(f"  checkpoint: {project['checkpoint']}")
    print(f"  next: {project['nextTransition']}")
    print(f"  observations: {len(payload['observations'])}")
    print(f"  inspectionHash: {payload['inspectionHash']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="project-machine")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_parser = sub.add_parser("inspect")
    scope_group = inspect_parser.add_mutually_exclusive_group(required=True)
    scope_group.add_argument("--live", action="store_true")
    scope_group.add_argument("--base", action="store_true")
    scope_group.add_argument("--local", action="store_true")
    inspect_parser.add_argument("--json", action="store_true", dest="as_json")
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("path")
    validate_parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            result = validate_inspection(load_json(args.path))
            print(json.dumps(result, indent=2 if args.as_json else None, ensure_ascii=False))
            return 0
        if args.live:
            payload = inspect_live()
        elif args.base:
            payload = inspect_base()
        else:
            payload = inspect_local()
        if args.as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            _print_human(payload)
        status = payload["trust"]["status"]
        if status == "PASS":
            return 0
        if status == "UNKNOWN":
            return UNKNOWN_EXIT
        return ERROR_EXIT
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False) if getattr(args, "as_json", False) else f"BLOCKED\n{exc}")
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
