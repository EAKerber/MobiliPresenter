from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools import capability_gates
from tools.semantics.registry import ROOT, load_registry, validate_registry

CAPABILITY_BASE_FIELDS = {
    "schemaVersion",
    "id",
    "policy",
    "gates",
    "roundsWithoutActiveGates",
    "maxRoundsWithoutActiveGates",
    "deferReason",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"SEMANTIC_CONTRACT_JSON_INVALID:{path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"SEMANTIC_CONTRACT_ROOT_INVALID:{path}")
    return value


def check_capability_gates_contract() -> list[str]:
    registry = load_registry()
    errors = validate_registry(registry)
    if errors:
        return errors
    contract = registry["contracts"].get("capability-gates")
    if not isinstance(contract, dict):
        return ["SEMANTIC_CAPABILITY_CONTRACT_MISSING"]
    if contract.get("semanticValidator") != "tools.capability_gates.validate_capability":
        return ["SEMANTIC_CAPABILITY_VALIDATOR_MISMATCH"]
    schema_path = ROOT / str(contract.get("structuralSchema"))
    schema = _load_json(schema_path)
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    schema_fields = set(properties)
    accepted_fields = CAPABILITY_BASE_FIELDS | {"supervisorParticipation"}
    if schema_fields != accepted_fields:
        errors.append("SEMANTIC_CAPABILITY_SCHEMA_FIELDS_MISMATCH")
    required = set(schema.get("required") or [])
    if required != CAPABILITY_BASE_FIELDS:
        errors.append("SEMANTIC_CAPABILITY_SCHEMA_REQUIRED_MISMATCH")
    policy_enum = set((properties.get("policy") or {}).get("enum") or []) if isinstance(properties.get("policy"), dict) else set()
    if policy_enum != set(capability_gates.POLICIES):
        errors.append("SEMANTIC_CAPABILITY_POLICY_ENUM_MISMATCH")
    participation_enum = set((properties.get("supervisorParticipation") or {}).get("enum") or []) if isinstance(properties.get("supervisorParticipation"), dict) else set()
    if participation_enum != set(capability_gates.SUPERVISOR_PARTICIPATION):
        errors.append("SEMANTIC_CAPABILITY_SUPERVISOR_ENUM_MISMATCH")

    for path in sorted(capability_gates.CAPABILITY_DIR.glob("*.json")):
        value = _load_json(path)
        runtime_errors = capability_gates.validate_capability(value, expected_id=path.stem)
        if runtime_errors:
            errors.append(f"SEMANTIC_CAPABILITY_RUNTIME_INVALID:{path.name}:{runtime_errors[0]}")
            continue
        extra = set(value) - schema_fields
        if extra:
            errors.append(f"SEMANTIC_CAPABILITY_SCHEMA_REJECTS_RUNTIME:{path.name}")
        if value.get("policy") not in policy_enum:
            errors.append(f"SEMANTIC_CAPABILITY_SCHEMA_POLICY_REJECTS_RUNTIME:{path.name}")
        participation = value.get("supervisorParticipation")
        if participation is not None and participation not in participation_enum:
            errors.append(f"SEMANTIC_CAPABILITY_SCHEMA_SUPERVISOR_REJECTS_RUNTIME:{path.name}")
    return errors


def check_contracts() -> list[str]:
    return check_capability_gates_contract()
