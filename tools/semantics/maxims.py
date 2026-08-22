from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tools.semantics.registry import ROOT, load_registry

SCHEMA_VERSION = "EcosystemMaximCatalog 0.1"
CATALOG_PATH = ROOT / "ops" / "semantics" / "maxims.json"
TOP_FIELDS = {
    "schemaVersion",
    "readOnly",
    "semanticAuthority",
    "authorizesMutation",
    "overridesContract",
    "items",
}
ITEM_FIELDS = {
    "id",
    "statement",
    "justification",
    "operationalQuestion",
    "misreadRisk",
    "appliesTo",
    "relatedContracts",
    "editorialOwner",
    "deathCondition",
    "semanticAuthority",
    "authorizesMutation",
    "overridesContract",
}
MAXIM_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"ECOSYSTEM_MAXIMS_MISSING:{path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"ECOSYSTEM_MAXIMS_JSON_INVALID:{exc.lineno}:{exc.colno}"
        ) from exc
    if not isinstance(value, dict):
        raise RuntimeError("ECOSYSTEM_MAXIMS_ROOT_INVALID")
    return value


def _sorted_strings(value: Any, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(isinstance(item, str) and item.strip() for item in value)
        and len(value) == len(set(value))
        and value == sorted(value)
    )


def validate_catalog(value: dict[str, Any] | None = None) -> list[str]:
    catalog = load_catalog() if value is None else value
    errors: list[str] = []
    if not isinstance(catalog, dict) or set(catalog) != TOP_FIELDS:
        return ["ECOSYSTEM_MAXIMS_FIELDS_INVALID"]
    if catalog.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("ECOSYSTEM_MAXIMS_SCHEMA_UNSUPPORTED")
    for field, expected in (
        ("readOnly", True),
        ("semanticAuthority", False),
        ("authorizesMutation", False),
        ("overridesContract", False),
    ):
        if catalog.get(field) is not expected:
            errors.append(f"ECOSYSTEM_MAXIMS_{field.upper()}_INVALID")

    registry = load_registry()
    owners = registry.get("owners", {})
    contracts = registry.get("contracts", {})
    items = catalog.get("items")
    if not isinstance(items, dict) or not items:
        return errors + ["ECOSYSTEM_MAXIMS_ITEMS_INVALID"]
    if list(items) != sorted(items):
        errors.append("ECOSYSTEM_MAXIMS_ITEMS_NOT_SORTED")
    statements: set[str] = set()
    for maxim_id, item in items.items():
        if not MAXIM_ID_RE.fullmatch(str(maxim_id)):
            errors.append("ECOSYSTEM_MAXIM_ID_INVALID")
        if not isinstance(item, dict) or set(item) != ITEM_FIELDS:
            errors.append(f"ECOSYSTEM_MAXIM_FIELDS_INVALID:{maxim_id}")
            continue
        if item.get("id") != maxim_id:
            errors.append(f"ECOSYSTEM_MAXIM_ID_MISMATCH:{maxim_id}")
        for field in (
            "statement",
            "justification",
            "operationalQuestion",
            "misreadRisk",
            "deathCondition",
        ):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"ECOSYSTEM_MAXIM_{field.upper()}_INVALID:{maxim_id}")
        statement = item.get("statement")
        if isinstance(statement, str):
            if statement in statements:
                errors.append(f"ECOSYSTEM_MAXIM_STATEMENT_DUPLICATE:{maxim_id}")
            statements.add(statement)
        if not _sorted_strings(item.get("appliesTo")):
            errors.append(f"ECOSYSTEM_MAXIM_APPLIES_TO_INVALID:{maxim_id}")
        related = item.get("relatedContracts")
        if not _sorted_strings(related):
            errors.append(f"ECOSYSTEM_MAXIM_CONTRACTS_INVALID:{maxim_id}")
        else:
            for contract_id in related:
                if contract_id not in contracts:
                    errors.append(
                        f"ECOSYSTEM_MAXIM_CONTRACT_UNKNOWN:{maxim_id}:{contract_id}"
                    )
        if item.get("editorialOwner") not in owners:
            errors.append(f"ECOSYSTEM_MAXIM_OWNER_UNKNOWN:{maxim_id}")
        for field in ("semanticAuthority", "authorizesMutation", "overridesContract"):
            if item.get(field) is not False:
                errors.append(f"ECOSYSTEM_MAXIM_{field.upper()}_INVALID:{maxim_id}")
    return errors


def maxim(maxim_id: str) -> dict[str, Any]:
    catalog = load_catalog()
    errors = validate_catalog(catalog)
    if errors:
        raise RuntimeError(errors[0])
    value = catalog["items"].get(maxim_id)
    if value is None:
        raise RuntimeError("ECOSYSTEM_MAXIM_UNKNOWN")
    return dict(value)
