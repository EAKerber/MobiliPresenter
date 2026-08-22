from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "ops" / "semantics" / "registry.json"
SEMANTIC_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
OWNER_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TOPOLOGY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
READ_ONLY_COMPONENT_KINDS = {
    "inspection",
    "mutation-planner",
    "recommendation",
    "routing-planner",
    "sanitization-planner",
}
COMPONENT_KINDS = READ_ONLY_COMPONENT_KINDS | {"authority-executor", "cli-adapter", "sanitization-executor"}
LOCATOR_KINDS = {"repository-file", "repository-directory", "git-authority", "github-git-refs"}
FACET_FIELDS = {
    "roles",
    "intentClasses",
    "lifecyclePhases",
    "operations",
    "objects",
    "riskClasses",
}
FACET_VOCABULARY_FIELDS = FACET_FIELDS | {"scopes"}
CAPABILITY_FIELDS = {
    "owner",
    "description",
    "availabilityClass",
    "facets",
    "requiredAuthorities",
    "requiredScopes",
    "preconditions",
    "providerRequirements",
    "toolSurfaces",
    "fallbackPolicy",
}
PROVIDER_FIELDS = {"description", "observationClass", "featureVocabulary"}
TOOL_SURFACE_FIELDS = {
    "owner",
    "kind",
    "provider",
    "locator",
    "features",
    "bindings",
    "sideEffects",
}
COVERAGE_POLICY_FIELDS = {"entrypointGlobs", "workflowGlobs", "exclusions"}


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"SEMANTIC_REGISTRY_MISSING:{path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"SEMANTIC_REGISTRY_JSON_INVALID:{exc.lineno}:{exc.colno}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("SEMANTIC_REGISTRY_ROOT_INVALID")
    return value


def _unique_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value) and len(value) == len(set(value))


def _sorted_string_list(value: Any, *, allow_empty: bool = True) -> bool:
    return (
        _unique_string_list(value)
        and (allow_empty or bool(value))
        and value == sorted(value)
    )


def _module_exists(module: str) -> bool:
    if not module.startswith("tools."):
        return False
    relative = Path(*module.split("."))
    return (ROOT / relative).with_suffix(".py").is_file() or (ROOT / relative / "__init__.py").is_file()


def _validate_locator(locator: Any, errors: list[str]) -> None:
    if not isinstance(locator, dict):
        errors.append("SEMANTIC_LOCATOR_INVALID")
        return
    kind = locator.get("kind")
    if kind not in LOCATOR_KINDS:
        errors.append("SEMANTIC_LOCATOR_KIND_INVALID")
        return
    if kind in {"repository-file", "repository-directory"}:
        expected = {"kind", "path"}
        if set(locator) != expected or not isinstance(locator.get("path"), str) or not locator["path"]:
            errors.append("SEMANTIC_LOCATOR_FIELDS_INVALID")
    elif kind == "git-authority":
        expected = {"kind", "branch", "path"}
        if set(locator) != expected or not all(isinstance(locator.get(key), str) and locator[key] for key in ("branch", "path")):
            errors.append("SEMANTIC_LOCATOR_FIELDS_INVALID")
    else:
        expected = {"kind", "repository"}
        if set(locator) != expected or not isinstance(locator.get("repository"), str) or not locator["repository"]:
            errors.append("SEMANTIC_LOCATOR_FIELDS_INVALID")


