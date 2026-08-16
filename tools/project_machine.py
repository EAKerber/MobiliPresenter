#!/usr/bin/env python3
"""Compose and validate a read-only factual inspection of MobiliPresenter."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import agent, project_coherence, project_sensors
from tools.canonical import stable_hash
from tools.semantics.observation import ObservationStatus

SCHEMA_VERSION = "ProjectMachineInspection 0.2"
REPOSITORY = "EAKerber/MobiliPresenter"
SCOPES = {"local", "base", "live"}
ERROR_EXIT = 2
UNKNOWN_EXIT = 1


def _sensor_status(value: Any) -> str:
    if not isinstance(value, dict):
        return ObservationStatus.FAIL.value
    status = str(value.get("status") or ObservationStatus.UNKNOWN.value).upper()
    try:
        return ObservationStatus.parse(status).value
    except RuntimeError:
        return ObservationStatus.FAIL.value


def aggregate_trust(sensors: dict[str, dict[str, Any]]) -> dict[str, Any]:
    failed: list[str] = []
    unknown: list[str] = []
    for name, value in sensors.items():
        if value.get("required") is not True:
            continue
        status = _sensor_status(value)
        if status == ObservationStatus.FAIL.value:
            failed.append(name)
        elif status == ObservationStatus.UNKNOWN.value:
            unknown.append(name)
    status = ObservationStatus.FAIL.value if failed else (ObservationStatus.UNKNOWN.value if unknown else ObservationStatus.PASS.value)
    return {
        "status": status,
        "ok": status != ObservationStatus.FAIL.value,
        "complete": status == ObservationStatus.PASS.value,
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
        "inspection": {"branch": observed.get("branch") if isinstance(observed, dict) else None, "sha": observed.get("head") if isinstance(observed, dict) else None},
        "control": {"branch": control.get("branch") if isinstance(control, dict) else None, "sha": control.get("sha") if isinstance(control, dict) else None},
        "coordination": {"branch": coordination.get("authorityBranch") if isinstance(coordination, dict) else None, "sha": coordination.get("authorityHead") if isinstance(coordination, dict) else None},
        "continuation": {"branch": continuations.get("authorityBranch") if isinstance(continuations, dict) else None, "sha": continuations.get("authorityHead") if isinstance(continuations, dict) else None},
    }


def observations(sensors: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    continuation_data = sensors.get("continuations", {}).get("data") or {}
    items = continuation_data.get("items", []) if isinstance(continuation_data, dict) else []
    terminal = [item for item in items if isinstance(item, dict) and item.get("status") == "DONE"]
    if terminal:
        out.append({"severity": "INFO", "code": "TERMINAL_CONTINUATION_RESIDUE", "subject": "coordination/continuations", "count": len(terminal), "ids": sorted(str(item.get("id")) for item in terminal)})
    return out


def project_summary(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "stateHash": stable_hash(state),
        "controlBranch": state["git"]["controlBranch"],
        "preserveBranches": sorted(state["git"].get("preserveBranches") or []),
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
    project = project_summary(state)
    body = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": state["project"]["repository"],
        "scope": scope,
        "sourceHeads": source_heads(sensors),
        "project": project,
        "sensors": sensors,
        "authorities": project_coherence.derive_authorities(sensors),
        "trust": aggregate_trust(sensors),
        "coherence": project_coherence.evaluate_coherence(project, sensors, scope=scope),
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


def _common_sensors(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sensors = project_sensors.observe_local_core(state)
    sensors["capabilities"] = project_sensors.observe_capabilities()
    return sensors


def inspect_local() -> dict[str, Any]:
    state = _load_state(); sensors = _common_sensors(state)
    sensors["control"] = project_sensors.observe_control_head(state, live=False)
    sensors["pullRequests"] = project_sensors.observe_pull_requests(state, live=False)
    sensors["coordination"] = project_sensors.observe_coordination(live=False)
    sensors["continuations"] = project_sensors.observe_continuations_local()
    return build_inspection(state, sensors, scope="local")


def inspect_base() -> dict[str, Any]:
    state = _load_state(); sensors = _common_sensors(state)
    sensors["control"] = project_sensors.observe_control_head(state, live=True)
    sensors["pullRequests"] = project_sensors.observe_pull_requests(state, live=True)
    sensors["coordination"] = project_sensors.observe_coordination(live=True)
    sensors["continuations"] = project_sensors.observe_continuations_local()
    return build_inspection(state, sensors, scope="base")


def inspect_live() -> dict[str, Any]:
    state = _load_state(); sensors = _common_sensors(state)
    sensors["control"] = project_sensors.observe_control_head(state, live=True)
    sensors["pullRequests"] = project_sensors.observe_pull_requests(state, live=True)
    sensors["coordination"] = project_sensors.observe_coordination(live=True)
    sensors["continuations"] = project_sensors.observe_continuations_live()
    return build_inspection(state, sensors, scope="live")


def _require_sha_or_none(value: Any, code: str) -> None:
    if value is None: return
    if not isinstance(value, str) or len(value) != 40 or any(char not in "0123456789abcdef" for char in value): raise RuntimeError(code)


def validate_inspection(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict): raise RuntimeError("PROJECT_MACHINE_INPUT_INVALID")
    if value.get("schemaVersion") != SCHEMA_VERSION: raise RuntimeError("PROJECT_MACHINE_SCHEMA_UNSUPPORTED")
    if value.get("repository") != REPOSITORY: raise RuntimeError("PROJECT_MACHINE_REPOSITORY_MISMATCH")
    if value.get("scope") not in SCOPES: raise RuntimeError("PROJECT_MACHINE_SCOPE_INVALID")
    if value.get("readOnly") is not True: raise RuntimeError("PROJECT_MACHINE_NOT_READ_ONLY")
    if value.get("semanticAuthority") is not False: raise RuntimeError("PROJECT_MACHINE_SEMANTIC_AUTHORITY_INVALID")
    project = value.get("project")
    if not isinstance(project, dict): raise RuntimeError("PROJECT_MACHINE_PROJECT_INVALID")
    if not isinstance(project.get("controlBranch"), str): raise RuntimeError("PROJECT_MACHINE_CONTROL_BRANCH_INVALID")
    if not isinstance(project.get("preserveBranches"), list): raise RuntimeError("PROJECT_MACHINE_PRESERVE_BRANCHES_INVALID")
    sensors = value.get("sensors")
    if not isinstance(sensors, dict) or not sensors: raise RuntimeError("PROJECT_MACHINE_SENSORS_INVALID")
    for name, item in sensors.items():
        if not isinstance(name, str) or not isinstance(item, dict): raise RuntimeError("PROJECT_MACHINE_SENSOR_INVALID")
        try: ObservationStatus.parse(str(item.get("status") or "").upper())
        except RuntimeError as exc: raise RuntimeError("PROJECT_MACHINE_SENSOR_STATUS_INVALID") from exc
        if not isinstance(item.get("required"), bool): raise RuntimeError("PROJECT_MACHINE_SENSOR_REQUIRED_INVALID")
    expected_authorities = project_coherence.derive_authorities(sensors)
    if value.get("authorities") != expected_authorities: raise RuntimeError("PROJECT_MACHINE_AUTHORITIES_MISMATCH")
    trust = value.get("trust"); expected_trust = aggregate_trust(sensors)
    if trust != expected_trust: raise RuntimeError("PROJECT_MACHINE_TRUST_MISMATCH")
    expected_coherence = project_coherence.evaluate_coherence(project, sensors, scope=value["scope"])
    if value.get("coherence") != expected_coherence: raise RuntimeError("PROJECT_MACHINE_COHERENCE_MISMATCH")
    heads = value.get("sourceHeads")
    if not isinstance(heads, dict): raise RuntimeError("PROJECT_MACHINE_SOURCE_HEADS_INVALID")
    if heads != source_heads(sensors): raise RuntimeError("PROJECT_MACHINE_SOURCE_HEADS_MISMATCH")
    for name in ("inspection", "control", "coordination", "continuation"):
        head = heads.get(name)
        if not isinstance(head, dict): raise RuntimeError("PROJECT_MACHINE_SOURCE_HEAD_INVALID")
        _require_sha_or_none(head.get("sha"), f"PROJECT_MACHINE_{name.upper()}_HEAD_INVALID")
    if value.get("observations") != observations(sensors): raise RuntimeError("PROJECT_MACHINE_OBSERVATIONS_MISMATCH")
    supplied_hash = value.get("inspectionHash"); body = {key: item for key, item in value.items() if key != "inspectionHash"}; expected_hash = stable_hash(body)
    if not isinstance(supplied_hash, str) or supplied_hash != expected_hash: raise RuntimeError("PROJECT_MACHINE_HASH_MISMATCH")
    return {"ok": True, "inspectionHash": supplied_hash, "trust": trust, "coherence": value["coherence"], "scope": value["scope"], "sourceHeads": heads}


def load_json(path: str) -> dict[str, Any]:
    try: value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise RuntimeError("PROJECT_MACHINE_INPUT_INVALID") from exc
    if not isinstance(value, dict): raise RuntimeError("PROJECT_MACHINE_INPUT_INVALID")
    return value


def _print_human(payload: dict[str, Any]) -> None:
    trust = payload["trust"]; coherence = payload["coherence"]; project = payload["project"]
    print("PROJECT MACHINE INSPECTION"); print(f"  scope: {payload['scope']}"); print(f"  trust: {trust['status']}"); print(f"  coherence: {coherence['status']}"); print(f"  phase: {project['phase']}"); print(f"  checkpoint: {project['checkpoint']}"); print(f"  next: {project['nextTransition']}"); print(f"  authorities: {len(payload['authorities'])}"); print(f"  observations: {len(payload['observations'])}"); print(f"  inspectionHash: {payload['inspectionHash']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="project-machine"); sub = parser.add_subparsers(dest="command", required=True)
    inspect_parser = sub.add_parser("inspect"); scope_group = inspect_parser.add_mutually_exclusive_group(required=True); scope_group.add_argument("--live", action="store_true"); scope_group.add_argument("--base", action="store_true"); scope_group.add_argument("--local", action="store_true"); inspect_parser.add_argument("--json", action="store_true", dest="as_json")
    validate_parser = sub.add_parser("validate"); validate_parser.add_argument("path"); validate_parser.add_argument("--json", action="store_true", dest="as_json"); args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            result = validate_inspection(load_json(args.path)); print(json.dumps(result, indent=2 if args.as_json else None, ensure_ascii=False)); return 0
        payload = inspect_live() if args.live else (inspect_base() if args.base else inspect_local())
        print(json.dumps(payload, indent=2, ensure_ascii=False) if args.as_json else "") if args.as_json else _print_human(payload)
        status = payload["trust"]["status"]; coherence_status = payload["coherence"]["status"]
        if status == ObservationStatus.FAIL.value or coherence_status == ObservationStatus.FAIL.value: return ERROR_EXIT
        if status == ObservationStatus.UNKNOWN.value or coherence_status == ObservationStatus.UNKNOWN.value: return UNKNOWN_EXIT
        return 0
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False) if getattr(args, "as_json", False) else f"BLOCKED\n{exc}"); return ERROR_EXIT


if __name__ == "__main__": raise SystemExit(main())
