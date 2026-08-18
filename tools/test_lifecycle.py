from __future__ import annotations

import importlib
import json
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
METADATA_ATTR = "__test_lifecycle__"


@dataclass(frozen=True)
class RetirementCondition:
    kind: str
    params: dict[str, Any]
    description: str

    def due(self) -> bool:
        if self.kind == "semantic-alias-absent":
            path = ROOT / "ops" / "semantics" / "registry.json"
            registry = json.loads(path.read_text(encoding="utf-8"))
            concept = registry.get("concepts", {}).get(self.params["semanticId"])
            if not isinstance(concept, dict):
                return True
            aliases = concept.get("aliases", [])
            return not any(
                isinstance(alias, dict)
                and alias.get("term") == self.params["alias"]
                and alias.get("scope") == self.params["scope"]
                for alias in aliases
            )

        if self.kind == "capability-policy-changed":
            path = ROOT / "ops" / "capabilities" / f"{self.params['capabilityId']}.json"
            if not path.is_file():
                return True
            value = json.loads(path.read_text(encoding="utf-8"))
            return value.get("policy") != self.params["expectedPolicy"]

        if self.kind == "capability-record-absent":
            path = ROOT / "ops" / "capabilities" / f"{self.params['capabilityId']}.json"
            return not path.is_file()

        if self.kind == "symbol-absent":
            module = importlib.import_module(self.params["module"])
            return not hasattr(module, self.params["symbol"])

        if self.kind == "schema-field-absent":
            path = ROOT / self.params["schemaPath"]
            schema = json.loads(path.read_text(encoding="utf-8"))
            current: Any = schema
            for part in self.params["fieldPath"].split("."):
                properties = current.get("properties", {}) if isinstance(current, dict) else {}
                if part not in properties:
                    return True
                current = properties[part]
            return False

        raise RuntimeError(f"TEST_RETIREMENT_CONDITION_UNKNOWN:{self.kind}")


def semantic_alias_absent(semantic_id: str, alias: str, scope: str) -> RetirementCondition:
    return RetirementCondition(
        "semantic-alias-absent",
        {"semanticId": semantic_id, "alias": alias, "scope": scope},
        f"semantic alias {semantic_id}:{scope}:{alias} is absent",
    )


def capability_policy_changed(capability_id: str, expected_policy: str) -> RetirementCondition:
    return RetirementCondition(
        "capability-policy-changed",
        {"capabilityId": capability_id, "expectedPolicy": expected_policy},
        f"capability {capability_id} policy is no longer {expected_policy}",
    )


def capability_record_absent(capability_id: str) -> RetirementCondition:
    return RetirementCondition(
        "capability-record-absent",
        {"capabilityId": capability_id},
        f"capability record {capability_id} is absent",
    )


def symbol_absent(module: str, symbol: str) -> RetirementCondition:
    return RetirementCondition(
        "symbol-absent",
        {"module": module, "symbol": symbol},
        f"symbol {module}.{symbol} is absent",
    )


def schema_field_absent(schema_path: str, field_path: str) -> RetirementCondition:
    return RetirementCondition(
        "schema-field-absent",
        {"schemaPath": schema_path, "fieldPath": field_path},
        f"schema field {schema_path}:{field_path} is absent",
    )


def transitional_test(*, owner: str, reason: str, retire_when: RetirementCondition) -> Callable[[Any], Any]:
    if not owner.strip():
        raise RuntimeError("TRANSITIONAL_TEST_OWNER_REQUIRED")
    if not reason.strip():
        raise RuntimeError("TRANSITIONAL_TEST_REASON_REQUIRED")
    if not isinstance(retire_when, RetirementCondition):
        raise RuntimeError("TRANSITIONAL_TEST_RETIREMENT_CONDITION_REQUIRED")

    def decorate(target: Any) -> Any:
        metadata = {
            "status": "transitional",
            "owner": owner,
            "reason": reason,
            "retireWhen": retire_when,
        }
        setattr(target, METADATA_ATTR, metadata)
        if retire_when.due():
            target = unittest.skip(
                f"TRANSITIONAL_TEST_RETIREMENT_DUE:{retire_when.description}"
            )(target)
            setattr(target, METADATA_ATTR, metadata)
        return target

    return decorate


transitional_suite = transitional_test


def lifecycle_metadata(target: Any) -> dict[str, Any] | None:
    value = getattr(target, METADATA_ATTR, None)
    return value if isinstance(value, dict) else None


def validate_metadata(metadata: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if metadata.get("status") != "transitional":
        errors.append("TRANSITIONAL_TEST_STATUS_INVALID")
    if not isinstance(metadata.get("owner"), str) or not metadata["owner"].strip():
        errors.append("TRANSITIONAL_TEST_OWNER_REQUIRED")
    if not isinstance(metadata.get("reason"), str) or not metadata["reason"].strip():
        errors.append("TRANSITIONAL_TEST_REASON_REQUIRED")
    if not isinstance(metadata.get("retireWhen"), RetirementCondition):
        errors.append("TRANSITIONAL_TEST_RETIREMENT_CONDITION_REQUIRED")
    return errors
