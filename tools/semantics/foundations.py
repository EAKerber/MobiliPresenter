from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from tools.semantics.registry import ROOT, load_registry

FOUNDATIONS_PATH = ROOT / "ops" / "semantics" / "foundations.json"
SCHEMA_VERSION = "SemanticFoundations 0.1"
TOP_FIELDS = {
    "schemaVersion", "readOnly", "semanticAuthority", "authorizesMutation",
    "technicalDictionary", "determinismPolicy", "artifactContracts", "freshnessContract",
}
DICTIONARY_TERMS = {
    "Authority", "CoordinationIntent", "DeclaredIntent", "EcosystemCapability",
    "LogicalCapability", "Maxim", "Projection", "Provider", "Role", "ToolSurface",
}
ARTIFACT_IDS = {"agent-semantic-brief", "capability-relevance-projection", "ecosystem-maxim"}
DETERMINISM_CLASSES = {
    "factual-deterministic", "policy-deterministic", "non-authoritative-recommendation",
}
FORBIDDEN_HEURISTIC_TARGETS = {
    "authority", "availability", "eligibility", "mutationPermission", "scope",
}
REQUIRED_CAPABILITY_BUCKETS = {
    "conditional", "relevantAvailable", "required", "requiredUnavailable",
}
REQUIRED_FRESHNESS_INPUTS = {
    "context", "maximsCatalogHash", "operationalSemanticsCoverageHash",
    "operationalSemanticsHash", "roleContractRefs", "runtimeCapabilityInspectionHash",
}


