#!/usr/bin/env python3
"""Read-only runtime capability/provider inspection.

This module never performs transport discovery itself and never authorizes mutation.
It resolves logical capabilities from normalized provider observations so callers can
distinguish "one provider is absent" from "the capability is unavailable".
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.canonical import stable_hash
from tools.semantics.registry import load_registry, validate_registry

INSPECTION_SCHEMA = "RuntimeCapabilityInspection 0.1"
PROVIDER_OBSERVATIONS_SCHEMA = "RuntimeProviderObservations 0.1"
STATUSES = {"PASS", "UNKNOWN", "FAIL"}

def _runtime_catalog() -> tuple[tuple[str, ...], dict[str, dict[str, dict[str, list[str]]]]]:
    registry = load_registry()
    errors = validate_registry(registry)
    if errors:
        raise RuntimeError(errors[0])
    providers = tuple(sorted(registry["providerProfiles"]))
    capabilities = {
        capability_id: {
            "providerRequirements": {
                provider_id: list(features)
                for provider_id, features in item["providerRequirements"].items()
            }
        }
        for capability_id, item in registry["logicalCapabilities"].items()
        if item["availabilityClass"] == "runtime-observed"
    }
    return providers, capabilities


PROVIDERS, CAPABILITIES = _runtime_catalog()


def _unique_strings(value: Any, code: str) -> list[str]:
    if not isinstance(value, list):
        raise RuntimeError(code)
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise RuntimeError(code)
        item = item.strip()
        if item in result:
            raise RuntimeError(code)
        result.append(item)
    return sorted(result)


def _provider_record(value: Any, *, provider_id: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"status", "features", "reason"}:
        raise RuntimeError("RUNTIME_PROVIDER_FIELDS_INVALID")
    status = str(value.get("status") or "").upper()
    if status not in STATUSES:
        raise RuntimeError("RUNTIME_PROVIDER_STATUS_INVALID")
    features = _unique_strings(value.get("features"), "RUNTIME_PROVIDER_FEATURES_INVALID")
    reason = value.get("reason")
    if reason is not None and (not isinstance(reason, str) or not reason.strip()):
        raise RuntimeError("RUNTIME_PROVIDER_REASON_INVALID")
    if status != "PASS" and features:
        raise RuntimeError("RUNTIME_PROVIDER_UNVERIFIED_FEATURES")
    return {
        "status": status,
        "features": features,
        "reason": reason.strip() if isinstance(reason, str) else None,
    }


def validate_provider_observations(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"schemaVersion", "providers"}:
        raise RuntimeError("RUNTIME_PROVIDER_OBSERVATIONS_FIELDS_INVALID")
    if value.get("schemaVersion") != PROVIDER_OBSERVATIONS_SCHEMA:
        raise RuntimeError("RUNTIME_PROVIDER_OBSERVATIONS_SCHEMA_UNSUPPORTED")
    providers = value.get("providers")
    if not isinstance(providers, dict):
        raise RuntimeError("RUNTIME_PROVIDERS_INVALID")
    unknown = sorted(set(providers) - set(PROVIDERS))
    if unknown:
        raise RuntimeError(f"RUNTIME_PROVIDER_UNKNOWN:{unknown[0]}")
    normalized: dict[str, dict[str, Any]] = {}
    for provider_id in sorted(providers):
        normalized[provider_id] = _provider_record(providers[provider_id], provider_id=provider_id)
    return {"schemaVersion": PROVIDER_OBSERVATIONS_SCHEMA, "providers": normalized}


def load_provider_observations(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError("RUNTIME_PROVIDER_OBSERVATIONS_MISSING") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("RUNTIME_PROVIDER_OBSERVATIONS_JSON_INVALID") from exc
    return validate_provider_observations(value)


def local_provider_observations() -> dict[str, Any]:
    providers: dict[str, dict[str, Any]] = {}
    if shutil.which("git"):
        providers["local-git"] = {
            "status": "PASS",
            "features": ["local-git-read"],
            "reason": None,
        }
    else:
        providers["local-git"] = {
            "status": "FAIL",
            "features": [],
            "reason": "PROVIDER_NOT_PRESENT",
        }
    if shutil.which("gh"):
        providers["gh-api"] = {
            "status": "UNKNOWN",
            "features": [],
            "reason": "PROVIDER_PRESENT_NOT_PROBED",
        }
    else:
        providers["gh-api"] = {
            "status": "FAIL",
            "features": [],
            "reason": "PROVIDER_NOT_PRESENT",
        }
    providers["local-python"] = {
        "status": "PASS",
        "features": ["python-module-execution"],
        "reason": None,
    }
    return validate_provider_observations(
        {"schemaVersion": PROVIDER_OBSERVATIONS_SCHEMA, "providers": providers}
    )


def merge_provider_observations(
    base: dict[str, Any], overlay: dict[str, Any]
) -> dict[str, Any]:
    left = validate_provider_observations(base)
    right = validate_provider_observations(overlay)
    providers = copy.deepcopy(left["providers"])
    for provider_id, value in right["providers"].items():
        providers[provider_id] = copy.deepcopy(value)
    return validate_provider_observations(
        {"schemaVersion": PROVIDER_OBSERVATIONS_SCHEMA, "providers": providers}
    )


def normalize_provider_observations(value: dict[str, Any]) -> dict[str, Any]:
    observed = validate_provider_observations(value)
    providers = copy.deepcopy(observed["providers"])
    for provider_id in PROVIDERS:
        providers.setdefault(
            provider_id,
            {
                "status": "UNKNOWN",
                "features": [],
                "reason": "PROVIDER_NOT_OBSERVED",
            },
        )
    return {
        "schemaVersion": PROVIDER_OBSERVATIONS_SCHEMA,
        "providers": {key: providers[key] for key in sorted(providers)},
    }


def _evaluate_capability(
    provider_observations: dict[str, Any],
    capability_id: str,
    spec: dict[str, dict[str, list[str]]],
) -> dict[str, Any]:
    requirements = spec["providerRequirements"]
    required = sorted(
        {
            feature
            for features in requirements.values()
            for feature in features
        }
    )
    evaluations: list[dict[str, Any]] = []
    satisfied: list[str] = []
    undecided = False
    for provider_id, provider_required in requirements.items():
        provider = provider_observations["providers"][provider_id]
        status = provider["status"]
        missing = sorted(set(provider_required) - set(provider["features"]))
        if status == "PASS" and not missing:
            outcome = "SATISFIED"
            satisfied.append(provider_id)
        elif status == "UNKNOWN":
            outcome = "UNOBSERVED_OR_INCOMPLETE"
            undecided = True
        elif status == "PASS":
            outcome = "MISSING_REQUIRED_FEATURES"
        else:
            outcome = "PROVIDER_FAILED"
        evaluations.append(
            {
                "provider": provider_id,
                "providerStatus": status,
                "outcome": outcome,
                "missingFeatures": missing,
                "reason": provider["reason"],
            }
        )
    if satisfied:
        status = "PASS"
        reason_code = "CAPABILITY_SATISFIED"
    elif undecided:
        status = "UNKNOWN"
        reason_code = "PROVIDER_OBSERVATION_INCOMPLETE"
    else:
        status = "FAIL"
        reason_code = "NO_SUPPORTED_PROVIDER_SATISFIES_REQUIREMENTS"
    return {
        "status": status,
        "reasonCode": reason_code,
        "requiredFeatures": required,
        "supportedProviders": list(requirements),
        "satisfiedProviders": sorted(satisfied),
        "providerEvaluations": evaluations,
    }


def build_inspection(provider_observations: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_provider_observations(provider_observations)
    capabilities = {
        capability_id: _evaluate_capability(normalized, capability_id, CAPABILITIES[capability_id])
        for capability_id in sorted(CAPABILITIES)
    }
    body = {
        "schemaVersion": INSPECTION_SCHEMA,
        "providerObservationSchemaVersion": PROVIDER_OBSERVATIONS_SCHEMA,
        "providers": normalized["providers"],
        "capabilities": capabilities,
        "authorizesMutation": False,
    }
    return {**body, "inspectionHash": stable_hash(body)}


def validate_inspection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("RUNTIME_CAPABILITY_INSPECTION_INVALID")
    required = {
        "schemaVersion",
        "providerObservationSchemaVersion",
        "providers",
        "capabilities",
        "authorizesMutation",
        "inspectionHash",
    }
    if set(value) != required:
        raise RuntimeError("RUNTIME_CAPABILITY_INSPECTION_FIELDS_INVALID")
    if value.get("schemaVersion") != INSPECTION_SCHEMA:
        raise RuntimeError("RUNTIME_CAPABILITY_INSPECTION_SCHEMA_UNSUPPORTED")
    if value.get("providerObservationSchemaVersion") != PROVIDER_OBSERVATIONS_SCHEMA:
        raise RuntimeError("RUNTIME_PROVIDER_OBSERVATIONS_SCHEMA_UNSUPPORTED")
    if value.get("authorizesMutation") is not False:
        raise RuntimeError("RUNTIME_CAPABILITY_INSPECTION_MUST_NOT_AUTHORIZE")
    normalized = normalize_provider_observations(
        {
            "schemaVersion": PROVIDER_OBSERVATIONS_SCHEMA,
            "providers": value.get("providers"),
        }
    )
    expected = build_inspection(normalized)
    if value != expected:
        raise RuntimeError("RUNTIME_CAPABILITY_INSPECTION_MISMATCH")
    return value


def _build_from_args(args: argparse.Namespace) -> dict[str, Any]:
    observations = local_provider_observations()
    if args.providers:
        observations = merge_provider_observations(
            observations, load_provider_observations(Path(args.providers))
        )
    return build_inspection(observations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="runtime-capabilities",
        description="Read-only runtime capability/provider inspection",
    )
    parser.add_argument("command", choices=("inspect", "validate"))
    parser.add_argument("path", nargs="?")
    parser.add_argument("--providers")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            if args.path is not None:
                raise RuntimeError("RUNTIME_CAPABILITY_UNEXPECTED_PATH")
            payload = _build_from_args(args)
        else:
            if not args.path:
                raise RuntimeError("RUNTIME_CAPABILITY_INSPECTION_PATH_REQUIRED")
            payload = validate_inspection(json.loads(Path(args.path).read_text(encoding="utf-8")))
        if args.as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            for capability_id, item in payload["capabilities"].items():
                providers = ",".join(item["satisfiedProviders"]) or "-"
                print(f"{item['status']:7} {capability_id} [{providers}]")
        return 0
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        if args.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"BLOCKED\n{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
