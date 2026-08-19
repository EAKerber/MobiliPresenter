#!/usr/bin/env python3
"""Deterministic recurring operational routine inspection.

Routines are read-only obligations evaluated from an already materialized
ProjectMachineInspection. They do not reobserve authorities, authorize mutation,
or emit OperationalAction. Maintenance/Scheduler adoption is intentionally
separate from this shadow kernel.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import project_machine
from tools.canonical import stable_hash
from tools.semantics.observation import ObservationStatus

SCHEMA_VERSION = "RoutineInspection 0.1"
REPOSITORY = "EAKerber/MobiliPresenter"
ERROR_EXIT = 2
UNKNOWN_EXIT = 1
RESULT_FIELDS = {"id", "status", "applicable", "findings", "evidence"}
FINDING_FIELDS = {"code", "subject", "detail", "supervisorEligible"}


@dataclass(frozen=True)
class RoutineDefinition:
    id: str
    required: bool
    input_kind: str
    evaluator: Callable[[dict[str, Any]], dict[str, Any]]


def _finding(code: str, subject: str, detail: str, *, supervisor_eligible: bool) -> dict[str, Any]:
    return {
        "code": str(code),
        "subject": str(subject),
        "detail": str(detail),
        "supervisorEligible": bool(supervisor_eligible),
    }


def _result(
    routine_id: str,
    *,
    status: str,
    applicable: bool,
    findings: list[dict[str, Any]],
    machine_hash: str,
) -> dict[str, Any]:
    try:
        normalized = ObservationStatus.parse(str(status).upper()).value
    except RuntimeError as exc:
        raise RuntimeError("ROUTINE_STATUS_INVALID") from exc
    normalized_findings = sorted(
        [dict(item) for item in findings],
        key=lambda item: (str(item.get("subject") or ""), str(item.get("code") or ""), str(item.get("detail") or "")),
    )
    return {
        "id": routine_id,
        "status": normalized,
        "applicable": bool(applicable),
        "findings": normalized_findings,
        "evidence": {"projectMachineInspectionHash": machine_hash},
    }


def _capability_items(machine: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    sensors = machine.get("sensors")
    if not isinstance(sensors, dict):
        raise RuntimeError("ROUTINE_PROJECT_MACHINE_SENSORS_INVALID")
    sensor = sensors.get("capabilities")
    if not isinstance(sensor, dict):
        raise RuntimeError("ROUTINE_CAPABILITY_SENSOR_MISSING")
    try:
        status = ObservationStatus.parse(str(sensor.get("status") or "").upper()).value
    except RuntimeError as exc:
        raise RuntimeError("ROUTINE_CAPABILITY_SENSOR_STATUS_INVALID") from exc
    data = sensor.get("data")
    if not isinstance(data, dict):
        if status == ObservationStatus.PASS.value:
            raise RuntimeError("ROUTINE_CAPABILITY_SENSOR_DATA_INVALID")
        return status, []
    items = data.get("items")
    if not isinstance(items, list):
        if status == ObservationStatus.PASS.value:
            raise RuntimeError("ROUTINE_CAPABILITY_ITEMS_INVALID")
        return status, []
    if any(not isinstance(item, dict) for item in items):
        raise RuntimeError("ROUTINE_CAPABILITY_ITEM_INVALID")
    return status, items


def evaluate_capability_deathcircle(machine: dict[str, Any]) -> dict[str, Any]:
    """Evaluate capability review obligations without mutating capability state."""
    project_machine.validate_inspection(machine)
    machine_hash = machine["inspectionHash"]
    sensor_status, items = _capability_items(machine)
    if sensor_status != ObservationStatus.PASS.value:
        return _result(
            "capability-deathcircle",
            status=sensor_status,
            applicable=True,
            findings=[],
            machine_hash=machine_hash,
        )

    experimental = sorted(
        [item for item in items if item.get("policy") == "experimental"],
        key=lambda item: str(item.get("id") or ""),
    )
    findings: list[dict[str, Any]] = []
    for item in experimental:
        capability_id = item.get("id")
        if not isinstance(capability_id, str) or not capability_id:
            raise RuntimeError("ROUTINE_CAPABILITY_ID_INVALID")
        review_action = item.get("reviewAction")
        participation = item.get("supervisorParticipation", "active")
        supervisor_eligible = participation != "isolated"

        if review_action == "TEST_NEXT_GATES":
            detail = f"next Gates: {', '.join(str(value) for value in item.get('nextGates') or [])}"
            code = "CAPABILITY_GATES_DUE"
        elif review_action == "REVIEW_EMPTY_ROUND":
            detail = "re-evaluate the recorded deferral reason"
            code = "CAPABILITY_EMPTY_REVIEW_DUE"
        elif review_action == "REVIEW_EMPTY_LIMIT":
            detail = "formal capability review reached its configured empty-round limit"
            code = "CAPABILITY_EMPTY_LIMIT"
        else:
            raise RuntimeError(f"ROUTINE_CAPABILITY_REVIEW_ACTION_INVALID:{capability_id}:{review_action}")

        findings.append(
            _finding(code, capability_id, detail, supervisor_eligible=supervisor_eligible)
        )

    return _result(
        "capability-deathcircle",
        status=ObservationStatus.PASS.value,
        applicable=bool(experimental),
        findings=findings,
        machine_hash=machine_hash,
    )


ROUTINE_CATALOG = (
    RoutineDefinition(
        id="capability-deathcircle",
        required=True,
        input_kind="ProjectMachineInspection",
        evaluator=evaluate_capability_deathcircle,
    ),
)


def _catalog(catalog: tuple[RoutineDefinition, ...] | list[RoutineDefinition] | None = None) -> tuple[RoutineDefinition, ...]:
    values = tuple(ROUTINE_CATALOG if catalog is None else catalog)
    if any(not isinstance(item, RoutineDefinition) for item in values):
        raise RuntimeError("ROUTINE_DEFINITION_INVALID")
    ids = [item.id for item in values]
    if any(not isinstance(value, str) or not value for value in ids):
        raise RuntimeError("ROUTINE_ID_INVALID")
    if len(ids) != len(set(ids)):
        raise RuntimeError("ROUTINE_ID_DUPLICATE")
    if ids != sorted(ids):
        raise RuntimeError("ROUTINE_CATALOG_NOT_SORTED")
    if any(item.input_kind != "ProjectMachineInspection" for item in values):
        raise RuntimeError("ROUTINE_INPUT_KIND_UNSUPPORTED")
    return values


def coverage_for(
    catalog: tuple[RoutineDefinition, ...] | list[RoutineDefinition],
    results: list[dict[str, Any]],
) -> dict[str, list[str]]:
    definitions = _catalog(catalog)
    required = sorted(item.id for item in definitions if item.required)
    evaluated = sorted(
        {
            str(item.get("id"))
            for item in results
            if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id")
        }
    )
    missing = sorted(set(required) - set(evaluated))
    return {"required": required, "evaluated": evaluated, "missing": missing}


def _validate_finding(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != FINDING_FIELDS:
        raise RuntimeError("ROUTINE_FINDING_FIELDS_INVALID")
    for key in ("code", "subject", "detail"):
        if not isinstance(value.get(key), str) or not value[key]:
            raise RuntimeError("ROUTINE_FINDING_VALUE_INVALID")
    if not isinstance(value.get("supervisorEligible"), bool):
        raise RuntimeError("ROUTINE_FINDING_ELIGIBILITY_INVALID")


def _validate_result(value: Any, *, expected_id: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RESULT_FIELDS:
        raise RuntimeError("ROUTINE_RESULT_FIELDS_INVALID")
    routine_id = value.get("id")
    if not isinstance(routine_id, str) or not routine_id:
        raise RuntimeError("ROUTINE_RESULT_ID_INVALID")
    if expected_id is not None and routine_id != expected_id:
        raise RuntimeError("ROUTINE_RESULT_ID_MISMATCH")
    try:
        ObservationStatus.parse(str(value.get("status") or "").upper())
    except RuntimeError as exc:
        raise RuntimeError("ROUTINE_RESULT_STATUS_INVALID") from exc
    if not isinstance(value.get("applicable"), bool):
        raise RuntimeError("ROUTINE_RESULT_APPLICABLE_INVALID")
    findings = value.get("findings")
    if not isinstance(findings, list):
        raise RuntimeError("ROUTINE_RESULT_FINDINGS_INVALID")
    for item in findings:
        _validate_finding(item)
    if findings != sorted(
        findings,
        key=lambda item: (str(item.get("subject") or ""), str(item.get("code") or ""), str(item.get("detail") or "")),
    ):
        raise RuntimeError("ROUTINE_RESULT_FINDINGS_NOT_SORTED")
    evidence = value.get("evidence")
    if not isinstance(evidence, dict) or set(evidence) != {"projectMachineInspectionHash"}:
        raise RuntimeError("ROUTINE_RESULT_EVIDENCE_INVALID")
    digest = evidence.get("projectMachineInspectionHash")
    if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise RuntimeError("ROUTINE_RESULT_MACHINE_HASH_INVALID")
    return value


def _failed_result(definition: RoutineDefinition, machine_hash: str, exc: Exception) -> dict[str, Any]:
    detail = str(exc).split(":", 1)[0] or exc.__class__.__name__
    return _result(
        definition.id,
        status=ObservationStatus.FAIL.value,
        applicable=True,
        findings=[_finding("ROUTINE_EVALUATION_FAILED", definition.id, detail, supervisor_eligible=False)],
        machine_hash=machine_hash,
    )


def _aggregate_status(results: list[dict[str, Any]], coverage: dict[str, list[str]]) -> str:
    if coverage["missing"]:
        return ObservationStatus.FAIL.value
    statuses = [str(item.get("status") or ObservationStatus.FAIL.value).upper() for item in results]
    if ObservationStatus.FAIL.value in statuses:
        return ObservationStatus.FAIL.value
    if ObservationStatus.UNKNOWN.value in statuses:
        return ObservationStatus.UNKNOWN.value
    return ObservationStatus.PASS.value


def build_inspection(
    machine: dict[str, Any],
    *,
    catalog: tuple[RoutineDefinition, ...] | list[RoutineDefinition] | None = None,
) -> dict[str, Any]:
    project_machine.validate_inspection(machine)
    definitions = _catalog(catalog)
    machine_hash = machine["inspectionHash"]
    results: list[dict[str, Any]] = []
    for definition in definitions:
        try:
            result = definition.evaluator(machine)
            _validate_result(result, expected_id=definition.id)
        except Exception as exc:  # a routine failure must become visible, never silent
            result = _failed_result(definition, machine_hash, exc)
        results.append(result)
    coverage = coverage_for(definitions, results)
    status = _aggregate_status(results, coverage)
    body = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": REPOSITORY,
        "projectMachineInspectionHash": machine_hash,
        "catalog": [item.id for item in definitions],
        "results": results,
        "coverage": coverage,
        "status": status,
        "complete": status == ObservationStatus.PASS.value and not coverage["missing"],
        "readOnly": True,
        "semanticAuthority": False,
    }
    return {**body, "inspectionHash": stable_hash(body)}


def validate_inspection(value: Any, machine: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("ROUTINE_INSPECTION_INVALID")
    expected_fields = {
        "schemaVersion", "repository", "projectMachineInspectionHash", "catalog", "results",
        "coverage", "status", "complete", "readOnly", "semanticAuthority", "inspectionHash",
    }
    if set(value) != expected_fields:
        raise RuntimeError("ROUTINE_INSPECTION_FIELDS_INVALID")
    if value.get("schemaVersion") != SCHEMA_VERSION:
        raise RuntimeError("ROUTINE_INSPECTION_SCHEMA_UNSUPPORTED")
    if value.get("repository") != REPOSITORY:
        raise RuntimeError("ROUTINE_REPOSITORY_MISMATCH")
    if value.get("readOnly") is not True or value.get("semanticAuthority") is not False:
        raise RuntimeError("ROUTINE_BOUNDARY_INVALID")

    definitions = _catalog()
    expected_catalog = [item.id for item in definitions]
    if value.get("catalog") != expected_catalog:
        raise RuntimeError("ROUTINE_CATALOG_MISMATCH")
    results = value.get("results")
    if not isinstance(results, list) or len(results) != len(expected_catalog):
        raise RuntimeError("ROUTINE_RESULTS_INVALID")
    result_ids: list[str] = []
    for item in results:
        _validate_result(item)
        result_ids.append(item["id"])
    if result_ids != expected_catalog:
        raise RuntimeError("ROUTINE_RESULT_COVERAGE_MISMATCH")

    coverage = coverage_for(definitions, results)
    if value.get("coverage") != coverage:
        raise RuntimeError("ROUTINE_COVERAGE_MISMATCH")
    status = _aggregate_status(results, coverage)
    if value.get("status") != status:
        raise RuntimeError("ROUTINE_STATUS_MISMATCH")
    expected_complete = status == ObservationStatus.PASS.value and not coverage["missing"]
    if value.get("complete") is not expected_complete:
        raise RuntimeError("ROUTINE_COMPLETE_MISMATCH")

    machine_hash = value.get("projectMachineInspectionHash")
    if not isinstance(machine_hash, str) or len(machine_hash) != 64 or any(char not in "0123456789abcdef" for char in machine_hash):
        raise RuntimeError("ROUTINE_PROJECT_MACHINE_HASH_INVALID")
    if any(item["evidence"]["projectMachineInspectionHash"] != machine_hash for item in results):
        raise RuntimeError("ROUTINE_RESULT_LINEAGE_MISMATCH")

    supplied = value.get("inspectionHash")
    body = {key: item for key, item in value.items() if key != "inspectionHash"}
    if not isinstance(supplied, str) or supplied != stable_hash(body):
        raise RuntimeError("ROUTINE_HASH_MISMATCH")

    if machine is not None:
        project_machine.validate_inspection(machine)
        if machine["inspectionHash"] != machine_hash:
            raise RuntimeError("ROUTINE_PROJECT_MACHINE_MISMATCH")
        if value != build_inspection(machine):
            raise RuntimeError("ROUTINE_DERIVATION_MISMATCH")
    return value


def load_json(path: str | Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(code) from exc
    if not isinstance(value, dict):
        raise RuntimeError(code)
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="routines", description="Read-only recurring operational routine inspection")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--input", required=True)
    inspect_parser.add_argument("--json", action="store_true", dest="as_json")
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("path")
    validate_parser.add_argument("--project-machine", required=True)
    validate_parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            machine = load_json(args.input, "ROUTINE_PROJECT_MACHINE_INPUT_INVALID")
            payload = build_inspection(machine)
        else:
            machine = load_json(args.project_machine, "ROUTINE_PROJECT_MACHINE_INPUT_INVALID")
            payload = validate_inspection(load_json(args.path, "ROUTINE_INSPECTION_INPUT_INVALID"), machine)
        if args.as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"ROUTINES {payload['status']} complete={str(payload['complete']).lower()}")
            for item in payload["results"]:
                print(f"  {item['status']:7} {item['id']} applicable={str(item['applicable']).lower()} findings={len(item['findings'])}")
        if args.command == "validate":
            return 0
        if payload["status"] == ObservationStatus.FAIL.value:
            return ERROR_EXIT
        if payload["status"] == ObservationStatus.UNKNOWN.value:
            return UNKNOWN_EXIT
        return 0
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        if getattr(args, "as_json", False):
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"BLOCKED\n{exc}", file=sys.stderr)
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