def load_foundations(path: Path = FOUNDATIONS_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"SEMANTIC_FOUNDATIONS_MISSING:{path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"SEMANTIC_FOUNDATIONS_JSON_INVALID:{exc.lineno}:{exc.colno}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("SEMANTIC_FOUNDATIONS_ROOT_INVALID")
    return value


def _unique_strings(value: Any, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(isinstance(item, str) and item for item in value)
        and len(value) == len(set(value))
    )


def _validate_dictionary(value: Any, registry: dict[str, Any], errors: list[str]) -> None:
    if not isinstance(value, dict) or set(value) != DICTIONARY_TERMS:
        errors.append("SEMANTIC_FOUNDATIONS_DICTIONARY_COVERAGE_INVALID")
        return
    if list(value) != sorted(value):
        errors.append("SEMANTIC_FOUNDATIONS_DICTIONARY_NOT_SORTED")
    seen_ids: set[str] = set()
    for item in value.values():
        if not isinstance(item, dict) or set(item) != {"semanticId", "definition"}:
            errors.append("SEMANTIC_FOUNDATIONS_DICTIONARY_ENTRY_INVALID")
            continue
        semantic_id = item.get("semanticId")
        if not isinstance(semantic_id, str) or semantic_id not in registry.get("concepts", {}):
            errors.append("SEMANTIC_FOUNDATIONS_DICTIONARY_CONCEPT_UNKNOWN")
        elif semantic_id in seen_ids:
            errors.append("SEMANTIC_FOUNDATIONS_DICTIONARY_CONCEPT_DUPLICATE")
        else:
            seen_ids.add(semantic_id)
        if not isinstance(item.get("definition"), str) or not item["definition"].strip():
            errors.append("SEMANTIC_FOUNDATIONS_DICTIONARY_DEFINITION_INVALID")


def _validate_classifications(contract: dict[str, Any], errors: list[str]) -> None:
    inventory = contract.get("fieldInventory")
    classifications = contract.get("fieldClassifications")
    if not _unique_strings(inventory) or inventory != sorted(inventory):
        errors.append("SEMANTIC_FOUNDATIONS_FIELD_INVENTORY_INVALID")
        return
    if not isinstance(classifications, dict) or set(classifications) != DETERMINISM_CLASSES:
        errors.append("SEMANTIC_FOUNDATIONS_FIELD_CLASSIFICATIONS_INVALID")
        return
    classified: list[str] = []
    for name in sorted(DETERMINISM_CLASSES):
        fields = classifications.get(name)
        if not _unique_strings(fields, allow_empty=True) or fields != sorted(fields):
            errors.append("SEMANTIC_FOUNDATIONS_FIELD_CLASS_INVALID")
            continue
        classified.extend(fields)
    if len(classified) != len(set(classified)):
        errors.append("SEMANTIC_FOUNDATIONS_FIELD_CLASS_OVERLAP")
    if set(classified) != set(inventory):
        errors.append("SEMANTIC_FOUNDATIONS_FIELD_CLASS_COVERAGE_INVALID")


def _validate_relevance_policy(invariants: dict[str, Any], registry: dict[str, Any], errors: list[str]) -> None:
    if set(invariants.get("requiredBuckets") or []) != REQUIRED_CAPABILITY_BUCKETS:
        errors.append("SEMANTIC_FOUNDATIONS_CAPABILITY_BUCKETS_INVALID")
    if invariants.get("requiredCapabilityMustRemainVisible") is not True:
        errors.append("SEMANTIC_FOUNDATIONS_REQUIRED_CAPABILITY_VISIBILITY_INVALID")
    if invariants.get("inventoryCountMustEqualSelectedPlusOmitted") is not True:
        errors.append("SEMANTIC_FOUNDATIONS_COVERAGE_COUNT_INVALID")
    if invariants.get("unknownAvailabilityMustNotPass") is not True:
        errors.append("SEMANTIC_FOUNDATIONS_UNKNOWN_AVAILABILITY_INVALID")
    if invariants.get("defaultIntentRelevance") != "relevant":
        errors.append("SEMANTIC_FOUNDATIONS_DEFAULT_RELEVANCE_INVALID")
    policy = invariants.get("requiredCapabilitiesByIntent")
    intents = registry.get("facetVocabulary", {}).get("intentClasses", [])
    capabilities = registry.get("logicalCapabilities", {})
    if not isinstance(policy, dict) or set(policy) != set(intents):
        errors.append("SEMANTIC_FOUNDATIONS_REQUIRED_POLICY_COVERAGE_INVALID")
        return
    for intent in sorted(policy):
        ids = policy[intent]
        if not _unique_strings(ids, allow_empty=True) or ids != sorted(ids):
            errors.append(f"SEMANTIC_FOUNDATIONS_REQUIRED_POLICY_INVALID:{intent}")
            continue
        for capability_id in ids:
            item = capabilities.get(capability_id)
            if not isinstance(item, dict):
                errors.append(f"SEMANTIC_FOUNDATIONS_REQUIRED_CAPABILITY_UNKNOWN:{capability_id}")
                continue
            if intent not in item.get("facets", {}).get("intentClasses", []):
                errors.append(f"SEMANTIC_FOUNDATIONS_REQUIRED_CAPABILITY_INTENT_MISMATCH:{capability_id}:{intent}")


def _validate_artifacts(value: Any, registry: dict[str, Any], errors: list[str]) -> None:
    if not isinstance(value, dict) or set(value) != ARTIFACT_IDS:
        errors.append("SEMANTIC_FOUNDATIONS_ARTIFACT_COVERAGE_INVALID")
        return
    if list(value) != sorted(value):
        errors.append("SEMANTIC_FOUNDATIONS_ARTIFACTS_NOT_SORTED")
    for artifact_id, contract in value.items():
        if not isinstance(contract, dict) or set(contract) != {
            "schemaVersion", "kind", "fieldInventory", "fieldClassifications", "invariants"
        }:
            errors.append("SEMANTIC_FOUNDATIONS_ARTIFACT_CONTRACT_INVALID")
            continue
        if not isinstance(contract.get("schemaVersion"), str) or not contract["schemaVersion"].endswith(" 0.1"):
            errors.append("SEMANTIC_FOUNDATIONS_ARTIFACT_VERSION_INVALID")
        if contract.get("kind") not in {"projection", "recommendation"}:
            errors.append("SEMANTIC_FOUNDATIONS_ARTIFACT_KIND_INVALID")
        _validate_classifications(contract, errors)
        invariants = contract.get("invariants")
        if not isinstance(invariants, dict) or not invariants:
            errors.append("SEMANTIC_FOUNDATIONS_ARTIFACT_INVARIANTS_INVALID")
            continue
        if artifact_id in {"agent-semantic-brief", "ecosystem-maxim"}:
            if invariants.get("semanticAuthority") is not False:
                errors.append("SEMANTIC_FOUNDATIONS_SEMANTIC_AUTHORITY_FORBIDDEN")
            if invariants.get("authorizesMutation") is not False:
                errors.append("SEMANTIC_FOUNDATIONS_MUTATION_AUTHORITY_FORBIDDEN")
        if artifact_id == "agent-semantic-brief" and invariants.get("maximsMaximum") != 3:
            errors.append("SEMANTIC_FOUNDATIONS_MAXIM_SELECTION_LIMIT_INVALID")
        if artifact_id == "ecosystem-maxim" and invariants.get("overridesContract") is not False:
            errors.append("SEMANTIC_FOUNDATIONS_MAXIM_OVERRIDE_FORBIDDEN")
        if artifact_id == "capability-relevance-projection":
            _validate_relevance_policy(invariants, registry, errors)


def validate_foundations(value: dict[str, Any] | None = None) -> list[str]:
    foundations = load_foundations() if value is None else value
    errors: list[str] = []
    if not isinstance(foundations, dict) or set(foundations) != TOP_FIELDS:
        return ["SEMANTIC_FOUNDATIONS_FIELDS_INVALID"]
    if foundations.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("SEMANTIC_FOUNDATIONS_SCHEMA_UNSUPPORTED")
    if foundations.get("readOnly") is not True:
        errors.append("SEMANTIC_FOUNDATIONS_READ_ONLY_REQUIRED")
    if foundations.get("semanticAuthority") is not False:
        errors.append("SEMANTIC_FOUNDATIONS_SEMANTIC_AUTHORITY_FORBIDDEN")
    if foundations.get("authorizesMutation") is not False:
        errors.append("SEMANTIC_FOUNDATIONS_MUTATION_AUTHORITY_FORBIDDEN")

    registry = load_registry()
    _validate_dictionary(foundations.get("technicalDictionary"), registry, errors)

    policy = foundations.get("determinismPolicy")
    if not isinstance(policy, dict) or set(policy) != {
        "classes", "heuristicMayInfluence", "heuristicMustNotInfluence", "unknownNeverEqualsPass"
    }:
        errors.append("SEMANTIC_FOUNDATIONS_DETERMINISM_POLICY_INVALID")
    else:
        if set(policy.get("classes") or []) != DETERMINISM_CLASSES:
            errors.append("SEMANTIC_FOUNDATIONS_DETERMINISM_CLASSES_INVALID")
        if set(policy.get("heuristicMustNotInfluence") or []) != FORBIDDEN_HEURISTIC_TARGETS:
            errors.append("SEMANTIC_FOUNDATIONS_HEURISTIC_BOUNDARY_INVALID")
        if policy.get("heuristicMayInfluence") != ["recommendationOrder"]:
            errors.append("SEMANTIC_FOUNDATIONS_HEURISTIC_SCOPE_INVALID")
        if policy.get("unknownNeverEqualsPass") is not True:
            errors.append("SEMANTIC_FOUNDATIONS_UNKNOWN_POLICY_INVALID")

    _validate_artifacts(foundations.get("artifactContracts"), registry, errors)

    freshness = foundations.get("freshnessContract")
    if not isinstance(freshness, dict) or set(freshness) != {
        "requiredInputs", "invalidationTriggers", "staleRules", "guardId"
    }:
        errors.append("SEMANTIC_FOUNDATIONS_FRESHNESS_CONTRACT_INVALID")
    else:
        for field in ("requiredInputs", "invalidationTriggers", "staleRules"):
            if not _unique_strings(freshness.get(field)):
                errors.append("SEMANTIC_FOUNDATIONS_FRESHNESS_COVERAGE_INVALID")
        if set(freshness.get("requiredInputs") or []) != REQUIRED_FRESHNESS_INPUTS:
            errors.append("SEMANTIC_FOUNDATIONS_FRESHNESS_INPUTS_INVALID")
        if freshness.get("guardId") != "CAPABILITY_DISCOVERY_FRESHNESS_GUARD":
            errors.append("SEMANTIC_FOUNDATIONS_FRESHNESS_GUARD_INVALID")
    return errors


def contract(artifact_id: str) -> dict[str, Any]:
    foundations = load_foundations()
    errors = validate_foundations(foundations)
    if errors:
        raise RuntimeError(errors[0])
    value = foundations["artifactContracts"].get(artifact_id)
    if value is None:
        raise RuntimeError("SEMANTIC_FOUNDATIONS_ARTIFACT_UNKNOWN")
    return deepcopy(value)
