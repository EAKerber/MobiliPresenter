from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.canonical import stable_hash
from tools.semantics.registry import ROOT, load_registry, validate_registry

SCHEMA_VERSION = "OperationalSemanticsCoverage 0.1"
ENTRYPOINT_MARKER = re.compile(
    r"argparse\.ArgumentParser|if\s+__name__\s*==\s*['\"]__main__['\"]"
)
FINDING_FIELDS = {
    "registryErrors",
    "missingEntrypointComponents",
    "missingEntrypointBindings",
    "missingWorkflowBindings",
    "orphanedWorkflowBindings",
    "unregisteredSchemas",
    "missingSchemaFiles",
    "runtimeCapabilityMismatch",
    "providerProfileMismatch",
    "invalidExclusions",
}


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _module(path: Path) -> str:
    relative = path.relative_to(ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__main__":
        parts = parts[:-1]
    return ".".join(parts)


def _globbed(patterns: list[str]) -> list[Path]:
    found: set[Path] = set()
    for pattern in patterns:
        found.update(path for path in ROOT.glob(pattern) if path.is_file())
    return sorted(found)


def _entrypoints(registry: dict[str, Any]) -> list[Path]:
    candidates = _globbed(registry["coveragePolicy"]["entrypointGlobs"])
    return [
        path
        for path in candidates
        if ENTRYPOINT_MARKER.search(path.read_text(encoding="utf-8"))
    ]


def _bound_targets(registry: dict[str, Any], target_kind: str) -> set[str]:
    return {
        binding["target"]
        for surface in registry["toolSurfaces"].values()
        for binding in surface["bindings"]
        if binding["targetKind"] == target_kind
    }


def build_inspection(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    value = load_registry() if registry is None else registry
    registry_errors = sorted(validate_registry(value))
    components = value.get("components") if isinstance(value.get("components"), dict) else {}
    module_to_component = {
        item.get("module"): component_id
        for component_id, item in components.items()
        if isinstance(item, dict) and isinstance(item.get("module"), str)
    }

    entrypoints = _entrypoints(value)
    entrypoint_modules = {_module(path): _relative(path) for path in entrypoints}
    missing_components = sorted(
        path
        for module, path in entrypoint_modules.items()
        if module not in module_to_component
    )
    component_bindings = _bound_targets(value, "component")
    missing_bindings = sorted(
        path
        for module, path in entrypoint_modules.items()
        if module in module_to_component
        and module_to_component[module] not in component_bindings
    )

    workflows = [_relative(path) for path in _globbed(value["coveragePolicy"]["workflowGlobs"])]
    exclusions = value["coveragePolicy"]["exclusions"]
    excluded_paths = {item["path"] for item in exclusions}
    workflow_bindings = _bound_targets(value, "workflow")
    missing_workflows = sorted(set(workflows) - excluded_paths - workflow_bindings)
    orphaned_workflow_bindings = sorted(workflow_bindings - set(workflows))
    invalid_exclusions = sorted(
        path
        for path in excluded_paths
        if path not in set(workflows) and path not in set(entrypoint_modules.values())
    )

    contract_schemas = {
        item["structuralSchema"]
        for item in value.get("contracts", {}).values()
        if isinstance(item, dict) and isinstance(item.get("structuralSchema"), str)
    }
    actual_schemas = {
        _relative(path)
        for path in (ROOT / "ops" / "schemas").glob("*.schema.json")
    }
    unregistered_schemas = sorted(actual_schemas - contract_schemas)
    missing_schema_files = sorted(contract_schemas - actual_schemas)

    from tools import runtime_capabilities

    runtime_descriptors = {
        capability_id
        for capability_id, item in value["logicalCapabilities"].items()
        if item["availabilityClass"] == "runtime-observed"
    }
    runtime_capability_mismatch = sorted(
        runtime_descriptors.symmetric_difference(runtime_capabilities.CAPABILITIES)
    )
    provider_mismatch = sorted(
        set(value["providerProfiles"]).symmetric_difference(runtime_capabilities.PROVIDERS)
    )

    findings = {
        "registryErrors": registry_errors,
        "missingEntrypointComponents": missing_components,
        "missingEntrypointBindings": missing_bindings,
        "missingWorkflowBindings": missing_workflows,
        "orphanedWorkflowBindings": orphaned_workflow_bindings,
        "unregisteredSchemas": unregistered_schemas,
        "missingSchemaFiles": missing_schema_files,
        "runtimeCapabilityMismatch": runtime_capability_mismatch,
        "providerProfileMismatch": provider_mismatch,
        "invalidExclusions": invalid_exclusions,
    }
    counts = {
        "concepts": len(value.get("concepts", {})),
        "contracts": len(value.get("contracts", {})),
        "authorities": len(value.get("managedAuthorities", {})),
        "resources": len(value.get("resources", {})),
        "components": len(components),
        "logicalCapabilities": len(value.get("logicalCapabilities", {})),
        "providerProfiles": len(value.get("providerProfiles", {})),
        "toolSurfaces": len(value.get("toolSurfaces", {})),
        "entrypoints": len(entrypoints),
        "workflows": len(workflows),
        "exclusions": len(exclusions),
    }
    core = {
        "schemaVersion": SCHEMA_VERSION,
        "operationalSemanticsHash": stable_hash(value),
        "catalogCounts": counts,
        "findings": findings,
        "coverageComplete": not any(findings.values()),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "inspectionHash": stable_hash(core)}


def validate_inspection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("OPERATIONAL_SEMANTICS_COVERAGE_INVALID")
    required = {
        "schemaVersion",
        "operationalSemanticsHash",
        "catalogCounts",
        "findings",
        "coverageComplete",
        "readOnly",
        "semanticAuthority",
        "authorizesMutation",
        "inspectionHash",
    }
    if set(value) != required:
        raise RuntimeError("OPERATIONAL_SEMANTICS_COVERAGE_FIELDS_INVALID")
    if value.get("schemaVersion") != SCHEMA_VERSION:
        raise RuntimeError("OPERATIONAL_SEMANTICS_COVERAGE_SCHEMA_UNSUPPORTED")
    findings = value.get("findings")
    if not isinstance(findings, dict) or set(findings) != FINDING_FIELDS:
        raise RuntimeError("OPERATIONAL_SEMANTICS_COVERAGE_FINDINGS_INVALID")
    for field in FINDING_FIELDS:
        items = findings.get(field)
        if (
            not isinstance(items, list)
            or not all(isinstance(item, str) and item for item in items)
            or items != sorted(set(items))
        ):
            raise RuntimeError("OPERATIONAL_SEMANTICS_COVERAGE_FINDING_LIST_INVALID")
    expected = build_inspection()
    if value != expected:
        raise RuntimeError("OPERATIONAL_SEMANTICS_COVERAGE_MISMATCH")
    return value
