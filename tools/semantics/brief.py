from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from tools import runtime_capabilities
from tools.canonical import stable_hash
from tools.semantics.coverage import build_inspection as build_semantic_coverage
from tools.semantics.foundations import contract as foundation_contract
from tools.semantics.maxims import load_catalog, validate_catalog
from tools.semantics.registry import ROOT, load_registry, validate_registry

BRIEF_SCHEMA = "AgentSemanticBrief 0.1"
CONTEXT_SCHEMA = "AgentSemanticContext 0.1"
PROJECTION_SCHEMA = "CapabilityRelevanceProjection 0.1"
FRESHNESS_SCHEMA = "CapabilityDiscoveryFreshness 0.1"
ROLE_DIR = ROOT / "docs" / "kickstarts" / "roles"
CURRENT_TARGET_RE = re.compile(r"\]\(\./([A-Za-z0-9._-]+-v[A-Za-z0-9._-]+\.md)\)")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
BRIEF_FIELDS = {
    "schemaVersion", "context", "inputs", "capabilityProjection", "maxims",
    "readOnly", "semanticAuthority", "authorizesMutation", "briefHash",
}
CONTEXT_FIELDS = {
    "schemaVersion", "role", "declaredIntent", "lifecyclePhase",
    "objects", "operations", "scope",
}
PROJECTION_FIELDS = {
    "schemaVersion", "inventoryCount", "selectedCount", "omittedCount",
    "required", "relevantAvailable", "conditional", "requiredUnavailable",
    "missingCoverage",
}
INPUT_FIELDS = {
    "contextHash", "operationalSemanticsHash", "operationalSemanticsCoverageHash",
    "maximsCatalogHash", "runtimeCapabilityInspectionHash", "roleContractRefs",
}