def _validate_v03_extensions(
    registry: dict[str, Any],
    owners: dict[str, Any],
    authorities: dict[str, Any],
    components: dict[str, Any],
    errors: list[str],
) -> None:
    vocabulary = registry.get("facetVocabulary")
    if not isinstance(vocabulary, dict) or set(vocabulary) != FACET_VOCABULARY_FIELDS:
        errors.append("SEMANTIC_FACET_VOCABULARY_INVALID")
        vocabulary = {key: [] for key in FACET_VOCABULARY_FIELDS}
    for field in FACET_VOCABULARY_FIELDS:
        if not _sorted_string_list(vocabulary.get(field), allow_empty=False):
            errors.append(f"SEMANTIC_FACET_{field.upper()}_INVALID")

    providers = registry.get("providerProfiles")
    if not isinstance(providers, dict) or not providers:
        errors.append("SEMANTIC_PROVIDER_PROFILES_INVALID")
        providers = {}
    if list(providers) != sorted(providers):
        errors.append("SEMANTIC_PROVIDER_PROFILES_NOT_SORTED")
    for provider_id, item in providers.items():
        if not TOPOLOGY_ID_RE.fullmatch(str(provider_id)):
            errors.append("SEMANTIC_PROVIDER_ID_INVALID")
        if not isinstance(item, dict) or set(item) != PROVIDER_FIELDS:
            errors.append("SEMANTIC_PROVIDER_FIELDS_INVALID")
            continue
        if not isinstance(item.get("description"), str) or not item["description"].strip():
            errors.append("SEMANTIC_PROVIDER_DESCRIPTION_INVALID")
        if item.get("observationClass") not in {"artifact", "connected", "local", "workflow"}:
            errors.append("SEMANTIC_PROVIDER_OBSERVATION_CLASS_INVALID")
        if not _sorted_string_list(item.get("featureVocabulary"), allow_empty=False):
            errors.append("SEMANTIC_PROVIDER_FEATURES_INVALID")

    capabilities = registry.get("logicalCapabilities")
    if not isinstance(capabilities, dict) or not capabilities:
        errors.append("SEMANTIC_LOGICAL_CAPABILITIES_INVALID")
        capabilities = {}
    if list(capabilities) != sorted(capabilities):
        errors.append("SEMANTIC_LOGICAL_CAPABILITIES_NOT_SORTED")
    for capability_id, item in capabilities.items():
        if not SEMANTIC_ID_RE.fullmatch(str(capability_id)):
            errors.append("SEMANTIC_LOGICAL_CAPABILITY_ID_INVALID")
        if not isinstance(item, dict) or set(item) != CAPABILITY_FIELDS:
            errors.append("SEMANTIC_LOGICAL_CAPABILITY_FIELDS_INVALID")
            continue
        if item.get("owner") not in owners:
            errors.append("SEMANTIC_LOGICAL_CAPABILITY_OWNER_UNKNOWN")
        if not isinstance(item.get("description"), str) or not item["description"].strip():
            errors.append("SEMANTIC_LOGICAL_CAPABILITY_DESCRIPTION_INVALID")
        availability = item.get("availabilityClass")
        if availability not in {"contextual", "repository-static", "runtime-observed"}:
            errors.append("SEMANTIC_LOGICAL_CAPABILITY_AVAILABILITY_INVALID")
        facets = item.get("facets")
        if not isinstance(facets, dict) or set(facets) != FACET_FIELDS:
            errors.append("SEMANTIC_LOGICAL_CAPABILITY_FACETS_INVALID")
            facets = {key: [] for key in FACET_FIELDS}
        for field in FACET_FIELDS:
            values = facets.get(field)
            if not _sorted_string_list(values, allow_empty=False):
                errors.append("SEMANTIC_LOGICAL_CAPABILITY_FACET_VALUES_INVALID")
                continue
            unknown = sorted(set(values) - set(vocabulary.get(field, [])))
            if unknown:
                errors.append(f"SEMANTIC_LOGICAL_CAPABILITY_FACET_UNKNOWN:{field}:{unknown[0]}")
        for field in ("requiredAuthorities", "requiredScopes", "preconditions", "toolSurfaces"):
            if not _sorted_string_list(item.get(field)):
                errors.append(f"SEMANTIC_LOGICAL_CAPABILITY_{field.upper()}_INVALID")
        for authority_id in item.get("requiredAuthorities", []):
            if authority_id not in authorities:
                errors.append("SEMANTIC_LOGICAL_CAPABILITY_AUTHORITY_UNKNOWN")
        for scope in item.get("requiredScopes", []):
            if scope not in vocabulary.get("scopes", []):
                errors.append("SEMANTIC_LOGICAL_CAPABILITY_SCOPE_UNKNOWN")
        requirements = item.get("providerRequirements")
        if not isinstance(requirements, dict) or list(requirements) != sorted(requirements):
            errors.append("SEMANTIC_LOGICAL_CAPABILITY_PROVIDER_REQUIREMENTS_INVALID")
            requirements = {}
        for provider_id, features in requirements.items():
            if provider_id not in providers:
                errors.append("SEMANTIC_LOGICAL_CAPABILITY_PROVIDER_UNKNOWN")
                continue
            if not _sorted_string_list(features, allow_empty=False):
                errors.append("SEMANTIC_LOGICAL_CAPABILITY_PROVIDER_FEATURES_INVALID")
                continue
            if not set(features).issubset(set(providers[provider_id].get("featureVocabulary", []))):
                errors.append("SEMANTIC_LOGICAL_CAPABILITY_PROVIDER_FEATURE_UNKNOWN")
        if availability == "runtime-observed" and not requirements:
            errors.append("SEMANTIC_LOGICAL_CAPABILITY_RUNTIME_REQUIREMENTS_MISSING")
        if availability != "runtime-observed" and requirements:
            errors.append("SEMANTIC_LOGICAL_CAPABILITY_STATIC_PROVIDER_REQUIREMENTS_FORBIDDEN")
        if item.get("fallbackPolicy") not in {"equivalent-only", "forbidden", "not-applicable"}:
            errors.append("SEMANTIC_LOGICAL_CAPABILITY_FALLBACK_INVALID")

    surfaces = registry.get("toolSurfaces")
    if not isinstance(surfaces, dict) or not surfaces:
        errors.append("SEMANTIC_TOOL_SURFACES_INVALID")
        surfaces = {}
    if list(surfaces) != sorted(surfaces):
        errors.append("SEMANTIC_TOOL_SURFACES_NOT_SORTED")
    bound_capabilities: dict[str, set[str]] = {key: set() for key in capabilities}
    used_providers: set[str] = set()
    for surface_id, item in surfaces.items():
        if not TOPOLOGY_ID_RE.fullmatch(str(surface_id)):
            errors.append("SEMANTIC_TOOL_SURFACE_ID_INVALID")
        if not isinstance(item, dict) or set(item) != TOOL_SURFACE_FIELDS:
            errors.append("SEMANTIC_TOOL_SURFACE_FIELDS_INVALID")
            continue
        if item.get("owner") not in owners:
            errors.append("SEMANTIC_TOOL_SURFACE_OWNER_UNKNOWN")
        if item.get("kind") not in {"artifact", "cli", "connector", "workflow"}:
            errors.append("SEMANTIC_TOOL_SURFACE_KIND_INVALID")
        provider_id = item.get("provider")
        if provider_id not in providers:
            errors.append("SEMANTIC_TOOL_SURFACE_PROVIDER_UNKNOWN")
        else:
            used_providers.add(provider_id)
        if not isinstance(item.get("locator"), str) or not item["locator"].strip():
            errors.append("SEMANTIC_TOOL_SURFACE_LOCATOR_INVALID")
        features = item.get("features")
        if not _sorted_string_list(features, allow_empty=False):
            errors.append("SEMANTIC_TOOL_SURFACE_FEATURES_INVALID")
        elif provider_id in providers and not set(features).issubset(
            set(providers[provider_id].get("featureVocabulary", []))
        ):
            errors.append("SEMANTIC_TOOL_SURFACE_FEATURE_UNKNOWN")
        if not isinstance(item.get("sideEffects"), bool):
            errors.append("SEMANTIC_TOOL_SURFACE_SIDE_EFFECTS_INVALID")
        bindings = item.get("bindings")
        if not isinstance(bindings, list) or not bindings:
            errors.append("SEMANTIC_TOOL_SURFACE_BINDINGS_INVALID")
            continue
        identities: set[tuple[str, str]] = set()
        for binding in bindings:
            if not isinstance(binding, dict) or set(binding) != {
                "targetKind",
                "target",
                "capabilities",
            }:
                errors.append("SEMANTIC_TOOL_SURFACE_BINDING_FIELDS_INVALID")
                continue
            target_kind = binding.get("targetKind")
            target = binding.get("target")
            if target_kind not in {"component", "external", "workflow"}:
                errors.append("SEMANTIC_TOOL_SURFACE_TARGET_KIND_INVALID")
            if not isinstance(target, str) or not target.strip():
                errors.append("SEMANTIC_TOOL_SURFACE_TARGET_INVALID")
                continue
            identity = (str(target_kind), target)
            if identity in identities:
                errors.append("SEMANTIC_TOOL_SURFACE_BINDING_DUPLICATE")
            identities.add(identity)
            if target_kind == "component" and target not in components:
                errors.append("SEMANTIC_TOOL_SURFACE_COMPONENT_UNKNOWN")
            capability_ids = binding.get("capabilities")
            if not _sorted_string_list(capability_ids, allow_empty=False):
                errors.append("SEMANTIC_TOOL_SURFACE_CAPABILITIES_INVALID")
                continue
            for capability_id in capability_ids:
                if capability_id not in capabilities:
                    errors.append("SEMANTIC_TOOL_SURFACE_CAPABILITY_UNKNOWN")
                else:
                    bound_capabilities[capability_id].add(surface_id)

    if set(providers) != used_providers:
        for provider_id in sorted(set(providers) - used_providers):
            errors.append(f"SEMANTIC_PROVIDER_ORPHAN:{provider_id}")
    for capability_id, item in capabilities.items():
        declared = set(item.get("toolSurfaces", []))
        unknown = sorted(declared - set(surfaces))
        if unknown:
            errors.append(f"SEMANTIC_LOGICAL_CAPABILITY_TOOL_SURFACE_UNKNOWN:{unknown[0]}")
        if declared != bound_capabilities.get(capability_id, set()):
            errors.append(f"SEMANTIC_LOGICAL_CAPABILITY_SURFACE_BINDING_MISMATCH:{capability_id}")

    coverage = registry.get("coveragePolicy")
    if not isinstance(coverage, dict) or set(coverage) != COVERAGE_POLICY_FIELDS:
        errors.append("SEMANTIC_COVERAGE_POLICY_INVALID")
        return
    for field in ("entrypointGlobs", "workflowGlobs"):
        if not _sorted_string_list(coverage.get(field), allow_empty=False):
            errors.append(f"SEMANTIC_COVERAGE_{field.upper()}_INVALID")
    exclusions = coverage.get("exclusions")
    if not isinstance(exclusions, list):
        errors.append("SEMANTIC_COVERAGE_EXCLUSIONS_INVALID")
        return
    paths: set[str] = set()
    for exclusion in exclusions:
        if not isinstance(exclusion, dict) or set(exclusion) != {
            "path",
            "owner",
            "reason",
            "deathCondition",
        }:
            errors.append("SEMANTIC_COVERAGE_EXCLUSION_FIELDS_INVALID")
            continue
        path = exclusion.get("path")
        if not isinstance(path, str) or not path.strip() or path in paths:
            errors.append("SEMANTIC_COVERAGE_EXCLUSION_PATH_INVALID")
        else:
            paths.add(path)
        if exclusion.get("owner") not in owners:
            errors.append("SEMANTIC_COVERAGE_EXCLUSION_OWNER_UNKNOWN")
        for field in ("reason", "deathCondition"):
            if not isinstance(exclusion.get(field), str) or not exclusion[field].strip():
                errors.append("SEMANTIC_COVERAGE_EXCLUSION_RATIONALE_INVALID")


