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


def validate_registry(value: dict[str, Any] | None = None) -> list[str]:
    registry = load_registry() if value is None else value
    errors: list[str] = []
    expected_top = {"schemaVersion", "owners", "concepts", "contracts", "branchGrammar"}
    if set(registry) != expected_top:
        errors.append("SEMANTIC_REGISTRY_FIELDS_INVALID")
    if registry.get("schemaVersion") != "OperationalSemantics 0.1":
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
        if not isinstance(related, list) or len(related) != len(set(related)):
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
        if not isinstance(controls, list) or not controls or len(controls) != len(set(controls)):
            errors.append("SEMANTIC_CONTROL_BRANCHES_INVALID")
        if not isinstance(legacy, list) or len(legacy) != len(set(legacy)):
            errors.append("SEMANTIC_LEGACY_NAMESPACES_INVALID")
        if not isinstance(canonical, dict) or set(canonical) != {"authority", "experiment", "work"}:
            errors.append("SEMANTIC_CANONICAL_BRANCHES_INVALID")
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