def _sorted_unique(values: Any, code: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(values, list):
        raise RuntimeError(code)
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise RuntimeError(code)
    normalized = sorted(item.strip() for item in values)
    if len(normalized) != len(set(normalized)) or (not allow_empty and not normalized):
        raise RuntimeError(code)
    return normalized


def normalize_context(
    *,
    role: str,
    declared_intent: str,
    lifecycle_phase: str,
    objects: list[str],
    operations: list[str],
    scopes: list[str],
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    value = load_registry() if registry is None else registry
    errors = validate_registry(value)
    if errors:
        raise RuntimeError(errors[0])
    vocab = value["facetVocabulary"]
    fields = {
        "role": (role, "roles", "AGENT_SEMANTIC_CONTEXT_ROLE_INVALID"),
        "declaredIntent": (declared_intent, "intentClasses", "AGENT_SEMANTIC_CONTEXT_INTENT_INVALID"),
        "lifecyclePhase": (lifecycle_phase, "lifecyclePhases", "AGENT_SEMANTIC_CONTEXT_LIFECYCLE_INVALID"),
    }
    normalized: dict[str, Any] = {"schemaVersion": CONTEXT_SCHEMA}
    for output, (raw, vocab_key, code) in fields.items():
        if not isinstance(raw, str) or raw not in vocab[vocab_key]:
            raise RuntimeError(code)
        normalized[output] = raw
    for output, raw, vocab_key, code in (
        ("objects", objects, "objects", "AGENT_SEMANTIC_CONTEXT_OBJECTS_INVALID"),
        ("operations", operations, "operations", "AGENT_SEMANTIC_CONTEXT_OPERATIONS_INVALID"),
        ("scope", scopes, "scopes", "AGENT_SEMANTIC_CONTEXT_SCOPE_INVALID"),
    ):
        items = _sorted_unique(raw, code)
        unknown = sorted(set(items) - set(vocab[vocab_key]))
        if unknown:
            raise RuntimeError(f"{code}:{unknown[0]}")
        normalized[output] = items
    return normalized


def validate_context(value: Any, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != CONTEXT_FIELDS:
        raise RuntimeError("AGENT_SEMANTIC_CONTEXT_FIELDS_INVALID")
    if value.get("schemaVersion") != CONTEXT_SCHEMA:
        raise RuntimeError("AGENT_SEMANTIC_CONTEXT_SCHEMA_UNSUPPORTED")
    expected = normalize_context(
        role=value.get("role"),
        declared_intent=value.get("declaredIntent"),
        lifecycle_phase=value.get("lifecyclePhase"),
        objects=value.get("objects"),
        operations=value.get("operations"),
        scopes=value.get("scope"),
        registry=registry,
    )
    if value != expected:
        raise RuntimeError("AGENT_SEMANTIC_CONTEXT_NOT_NORMALIZED")
    return value


def _required_policy(registry: dict[str, Any]) -> dict[str, list[str]]:
    contract = foundation_contract("capability-relevance-projection")
    policy = contract["invariants"].get("requiredCapabilitiesByIntent")
    if not isinstance(policy, dict):
        raise RuntimeError("CAPABILITY_RELEVANCE_REQUIRED_POLICY_MISSING")
    intents = registry["facetVocabulary"]["intentClasses"]
    if set(policy) != set(intents):
        raise RuntimeError("CAPABILITY_RELEVANCE_REQUIRED_POLICY_COVERAGE_INVALID")
    return {key: list(policy[key]) for key in sorted(policy)}


def _facet_match(item: dict[str, Any], context: dict[str, Any]) -> bool:
    facets = item["facets"]
    return (
        context["role"] in facets["roles"]
        and context["declaredIntent"] in facets["intentClasses"]
        and context["lifecyclePhase"] in facets["lifecyclePhases"]
        and bool(set(context["objects"]) & set(facets["objects"]))
        and bool(set(context["operations"]) & set(facets["operations"]))
    )


def _required_visible(
    capability_id: str,
    item: dict[str, Any],
    context: dict[str, Any],
) -> bool:
    facets = item["facets"]
    return (
        context["role"] in facets["roles"]
        and context["declaredIntent"] in facets["intentClasses"]
        and context["lifecyclePhase"] in facets["lifecyclePhases"]
    )


def _availability(
    capability_id: str,
    item: dict[str, Any],
    context: dict[str, Any],
    runtime: dict[str, Any],
    semantic_coverage: dict[str, Any],
) -> tuple[str, str]:
    missing_scopes = sorted(set(item["requiredScopes"]) - set(context["scope"]))
    if missing_scopes:
        return "UNAVAILABLE", f"MISSING_SCOPE:{missing_scopes[0]}"
    if item["preconditions"]:
        return "CONDITIONAL", f"PRECONDITION_REQUIRED:{item['preconditions'][0]}"
    kind = item["availabilityClass"]
    if kind == "contextual":
        return "CONDITIONAL", "CONTEXTUAL_CAPABILITY"
    if kind == "repository-static":
        if semantic_coverage.get("coverageComplete") is True:
            return "AVAILABLE", "SEMANTIC_COVERAGE_COMPLETE"
        return "UNAVAILABLE", "SEMANTIC_COVERAGE_INCOMPLETE"
    if kind != "runtime-observed":
        return "UNAVAILABLE", "AVAILABILITY_CLASS_UNKNOWN"
    observed = runtime["capabilities"].get(capability_id)
    if not isinstance(observed, dict):
        return "UNAVAILABLE", "RUNTIME_CAPABILITY_NOT_OBSERVED"
    status = observed.get("status")
    if status == "PASS":
        return "AVAILABLE", str(observed.get("reasonCode") or "CAPABILITY_SATISFIED")
    if status == "UNKNOWN":
        return "UNAVAILABLE", str(observed.get("reasonCode") or "CAPABILITY_UNKNOWN")
    return "UNAVAILABLE", str(observed.get("reasonCode") or "CAPABILITY_FAILED")


def build_projection(
    context: dict[str, Any],
    runtime_inspection: dict[str, Any],
    *,
    registry: dict[str, Any] | None = None,
    semantic_coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    value = load_registry() if registry is None else registry
    errors = validate_registry(value)
    if errors:
        raise RuntimeError(errors[0])
    validate_context(context, value)
    runtime_capabilities.validate_inspection(runtime_inspection)
    coverage = build_semantic_coverage(value) if semantic_coverage is None else semantic_coverage
    if coverage.get("operationalSemanticsHash") != stable_hash(value):
        raise RuntimeError("CAPABILITY_RELEVANCE_COVERAGE_REGISTRY_MISMATCH")

    required_policy = _required_policy(value)
    required_ids = required_policy[context["declaredIntent"]]
    capabilities = value["logicalCapabilities"]
    missing_coverage: list[str] = []
    selected: set[str] = set()
    required: list[str] = []
    for capability_id in required_ids:
        item = capabilities.get(capability_id)
        if not isinstance(item, dict):
            missing_coverage.append(f"REQUIRED_CAPABILITY_UNKNOWN:{capability_id}")
            continue
        if not _required_visible(capability_id, item, context):
            missing_coverage.append(f"REQUIRED_CAPABILITY_CONTEXT_MISMATCH:{capability_id}")
            continue
        selected.add(capability_id)
        required.append(capability_id)
    for capability_id, item in capabilities.items():
        if _facet_match(item, context):
            selected.add(capability_id)

    relevant_available: list[str] = []
    conditional: list[str] = []
    required_unavailable: list[str] = []
    required_set = set(required)
    for capability_id in sorted(selected):
        item = capabilities[capability_id]
        status, _reason = _availability(
            capability_id, item, context, runtime_inspection, coverage
        )
        if status == "AVAILABLE":
            relevant_available.append(capability_id)
        elif status == "CONDITIONAL":
            conditional.append(capability_id)
        elif capability_id in required_set:
            required_unavailable.append(capability_id)
        else:
            # The 0.1 contract has no separate relevantUnavailable bucket.
            # Keep a relevant but currently unavailable capability visible as conditional
            # rather than letting selectedCount hide it.
            conditional.append(capability_id)

    inventory_count = len(capabilities)
    selected_count = len(selected)
    projection = {
        "schemaVersion": PROJECTION_SCHEMA,
        "inventoryCount": inventory_count,
        "selectedCount": selected_count,
        "omittedCount": inventory_count - selected_count,
        "required": sorted(required),
        "relevantAvailable": sorted(relevant_available),
        "conditional": sorted(conditional),
        "requiredUnavailable": sorted(required_unavailable),
        "missingCoverage": sorted(missing_coverage),
    }
    validate_projection(projection)
    return projection


def validate_projection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != PROJECTION_FIELDS:
        raise RuntimeError("CAPABILITY_RELEVANCE_PROJECTION_FIELDS_INVALID")
    if value.get("schemaVersion") != PROJECTION_SCHEMA:
        raise RuntimeError("CAPABILITY_RELEVANCE_PROJECTION_SCHEMA_UNSUPPORTED")
    for field in ("required", "relevantAvailable", "conditional", "requiredUnavailable", "missingCoverage"):
        normalized = _sorted_unique(value.get(field), "CAPABILITY_RELEVANCE_PROJECTION_LIST_INVALID", allow_empty=True)
        if value[field] != normalized:
            raise RuntimeError("CAPABILITY_RELEVANCE_PROJECTION_NOT_NORMALIZED")
    for field in ("inventoryCount", "selectedCount", "omittedCount"):
        if type(value.get(field)) is not int or value[field] < 0:
            raise RuntimeError("CAPABILITY_RELEVANCE_PROJECTION_COUNT_INVALID")
    if value["inventoryCount"] != value["selectedCount"] + value["omittedCount"]:
        raise RuntimeError("CAPABILITY_RELEVANCE_PROJECTION_COUNT_MISMATCH")
    if not set(value["requiredUnavailable"]).issubset(set(value["required"])):
        raise RuntimeError("CAPABILITY_RELEVANCE_REQUIRED_UNAVAILABLE_NOT_REQUIRED")
    return value


def resolve_role_contract_refs(role: str) -> list[dict[str, str]]:
    current = ROLE_DIR / f"{role}-current.md"
    try:
        current_text = current.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError("AGENT_SEMANTIC_ROLE_CONTRACT_CURRENT_MISSING") from exc
    targets = CURRENT_TARGET_RE.findall(current_text)
    if len(targets) != 1:
        raise RuntimeError("AGENT_SEMANTIC_ROLE_CONTRACT_POINTER_INVALID")
    target = current.parent / targets[0]
    try:
        target_text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError("AGENT_SEMANTIC_ROLE_CONTRACT_TARGET_MISSING") from exc
    refs = [
        {"path": str(current.relative_to(ROOT)).replace("\\", "/"), "contentHash": hashlib.sha256(current_text.encode("utf-8")).hexdigest()},
        {"path": str(target.relative_to(ROOT)).replace("\\", "/"), "contentHash": hashlib.sha256(target_text.encode("utf-8")).hexdigest()},
    ]
    return sorted(refs, key=lambda item: item["path"])


def _selected_objects(
    projection: dict[str, Any], registry: dict[str, Any], context: dict[str, Any]
) -> tuple[set[str], set[str]]:
    selected_ids = (
        set(projection["required"])
        | set(projection["relevantAvailable"])
        | set(projection["conditional"])
        | set(projection["requiredUnavailable"])
    )
    blocked_ids = set(projection["conditional"]) | set(projection["requiredUnavailable"])
    selected_objects = set(context["objects"])
    blocked_objects: set[str] = set()
    for capability_id in selected_ids:
        selected_objects.update(registry["logicalCapabilities"][capability_id]["facets"]["objects"])
    for capability_id in blocked_ids:
        blocked_objects.update(registry["logicalCapabilities"][capability_id]["facets"]["objects"])
    return selected_objects, blocked_objects


def select_maxims(
    projection: dict[str, Any],
    context: dict[str, Any],
    *,
    registry: dict[str, Any],
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    errors = validate_catalog(catalog)
    if errors:
        raise RuntimeError(errors[0])
    selected_objects, blocked_objects = _selected_objects(projection, registry, context)
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for maxim_id, item in catalog["items"].items():
        applies = set(item["appliesTo"])
        if not (applies & selected_objects):
            continue
        priority = 0 if applies & blocked_objects else 1
        candidates.append((priority, maxim_id, item))
    return [deepcopy(item) for _, _, item in sorted(candidates)[:3]]


def _validate_hash(value: Any, code: str) -> str:
    if not isinstance(value, str) or not HEX64_RE.fullmatch(value):
        raise RuntimeError(code)
    return value


def _validate_role_refs(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) != 2:
        raise RuntimeError("AGENT_SEMANTIC_ROLE_REFS_INVALID")
    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"path", "contentHash"}:
            raise RuntimeError("AGENT_SEMANTIC_ROLE_REF_FIELDS_INVALID")
        path = item.get("path")
        if not isinstance(path, str) or not path:
            raise RuntimeError("AGENT_SEMANTIC_ROLE_REF_PATH_INVALID")
        normalized.append({"path": path, "contentHash": _validate_hash(item.get("contentHash"), "AGENT_SEMANTIC_ROLE_REF_HASH_INVALID")})
    if value != sorted(normalized, key=lambda item: item["path"]):
        raise RuntimeError("AGENT_SEMANTIC_ROLE_REFS_NOT_NORMALIZED")
    return normalized


def build_brief(
    context: dict[str, Any],
    runtime_inspection: dict[str, Any],
    *,
    registry: dict[str, Any] | None = None,
    semantic_coverage: dict[str, Any] | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    value = load_registry() if registry is None else registry
    errors = validate_registry(value)
    if errors:
        raise RuntimeError(errors[0])
    validate_context(context, value)
    runtime_capabilities.validate_inspection(runtime_inspection)
    coverage = build_semantic_coverage(value) if semantic_coverage is None else semantic_coverage
    maxims = load_catalog() if catalog is None else catalog
    catalog_errors = validate_catalog(maxims)
    if catalog_errors:
        raise RuntimeError(catalog_errors[0])

    projection = build_projection(
        context, runtime_inspection, registry=value, semantic_coverage=coverage
    )
    role_refs = resolve_role_contract_refs(context["role"])
    body = {
        "schemaVersion": BRIEF_SCHEMA,
        "context": deepcopy(context),
        "inputs": {
            "contextHash": stable_hash(context),
            "operationalSemanticsHash": stable_hash(value),
            "operationalSemanticsCoverageHash": coverage["inspectionHash"],
            "maximsCatalogHash": stable_hash(maxims),
            "runtimeCapabilityInspectionHash": runtime_inspection["inspectionHash"],
            "roleContractRefs": role_refs,
        },
        "capabilityProjection": projection,
        "maxims": select_maxims(projection, context, registry=value, catalog=maxims),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    result = {**body, "briefHash": stable_hash(body)}
    validate_brief(result)
    return result


def validate_brief(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != BRIEF_FIELDS:
        raise RuntimeError("AGENT_SEMANTIC_BRIEF_FIELDS_INVALID")
    if value.get("schemaVersion") != BRIEF_SCHEMA:
        raise RuntimeError("AGENT_SEMANTIC_BRIEF_SCHEMA_UNSUPPORTED")
    if value.get("readOnly") is not True or value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise RuntimeError("AGENT_SEMANTIC_BRIEF_BOUNDARY_INVALID")
    validate_context(value.get("context"))
    inputs = value.get("inputs")
    if not isinstance(inputs, dict) or set(inputs) != INPUT_FIELDS:
        raise RuntimeError("AGENT_SEMANTIC_BRIEF_INPUT_FIELDS_INVALID")
    for field in INPUT_FIELDS - {"roleContractRefs"}:
        _validate_hash(inputs.get(field), f"AGENT_SEMANTIC_BRIEF_INPUT_HASH_INVALID:{field}")
    _validate_role_refs(inputs.get("roleContractRefs"))
    if inputs["contextHash"] != stable_hash(value["context"]):
        raise RuntimeError("AGENT_SEMANTIC_BRIEF_CONTEXT_HASH_MISMATCH")
    validate_projection(value.get("capabilityProjection"))
    maxims = value.get("maxims")
    if not isinstance(maxims, list) or len(maxims) > 3:
        raise RuntimeError("AGENT_SEMANTIC_BRIEF_MAXIMS_INVALID")
    for item in maxims:
        if not isinstance(item, dict) or item.get("semanticAuthority") is not False or item.get("authorizesMutation") is not False or item.get("overridesContract") is not False:
            raise RuntimeError("AGENT_SEMANTIC_BRIEF_MAXIM_BOUNDARY_INVALID")
    body = {key: deepcopy(item) for key, item in value.items() if key != "briefHash"}
    if _validate_hash(value.get("briefHash"), "AGENT_SEMANTIC_BRIEF_HASH_INVALID") != stable_hash(body):
        raise RuntimeError("AGENT_SEMANTIC_BRIEF_HASH_MISMATCH")
    return value


def inspect_freshness(
    value: dict[str, Any],
    runtime_inspection: dict[str, Any],
) -> dict[str, Any]:
    try:
        validate_brief(value)
    except RuntimeError as exc:
        return {
            "schemaVersion": FRESHNESS_SCHEMA,
            "status": "TAMPERED",
            "reasonCodes": [str(exc).split(":", 1)[0]],
            "briefHash": value.get("briefHash") if isinstance(value, dict) else None,
            "readOnly": True,
            "semanticAuthority": False,
        }
    current = build_brief(value["context"], runtime_inspection)
    stale_fields = [
        field
        for field in sorted(INPUT_FIELDS)
        if value["inputs"].get(field) != current["inputs"].get(field)
    ]
    if stale_fields:
        return {
            "schemaVersion": FRESHNESS_SCHEMA,
            "status": "STALE",
            "reasonCodes": [f"INPUT_CHANGED:{field}" for field in stale_fields],
            "briefHash": value["briefHash"],
            "readOnly": True,
            "semanticAuthority": False,
        }
    if value != current:
        return {
            "schemaVersion": FRESHNESS_SCHEMA,
            "status": "TAMPERED",
            "reasonCodes": ["DERIVATION_MISMATCH"],
            "briefHash": value["briefHash"],
            "readOnly": True,
            "semanticAuthority": False,
        }
    return {
        "schemaVersion": FRESHNESS_SCHEMA,
        "status": "FRESH",
        "reasonCodes": [],
        "briefHash": value["briefHash"],
        "readOnly": True,
        "semanticAuthority": False,
    }