def validate_registry(value: dict[str, Any] | None = None) -> list[str]:
    registry = load_registry() if value is None else value
    errors: list[str] = []
    expected_top = {
        "schemaVersion",
        "owners",
        "concepts",
        "contracts",
        "branchGrammar",
        "managedAuthorities",
        "resources",
        "components",
        "facetVocabulary",
        "logicalCapabilities",
        "providerProfiles",
        "toolSurfaces",
        "coveragePolicy",
    }
    if set(registry) != expected_top:
        errors.append("SEMANTIC_REGISTRY_FIELDS_INVALID")
    if registry.get("schemaVersion") != "OperationalSemantics 0.3":
        errors.append("SEMANTIC_REGISTRY_SCHEMA_UNSUPPORTED")

    owners = registry.get("owners")
    if not isinstance(owners, dict) or not owners:
        errors.append("SEMANTIC_OWNERS_INVALID")
        owners = {}
    owner_ids = list(owners)
    if owner_ids != sorted(owner_ids):
        errors.append("SEMANTIC_OWNERS_NOT_SORTED")
    for owner_id, owner in owners.items():
        if not OWNER_RE.fullmatch(str(owner_id)):
            errors.append("SEMANTIC_OWNER_ID_INVALID")
        if not isinstance(owner, dict) or set(owner) != {"description"} or not isinstance(owner.get("description"), str) or not owner["description"].strip():
            errors.append("SEMANTIC_OWNER_INVALID")

    concepts = registry.get("concepts")
    if not isinstance(concepts, dict) or not concepts:
        errors.append("SEMANTIC_CONCEPTS_INVALID")
        concepts = {}
    concept_ids = list(concepts)
    if concept_ids != sorted(concept_ids):
        errors.append("SEMANTIC_CONCEPTS_NOT_SORTED")
    aliases: set[tuple[str, str]] = set()
    for semantic_id, item in concepts.items():
        if not SEMANTIC_ID_RE.fullmatch(str(semantic_id)):
            errors.append("SEMANTIC_ID_INVALID")
        if not isinstance(item, dict):
            errors.append("SEMANTIC_CONCEPT_INVALID")
            continue
        required = {"term", "kind", "owner", "definition"}
        allowed = required | {"related", "aliases"}
        if not required.issubset(item) or not set(item).issubset(allowed):
            errors.append("SEMANTIC_CONCEPT_FIELDS_INVALID")
        for key in ("term", "kind", "owner", "definition"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                errors.append(f"SEMANTIC_CONCEPT_{key.upper()}_INVALID")
        if item.get("owner") not in owners:
            errors.append("SEMANTIC_CONCEPT_OWNER_UNKNOWN")
        related = item.get("related", [])
        if not _unique_string_list(related):
            errors.append("SEMANTIC_RELATED_INVALID")
            related = []
        for related_id in related:
            if related_id not in concepts:
                errors.append("SEMANTIC_RELATED_UNKNOWN")
        raw_aliases = item.get("aliases", [])
        if not isinstance(raw_aliases, list):
            errors.append("SEMANTIC_ALIASES_INVALID")
            raw_aliases = []
        for alias in raw_aliases:
            if not isinstance(alias, dict):
                errors.append("SEMANTIC_ALIAS_INVALID")
                continue
            required_alias = {"term", "scope", "status"}
            allowed_alias = required_alias | {"retireBy"}
            if not required_alias.issubset(alias) or not set(alias).issubset(allowed_alias):
                errors.append("SEMANTIC_ALIAS_FIELDS_INVALID")
                continue
            term = alias.get("term")
            scope = alias.get("scope")
            status = alias.get("status")
            if not isinstance(term, str) or not term.strip() or not isinstance(scope, str) or not scope.strip():
                errors.append("SEMANTIC_ALIAS_IDENTITY_INVALID")
                continue
            key = (scope, term)
            if key in aliases:
                errors.append("SEMANTIC_ALIAS_DUPLICATE")
            aliases.add(key)
            if status not in {"legacy", "supported"}:
                errors.append("SEMANTIC_ALIAS_STATUS_INVALID")
            if status == "legacy" and (not isinstance(alias.get("retireBy"), str) or not alias["retireBy"].strip()):
                errors.append("SEMANTIC_ALIAS_RETIREMENT_REQUIRED")

    contracts = registry.get("contracts")
    if not isinstance(contracts, dict):
        errors.append("SEMANTIC_CONTRACTS_INVALID")
        contracts = {}
    for _, contract in contracts.items():
        if not isinstance(contract, dict) or set(contract) != {"owner", "semanticValidator", "structuralSchema"}:
            errors.append("SEMANTIC_CONTRACT_INVALID")
            continue
        if contract.get("owner") not in owners:
            errors.append("SEMANTIC_CONTRACT_OWNER_UNKNOWN")
        for key in ("semanticValidator", "structuralSchema"):
            if not isinstance(contract.get(key), str) or not contract[key].strip():
                errors.append("SEMANTIC_CONTRACT_REFERENCE_INVALID")

    grammar = registry.get("branchGrammar")
    if not isinstance(grammar, dict) or set(grammar) != {"controlBranches", "canonical", "legacyNamespaces"}:
        errors.append("SEMANTIC_BRANCH_GRAMMAR_INVALID")
    else:
        controls = grammar.get("controlBranches")
        legacy = grammar.get("legacyNamespaces")
        canonical = grammar.get("canonical")
        if not _unique_string_list(controls) or not controls:
            errors.append("SEMANTIC_CONTROL_BRANCHES_INVALID")
        if not _unique_string_list(legacy):
            errors.append("SEMANTIC_LEGACY_NAMESPACES_INVALID")
        if not isinstance(canonical, dict) or set(canonical) != {"authority", "experiment", "work"}:
            errors.append("SEMANTIC_CANONICAL_BRANCHES_INVALID")

    authorities = registry.get("managedAuthorities")
    if not isinstance(authorities, dict) or not authorities:
        errors.append("SEMANTIC_AUTHORITIES_INVALID")
        authorities = {}
    if list(authorities) != sorted(authorities):
        errors.append("SEMANTIC_AUTHORITIES_NOT_SORTED")
    for authority_id, item in authorities.items():
        if not TOPOLOGY_ID_RE.fullmatch(str(authority_id)):
            errors.append("SEMANTIC_AUTHORITY_ID_INVALID")
        if not isinstance(item, dict) or set(item) != {"owner", "mutable", "locator", "requiresCanonicalWriter"}:
            errors.append("SEMANTIC_AUTHORITY_FIELDS_INVALID")
            continue
        if item.get("owner") not in owners:
            errors.append("SEMANTIC_AUTHORITY_OWNER_UNKNOWN")
        if not isinstance(item.get("mutable"), bool) or not isinstance(item.get("requiresCanonicalWriter"), bool):
            errors.append("SEMANTIC_AUTHORITY_FLAGS_INVALID")
        if item.get("requiresCanonicalWriter") and not item.get("mutable"):
            errors.append("SEMANTIC_AUTHORITY_WRITER_ON_READ_ONLY")
        _validate_locator(item.get("locator"), errors)

    resources = registry.get("resources")
    if not isinstance(resources, dict):
        errors.append("SEMANTIC_RESOURCES_INVALID")
        resources = {}
    if list(resources) != sorted(resources):
        errors.append("SEMANTIC_RESOURCES_NOT_SORTED")
    for resource_id, item in resources.items():
        if not TOPOLOGY_ID_RE.fullmatch(str(resource_id)):
            errors.append("SEMANTIC_RESOURCE_ID_INVALID")
        if not isinstance(item, dict) or set(item) != {"owner", "locator"}:
            errors.append("SEMANTIC_RESOURCE_FIELDS_INVALID")
            continue
        if item.get("owner") not in owners:
            errors.append("SEMANTIC_RESOURCE_OWNER_UNKNOWN")
        _validate_locator(item.get("locator"), errors)

    components = registry.get("components")
    if not isinstance(components, dict) or not components:
        errors.append("SEMANTIC_COMPONENTS_INVALID")
        components = {}
    if list(components) != sorted(components):
        errors.append("SEMANTIC_COMPONENTS_NOT_SORTED")
    component_fields = {
        "module",
        "owner",
        "kind",
        "sideEffects",
        "readsAuthorities",
        "writesAuthorities",
        "readsResources",
        "writesResources",
        "produces",
        "canonicalWriterFor",
        "delegatesTo",
    }
    for component_id, item in components.items():
        if not TOPOLOGY_ID_RE.fullmatch(str(component_id)):
            errors.append("SEMANTIC_COMPONENT_ID_INVALID")
        if not isinstance(item, dict) or set(item) != component_fields:
            errors.append("SEMANTIC_COMPONENT_FIELDS_INVALID")
            continue
        module = item.get("module")
        if not isinstance(module, str) or not module or not _module_exists(module):
            errors.append("SEMANTIC_COMPONENT_MODULE_INVALID")
        if item.get("owner") not in owners:
            errors.append("SEMANTIC_COMPONENT_OWNER_UNKNOWN")
        kind = item.get("kind")
        if kind not in COMPONENT_KINDS:
            errors.append("SEMANTIC_COMPONENT_KIND_INVALID")
        if not isinstance(item.get("sideEffects"), bool):
            errors.append("SEMANTIC_COMPONENT_SIDE_EFFECTS_INVALID")
        for key in ("readsAuthorities", "writesAuthorities", "readsResources", "writesResources", "produces", "canonicalWriterFor", "delegatesTo"):
            if not _unique_string_list(item.get(key)):
                errors.append("SEMANTIC_COMPONENT_REFERENCES_INVALID")
        for authority_id in item.get("readsAuthorities", []) + item.get("writesAuthorities", []) + item.get("canonicalWriterFor", []):
            if authority_id not in authorities:
                errors.append("SEMANTIC_COMPONENT_AUTHORITY_UNKNOWN")
        for resource_id in item.get("readsResources", []) + item.get("writesResources", []):
            if resource_id not in resources:
                errors.append("SEMANTIC_COMPONENT_RESOURCE_UNKNOWN")
        for artifact_id in item.get("produces", []):
            if artifact_id not in concepts or concepts[artifact_id].get("kind") != "artifact":
                errors.append("SEMANTIC_COMPONENT_ARTIFACT_UNKNOWN")
        for target in item.get("delegatesTo", []):
            if target == component_id:
                errors.append("SEMANTIC_COMPONENT_SELF_DELEGATION")
            elif target not in components:
                errors.append("SEMANTIC_COMPONENT_DELEGATE_UNKNOWN")
        canonical = set(item.get("canonicalWriterFor", []))
        writes = set(item.get("writesAuthorities", []))
        if not canonical.issubset(writes):
            errors.append("SEMANTIC_CANONICAL_WRITER_NOT_WRITER")
        if kind in READ_ONLY_COMPONENT_KINDS and (item.get("sideEffects") or writes or item.get("writesResources")):
            errors.append("SEMANTIC_READ_ONLY_COMPONENT_WRITES")
        if kind == "cli-adapter" and (writes or canonical):
            errors.append("SEMANTIC_ADAPTER_DECLARED_WRITER")
        if kind == "authority-executor" and (not item.get("sideEffects") or not canonical):
            errors.append("SEMANTIC_AUTHORITY_EXECUTOR_INVALID")
        if kind == "sanitization-executor" and not item.get("sideEffects"):
            errors.append("SEMANTIC_SANITIZATION_EXECUTOR_INVALID")

    for authority_id, authority_item in authorities.items():
        writers = [component_id for component_id, item in components.items() if authority_id in item.get("writesAuthorities", [])]
        canonical_writers = [component_id for component_id, item in components.items() if authority_id in item.get("canonicalWriterFor", [])]
        if not authority_item.get("mutable") and writers:
            errors.append("SEMANTIC_READ_ONLY_AUTHORITY_WRITTEN")
        if authority_item.get("requiresCanonicalWriter"):
            if len(writers) != 1:
                errors.append("SEMANTIC_AUTHORITY_WRITER_COUNT_INVALID")
            if len(canonical_writers) != 1:
                errors.append("SEMANTIC_AUTHORITY_CANONICAL_WRITER_COUNT_INVALID")
            if writers and canonical_writers and writers[0] != canonical_writers[0]:
                errors.append("SEMANTIC_AUTHORITY_WRITER_MISMATCH")
    _validate_v03_extensions(registry, owners, authorities, components, errors)
    return errors


def _validated_registry() -> dict[str, Any]:
    registry = load_registry()
    errors = validate_registry(registry)
    if errors:
        raise RuntimeError(errors[0])
    return registry


def concept(semantic_id: str) -> dict[str, Any]:
    registry = _validated_registry()
    value = registry["concepts"].get(semantic_id)
    if value is None:
        raise RuntimeError("SEMANTIC_CONCEPT_UNKNOWN")
    return {"semanticId": semantic_id, **deepcopy(value)}


def owner_of(semantic_id: str) -> str:
    return str(concept(semantic_id)["owner"])


def aliases_for(semantic_id: str) -> list[dict[str, Any]]:
    return deepcopy(concept(semantic_id).get("aliases", []))


def managed_authority(authority_id: str) -> dict[str, Any]:
    registry = _validated_registry()
    value = registry["managedAuthorities"].get(authority_id)
    if value is None:
        raise RuntimeError("SEMANTIC_AUTHORITY_UNKNOWN")
    writers = [component_id for component_id, item in registry["components"].items() if authority_id in item.get("writesAuthorities", [])]
    canonical = [component_id for component_id, item in registry["components"].items() if authority_id in item.get("canonicalWriterFor", [])]
    readers = [component_id for component_id, item in registry["components"].items() if authority_id in item.get("readsAuthorities", [])]
    return {"authorityId": authority_id, **deepcopy(value), "readers": readers, "writers": writers, "canonicalWriter": canonical[0] if canonical else None}


def component(component_id: str) -> dict[str, Any]:
    registry = _validated_registry()
    value = registry["components"].get(component_id)
    if value is None:
        raise RuntimeError("SEMANTIC_COMPONENT_UNKNOWN")
    return {"componentId": component_id, **deepcopy(value)}


def logical_capability(capability_id: str) -> dict[str, Any]:
    registry = _validated_registry()
    value = registry["logicalCapabilities"].get(capability_id)
    if value is None:
        raise RuntimeError("SEMANTIC_LOGICAL_CAPABILITY_UNKNOWN")
    return {"capabilityId": capability_id, **deepcopy(value)}


def provider_profile(provider_id: str) -> dict[str, Any]:
    registry = _validated_registry()
    value = registry["providerProfiles"].get(provider_id)
    if value is None:
        raise RuntimeError("SEMANTIC_PROVIDER_UNKNOWN")
    return {"providerId": provider_id, **deepcopy(value)}


def tool_surface(surface_id: str) -> dict[str, Any]:
    registry = _validated_registry()
    value = registry["toolSurfaces"].get(surface_id)
    if value is None:
        raise RuntimeError("SEMANTIC_TOOL_SURFACE_UNKNOWN")
    return {"toolSurfaceId": surface_id, **deepcopy(value)}


def resolve_term(term: str, *, scope: str) -> dict[str, Any]:
    registry = _validated_registry()
    matches: list[dict[str, Any]] = []
    for semantic_id, item in registry["concepts"].items():
        if item.get("term") == term:
            matches.append({"semanticId": semantic_id, "alias": False, "status": "canonical"})
        for alias in item.get("aliases", []):
            if alias.get("term") == term and alias.get("scope") == scope:
                matches.append({"semanticId": semantic_id, "alias": True, "status": alias.get("status"), "retireBy": alias.get("retireBy")})
    if not matches:
        raise RuntimeError("SEMANTIC_TERM_UNKNOWN")
    semantic_ids = {item["semanticId"] for item in matches}
    if len(semantic_ids) != 1:
        raise RuntimeError("SEMANTIC_TERM_AMBIGUOUS")
    return matches[0]
