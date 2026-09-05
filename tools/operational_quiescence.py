from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterable

from tools import project_machine, reflection_eligibility
from tools.canonical import canonical_json, stable_hash

SAMPLE_SCHEMA_VERSION = "OperationalQuiescenceSample 0.1"
WINDOW_SCHEMA_VERSION = "OperationalQuiescence 0.1"
REPOSITORY = project_machine.REPOSITORY
WINDOW_SIZE = 3

SAMPLE_FIELDS = {
    "schemaVersion",
    "repository",
    "observationId",
    "sequence",
    "sourceProjectMachineInspectionHash",
    "readbackProjectMachineInspectionHash",
    "schedulerSnapshotHash",
    "reflectionEligibilityInspectionHash",
    "reflectionStatus",
    "reflectionEligible",
    "sourceFacts",
    "readbackFacts",
    "sourceCriticalHash",
    "readbackCriticalHash",
    "baselineHash",
    "sampleEligible",
    "reasonCodes",
    "decisionScope",
    "readOnly",
    "semanticAuthority",
    "authorizesMutation",
    "sampleHash",
}
WINDOW_FIELDS = {
    "schemaVersion",
    "repository",
    "windowSize",
    "sampleCountObserved",
    "sampleHashesObserved",
    "windowSampleHashes",
    "windowObservationIds",
    "windowSequences",
    "baselineHash",
    "windowComplete",
    "eligible",
    "invalidated",
    "resetCount",
    "lastResetReasonCodes",
    "status",
    "reasonCodes",
    "decisionScope",
    "readOnly",
    "semanticAuthority",
    "authorizesMutation",
    "evaluationHash",
}
WINDOW_STATUSES = {"NO_SAMPLES", "RESET", "ACCUMULATING", "QUIESCENT"}
ELIGIBLE_REFLECTION_STATUSES = {"LEGITIMATE_WAIT", "REFLECTION_ELIGIBLE"}


def _load_json(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("OPERATIONAL_QUIESCENCE_INPUT_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_INPUT_INVALID")
    return value


def _nonempty(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(code)
    return value


def _positive_int(value: Any, code: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise RuntimeError(code)
    return value


def _hash(value: Any, code: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise RuntimeError(code)
    return value


def _stable_items(values: Iterable[Any]) -> list[Any]:
    return sorted((copy.deepcopy(item) for item in values), key=canonical_json)


def _sensor(machine: dict[str, Any], name: str) -> dict[str, Any]:
    sensors = machine.get("sensors")
    sensor = sensors.get(name) if isinstance(sensors, dict) else None
    if not isinstance(sensor, dict):
        raise RuntimeError(f"OPERATIONAL_QUIESCENCE_SENSOR_MISSING:{name}")
    return sensor


def _data(machine: dict[str, Any], name: str) -> dict[str, Any]:
    data = _sensor(machine, name).get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"OPERATIONAL_QUIESCENCE_SENSOR_DATA_INVALID:{name}")
    return data


def _required_sensor_summary(machine: dict[str, Any]) -> list[dict[str, Any]]:
    sensors = machine.get("sensors")
    if not isinstance(sensors, dict):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_SENSORS_INVALID")
    out = []
    for name in sorted(sensors):
        sensor = sensors[name]
        if not isinstance(sensor, dict) or sensor.get("required") is not True:
            continue
        out.append(
            {
                "name": name,
                "status": sensor.get("status"),
                "code": sensor.get("code"),
            }
        )
    return out


def _required_coherence_summary(machine: dict[str, Any]) -> list[dict[str, Any]]:
    coherence = machine.get("coherence")
    checks = coherence.get("checks") if isinstance(coherence, dict) else None
    if not isinstance(checks, list):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_COHERENCE_INVALID")
    out = []
    for item in checks:
        if not isinstance(item, dict) or item.get("required") is not True:
            continue
        out.append(
            {
                "id": item.get("id"),
                "status": item.get("status"),
                "code": item.get("code"),
                "subjects": copy.deepcopy(item.get("subjects")),
                "detail": copy.deepcopy(item.get("detail")),
            }
        )
    return sorted(out, key=lambda item: str(item.get("id") or ""))


def _normalized_pull_requests(machine: dict[str, Any]) -> dict[str, Any]:
    data = _data(machine, "pullRequests")
    items = data.get("items")
    if not isinstance(items, list):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_PULL_REQUESTS_INVALID")
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            raise RuntimeError("OPERATIONAL_QUIESCENCE_PULL_REQUEST_INVALID")
        normalized.append(
            {
                key: copy.deepcopy(item.get(key))
                for key in (
                    "number",
                    "draft",
                    "headRef",
                    "headSha",
                    "baseRef",
                    "ci",
                    "ciObserved",
                )
            }
        )
    normalized.sort(key=lambda item: (int(item.get("number") or 0), str(item.get("headRef") or "")))
    return {"available": data.get("available") is True, "items": normalized}


def _normalized_coordination(machine: dict[str, Any]) -> dict[str, Any]:
    data = _data(machine, "coordination")
    intents = data.get("intents")
    leases = data.get("leases")
    if not isinstance(intents, list) or not isinstance(leases, list):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_COORDINATION_INVALID")
    return {
        "available": data.get("available") is True,
        "authorityBranch": data.get("authorityBranch"),
        "authorityHead": data.get("authorityHead"),
        "intents": _stable_items(intents),
        "leases": _stable_items(leases),
    }


def _normalized_continuations(machine: dict[str, Any]) -> dict[str, Any]:
    data = _data(machine, "continuations")
    items = data.get("items")
    if not isinstance(items, list):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_CONTINUATIONS_INVALID")
    normalized = _stable_items(items)
    normalized.sort(key=lambda item: str(item.get("id") or "") if isinstance(item, dict) else canonical_json(item))
    return {
        "available": data.get("available") is True,
        "authorityBranch": data.get("authorityBranch"),
        "authorityHead": data.get("authorityHead"),
        "items": normalized,
    }


def _normalized_capabilities(machine: dict[str, Any]) -> list[Any]:
    data = _data(machine, "capabilities")
    items = data.get("items")
    if not isinstance(items, list):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_CAPABILITIES_INVALID")
    normalized = _stable_items(items)
    normalized.sort(key=lambda item: str(item.get("id") or "") if isinstance(item, dict) else canonical_json(item))
    return normalized


def _normalized_publication(machine: dict[str, Any]) -> dict[str, Any]:
    data = _data(machine, "publication")
    keys = (
        "url",
        "artifactManifest",
        "release",
        "sourceBranch",
        "sourceBuildFingerprint",
        "fingerprintKind",
        "sourceBase",
        "sourcePaths",
        "publishPath",
    )
    return {key: copy.deepcopy(data.get(key)) for key in keys}


def critical_facts(machine: dict[str, Any]) -> dict[str, Any]:
    project_machine.validate_inspection(machine)
    if machine.get("scope") != "live":
        raise RuntimeError("OPERATIONAL_QUIESCENCE_REQUIRES_LIVE_SCOPE")
    heads = machine["sourceHeads"]
    trust = machine["trust"]
    coherence = machine["coherence"]
    return {
        "project": copy.deepcopy(machine["project"]),
        "authorityHeads": {
            name: copy.deepcopy(heads[name])
            for name in ("control", "coordination", "continuation")
        },
        "trust": {
            "status": trust.get("status"),
            "ok": trust.get("ok"),
            "complete": trust.get("complete"),
            "failedSensors": copy.deepcopy(trust.get("failedSensors")),
            "unknownSensors": copy.deepcopy(trust.get("unknownSensors")),
        },
        "coherence": {
            "status": coherence.get("status"),
            "ok": coherence.get("ok"),
            "complete": coherence.get("complete"),
            "failedChecks": copy.deepcopy(coherence.get("failedChecks")),
            "unknownChecks": copy.deepcopy(coherence.get("unknownChecks")),
            "requiredChecks": _required_coherence_summary(machine),
        },
        "requiredSensors": _required_sensor_summary(machine),
        "publication": _normalized_publication(machine),
        "pullRequests": _normalized_pull_requests(machine),
        "coordination": _normalized_coordination(machine),
        "continuations": _normalized_continuations(machine),
        "capabilities": _normalized_capabilities(machine),
        "workGraph": copy.deepcopy(machine["workGraph"]),
    }


def _machine_health_reasons(facts: dict[str, Any], prefix: str) -> list[str]:
    reasons: list[str] = []
    trust = facts["trust"]
    coherence = facts["coherence"]
    if trust.get("status") != "PASS" or trust.get("complete") is not True:
        reasons.append(f"{prefix}_TRUST_NOT_COMPLETE")
    if coherence.get("status") != "PASS" or coherence.get("complete") is not True:
        reasons.append(f"{prefix}_COHERENCE_NOT_COMPLETE")
    for sensor in facts["requiredSensors"]:
        if sensor.get("status") != "PASS":
            reasons.append(f"{prefix}_REQUIRED_SENSOR_NOT_PASS:{sensor.get('name')}")
    coordination = facts["coordination"]
    if coordination.get("available") is not True:
        reasons.append(f"{prefix}_COORDINATION_NOT_AVAILABLE")
    if coordination.get("intents"):
        reasons.append("COORDINATION_INTENTS_ACTIVE")
    if coordination.get("leases"):
        reasons.append("COORDINATION_LEASES_ACTIVE")
    if facts["pullRequests"].get("available") is not True:
        reasons.append(f"{prefix}_PULL_REQUESTS_NOT_AVAILABLE")
    if facts["continuations"].get("available") is not True:
        reasons.append(f"{prefix}_CONTINUATIONS_NOT_AVAILABLE")
    return reasons


def _sample_reasons(
    *,
    reflection: dict[str, Any],
    source_facts: dict[str, Any],
    readback_facts: dict[str, Any],
    source_hash: str,
    readback_hash: str,
) -> list[str]:
    reasons: list[str] = []
    status = reflection["status"]
    if status == "PRIORITY_OPERATION_REQUIRED":
        reasons.append("PRIORITY_OPERATION_REQUIRED")
        reasons.extend(reflection["reasonCodes"])
    elif status == "INSUFFICIENT_OBSERVATION":
        reasons.append("INSUFFICIENT_OBSERVATION")
        reasons.extend(reflection["reasonCodes"])
    elif status not in ELIGIBLE_REFLECTION_STATUSES:
        reasons.append("REFLECTION_DISPOSITION_UNSUPPORTED")
    reasons.extend(_machine_health_reasons(source_facts, "SOURCE"))
    reasons.extend(_machine_health_reasons(readback_facts, "READBACK"))
    if source_hash != readback_hash:
        reasons.append("INTRA_SAMPLE_OPERATIONAL_DRIFT")
    return sorted(set(str(item) for item in reasons))


def build_sample(
    *,
    snapshot: dict[str, Any],
    reflection: dict[str, Any],
    source_machine: dict[str, Any],
    routine_inspection: dict[str, Any],
    readback_machine: dict[str, Any],
    observation_id: str,
    sequence: int,
    expected_heads: dict[str, str] | None = None,
) -> dict[str, Any]:
    reflection_eligibility.validate_derivation(
        reflection,
        snapshot,
        source_machine=source_machine,
        routine_inspection=routine_inspection,
        readback_machine=readback_machine,
        expected_heads=expected_heads,
    )
    observation_id = _nonempty(
        observation_id, "OPERATIONAL_QUIESCENCE_OBSERVATION_ID_REQUIRED"
    )
    sequence = _positive_int(sequence, "OPERATIONAL_QUIESCENCE_SEQUENCE_INVALID")
    source_facts = critical_facts(source_machine)
    readback_facts = critical_facts(readback_machine)
    source_hash = stable_hash(source_facts)
    readback_hash = stable_hash(readback_facts)
    reasons = _sample_reasons(
        reflection=reflection,
        source_facts=source_facts,
        readback_facts=readback_facts,
        source_hash=source_hash,
        readback_hash=readback_hash,
    )
    sample_eligible = (
        reflection.get("reflectionEligible") is True
        and reflection.get("status") in ELIGIBLE_REFLECTION_STATUSES
        and not reasons
        and source_hash == readback_hash
    )
    body = {
        "schemaVersion": SAMPLE_SCHEMA_VERSION,
        "repository": REPOSITORY,
        "observationId": observation_id,
        "sequence": sequence,
        "sourceProjectMachineInspectionHash": source_machine["inspectionHash"],
        "readbackProjectMachineInspectionHash": readback_machine["inspectionHash"],
        "schedulerSnapshotHash": snapshot["snapshotHash"],
        "reflectionEligibilityInspectionHash": reflection["inspectionHash"],
        "reflectionStatus": reflection["status"],
        "reflectionEligible": reflection["reflectionEligible"],
        "sourceFacts": source_facts,
        "readbackFacts": readback_facts,
        "sourceCriticalHash": source_hash,
        "readbackCriticalHash": readback_hash,
        "baselineHash": readback_hash if sample_eligible else None,
        "sampleEligible": sample_eligible,
        "reasonCodes": reasons,
        "decisionScope": "operational-quiescence-sample-only",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    value = {**body, "sampleHash": stable_hash(body)}
    validate_sample(value)
    return value


def validate_sample(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != SAMPLE_FIELDS:
        raise RuntimeError("OPERATIONAL_QUIESCENCE_SAMPLE_FIELDS_INVALID")
    if value.get("schemaVersion") != SAMPLE_SCHEMA_VERSION:
        raise RuntimeError("OPERATIONAL_QUIESCENCE_SAMPLE_SCHEMA_UNSUPPORTED")
    if value.get("repository") != REPOSITORY:
        raise RuntimeError("OPERATIONAL_QUIESCENCE_REPOSITORY_MISMATCH")
    _nonempty(value.get("observationId"), "OPERATIONAL_QUIESCENCE_OBSERVATION_ID_REQUIRED")
    _positive_int(value.get("sequence"), "OPERATIONAL_QUIESCENCE_SEQUENCE_INVALID")
    for field in (
        "sourceProjectMachineInspectionHash",
        "readbackProjectMachineInspectionHash",
        "schedulerSnapshotHash",
        "reflectionEligibilityInspectionHash",
        "sourceCriticalHash",
        "readbackCriticalHash",
    ):
        _hash(value.get(field), "OPERATIONAL_QUIESCENCE_HASH_INVALID")
    source_facts = value.get("sourceFacts")
    readback_facts = value.get("readbackFacts")
    if not isinstance(source_facts, dict) or not isinstance(readback_facts, dict):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_FACTS_INVALID")
    source_hash = stable_hash(source_facts)
    readback_hash = stable_hash(readback_facts)
    if source_hash != value["sourceCriticalHash"] or readback_hash != value["readbackCriticalHash"]:
        raise RuntimeError("OPERATIONAL_QUIESCENCE_CRITICAL_HASH_MISMATCH")
    status = value.get("reflectionStatus")
    if status not in {
        "PRIORITY_OPERATION_REQUIRED",
        "LEGITIMATE_WAIT",
        "INSUFFICIENT_OBSERVATION",
        "REFLECTION_ELIGIBLE",
    }:
        raise RuntimeError("OPERATIONAL_QUIESCENCE_REFLECTION_STATUS_INVALID")
    if value.get("reflectionEligible") is not (status in ELIGIBLE_REFLECTION_STATUSES):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_REFLECTION_FLAG_MISMATCH")
    synthetic_reflection = {
        "status": status,
        "reflectionEligible": value["reflectionEligible"],
        "reasonCodes": [],
    }
    reasons = _sample_reasons(
        reflection=synthetic_reflection,
        source_facts=source_facts,
        readback_facts=readback_facts,
        source_hash=source_hash,
        readback_hash=readback_hash,
    )
    required_reasons = set(reasons)
    supplied_reasons = value.get("reasonCodes")
    if not isinstance(supplied_reasons, list) or supplied_reasons != sorted(
        set(str(item) for item in supplied_reasons)
    ):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_REASONS_INVALID")
    if not required_reasons.issubset(set(supplied_reasons)):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_REASONS_MISMATCH")
    eligible = (
        status in ELIGIBLE_REFLECTION_STATUSES
        and value["reflectionEligible"] is True
        and not supplied_reasons
        and source_hash == readback_hash
    )
    if value.get("sampleEligible") is not eligible:
        raise RuntimeError("OPERATIONAL_QUIESCENCE_SAMPLE_ELIGIBILITY_MISMATCH")
    expected_baseline = readback_hash if eligible else None
    if value.get("baselineHash") != expected_baseline:
        raise RuntimeError("OPERATIONAL_QUIESCENCE_BASELINE_MISMATCH")
    if (
        value.get("decisionScope") != "operational-quiescence-sample-only"
        or value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_SAMPLE_BOUNDARY_INVALID")
    supplied = value.get("sampleHash")
    body = {key: copy.deepcopy(item) for key, item in value.items() if key != "sampleHash"}
    if not isinstance(supplied, str) or supplied != stable_hash(body):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_SAMPLE_HASH_MISMATCH")
    return value


def validate_sample_derivation(
    value: dict[str, Any],
    *,
    snapshot: dict[str, Any],
    reflection: dict[str, Any],
    source_machine: dict[str, Any],
    routine_inspection: dict[str, Any],
    readback_machine: dict[str, Any],
    expected_heads: dict[str, str] | None = None,
) -> dict[str, Any]:
    validate_sample(value)
    expected = build_sample(
        snapshot=snapshot,
        reflection=reflection,
        source_machine=source_machine,
        routine_inspection=routine_inspection,
        readback_machine=readback_machine,
        observation_id=value["observationId"],
        sequence=value["sequence"],
        expected_heads=expected_heads,
    )
    if value != expected:
        raise RuntimeError("OPERATIONAL_QUIESCENCE_SAMPLE_DERIVATION_MISMATCH")
    return value


def _validate_sample_sequence(samples: list[dict[str, Any]]) -> None:
    sequences = [sample["sequence"] for sample in samples]
    observation_ids = [sample["observationId"] for sample in samples]
    sample_hashes = [sample["sampleHash"] for sample in samples]
    if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_SAMPLE_SEQUENCE_INVALID")
    if len(observation_ids) != len(set(observation_ids)):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_OBSERVATION_ID_DUPLICATE")
    if len(sample_hashes) != len(set(sample_hashes)):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_SAMPLE_DUPLICATE")


def _derive_window(samples: list[dict[str, Any]]) -> dict[str, Any]:
    for sample in samples:
        validate_sample(sample)
    _validate_sample_sequence(samples)

    segment: list[dict[str, Any]] = []
    reset_count = 0
    last_reset_reasons: list[str] = []
    for sample in samples:
        if not sample["sampleEligible"]:
            reset_count += 1
            segment = []
            last_reset_reasons = list(sample["reasonCodes"]) or ["SAMPLE_NOT_ELIGIBLE"]
            continue
        if segment and sample["baselineHash"] != segment[-1]["baselineHash"]:
            reset_count += 1
            segment = [sample]
            last_reset_reasons = ["OPERATIONAL_BASELINE_CHANGED"]
            continue
        segment.append(sample)

    selected = segment[-WINDOW_SIZE:]
    window_complete = len(segment) >= WINDOW_SIZE
    eligible = window_complete
    invalidated = bool(samples) and not samples[-1]["sampleEligible"]

    if not samples:
        status = "NO_SAMPLES"
        reasons = ["INSUFFICIENT_SAMPLES"]
    elif invalidated:
        status = "RESET"
        reasons = sorted(set(last_reset_reasons or ["SAMPLE_NOT_ELIGIBLE"]))
    elif eligible:
        status = "QUIESCENT"
        reasons = ["WINDOW_COMPLETE"]
    else:
        status = "ACCUMULATING"
        reasons = ["INSUFFICIENT_SAMPLES"]
        if reset_count:
            reasons.append("WINDOW_RESTARTED")

    baseline = selected[-1]["baselineHash"] if selected else None
    body = {
        "schemaVersion": WINDOW_SCHEMA_VERSION,
        "repository": REPOSITORY,
        "windowSize": WINDOW_SIZE,
        "sampleCountObserved": len(samples),
        "sampleHashesObserved": [sample["sampleHash"] for sample in samples],
        "windowSampleHashes": [sample["sampleHash"] for sample in selected],
        "windowObservationIds": [sample["observationId"] for sample in selected],
        "windowSequences": [sample["sequence"] for sample in selected],
        "baselineHash": baseline,
        "windowComplete": window_complete,
        "eligible": eligible,
        "invalidated": invalidated,
        "resetCount": reset_count,
        "lastResetReasonCodes": sorted(set(last_reset_reasons)),
        "status": status,
        "reasonCodes": reasons,
        "decisionScope": "operational-quiescence-only",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "evaluationHash": stable_hash(body)}


def evaluate_window(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(samples, list):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_SAMPLES_INVALID")
    value = _derive_window(samples)
    validate_window(value, samples=samples)
    return value


def validate_window(value: Any, *, samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != WINDOW_FIELDS:
        raise RuntimeError("OPERATIONAL_QUIESCENCE_WINDOW_FIELDS_INVALID")
    if value.get("schemaVersion") != WINDOW_SCHEMA_VERSION:
        raise RuntimeError("OPERATIONAL_QUIESCENCE_WINDOW_SCHEMA_UNSUPPORTED")
    if value.get("repository") != REPOSITORY or value.get("windowSize") != WINDOW_SIZE:
        raise RuntimeError("OPERATIONAL_QUIESCENCE_WINDOW_POLICY_INVALID")
    if value.get("status") not in WINDOW_STATUSES:
        raise RuntimeError("OPERATIONAL_QUIESCENCE_WINDOW_STATUS_INVALID")
    if (
        value.get("decisionScope") != "operational-quiescence-only"
        or value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_WINDOW_BOUNDARY_INVALID")
    supplied = value.get("evaluationHash")
    body = {key: copy.deepcopy(item) for key, item in value.items() if key != "evaluationHash"}
    if not isinstance(supplied, str) or supplied != stable_hash(body):
        raise RuntimeError("OPERATIONAL_QUIESCENCE_WINDOW_HASH_MISMATCH")
    expected = _derive_window(samples)
    if value != expected:
        raise RuntimeError("OPERATIONAL_QUIESCENCE_WINDOW_DERIVATION_MISMATCH")
    return value


def run(argv: list[str] | None = None) -> int:
    from argparse import ArgumentParser

    parser = ArgumentParser(prog="agent operational-quiescence")
    sub = parser.add_subparsers(dest="command", required=True)

    sample = sub.add_parser("sample")
    sample.add_argument("--snapshot", required=True)
    sample.add_argument("--reflection", required=True)
    sample.add_argument("--source-machine", required=True)
    sample.add_argument("--routines", required=True)
    sample.add_argument("--readback-machine", required=True)
    sample.add_argument("--observation-id", required=True)
    sample.add_argument("--sequence", required=True, type=int)
    sample.add_argument("--output")
    sample.add_argument("--json", action="store_true", dest="as_json")

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--sample", action="append", dest="samples", required=True)
    evaluate.add_argument("--output")
    evaluate.add_argument("--json", action="store_true", dest="as_json")

    args = parser.parse_args(argv)
    try:
        if args.command == "sample":
            value = build_sample(
                snapshot=_load_json(args.snapshot),
                reflection=_load_json(args.reflection),
                source_machine=_load_json(args.source_machine),
                routine_inspection=_load_json(args.routines),
                readback_machine=_load_json(args.readback_machine),
                observation_id=args.observation_id,
                sequence=args.sequence,
            )
        else:
            value = evaluate_window([_load_json(path) for path in args.samples])
        if args.output:
            Path(args.output).write_text(
                json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        print(json.dumps(value, indent=2 if args.as_json else None, ensure_ascii=False))
        return 0
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
