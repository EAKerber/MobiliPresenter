"""Registry-bound adapter from observed ToolSurfaces to provider observations."""
from __future__ import annotations
import copy
from typing import Any
from tools import runtime_capabilities
from tools.semantics.registry import load_registry, validate_registry

_INCOMPLETE_REASON = "TOOL_SURFACE_INVENTORY_INCOMPLETE"

def _registry() -> dict[str, Any]:
    registry = load_registry()
    errors = validate_registry(registry)
    if errors:
        raise RuntimeError(errors[0])
    return registry

def _surface_ids(value: Any, surfaces: dict[str, Any]) -> list[str]:
    if not isinstance(value, list):
        raise RuntimeError("RUNTIME_PROVIDER_SURFACES_INVALID")
    normalized: list[str] = []
    for surface_id in value:
        if not isinstance(surface_id, str) or not surface_id.strip():
            raise RuntimeError("RUNTIME_PROVIDER_SURFACE_ID_INVALID")
        surface_id = surface_id.strip()
        if surface_id in normalized:
            raise RuntimeError("RUNTIME_PROVIDER_SURFACES_DUPLICATE")
        if surface_id not in surfaces:
            raise RuntimeError(f"RUNTIME_PROVIDER_SURFACE_UNKNOWN:{surface_id}")
        normalized.append(surface_id)
    return sorted(normalized)

def observations_from_tool_surfaces(
    observed_surface_ids: list[str],
    *,
    inventory_complete: bool,
) -> dict[str, Any]:
    """Translate a complete external ToolSurface inventory into existing provider observations."""
    if not isinstance(inventory_complete, bool):
        raise RuntimeError("RUNTIME_PROVIDER_SURFACE_INVENTORY_COMPLETENESS_INVALID")
    registry = _registry()
    surfaces = registry["toolSurfaces"]
    surface_ids = _surface_ids(observed_surface_ids, surfaces)
    provider_ids = sorted({surfaces[surface_id]["provider"] for surface_id in surface_ids})
    providers: dict[str, dict[str, Any]] = {}
    for provider_id in provider_ids:
        if not inventory_complete:
            providers[provider_id] = {
                "status": "UNKNOWN",
                "features": [],
                "reason": _INCOMPLETE_REASON,
            }
            continue
        features = sorted({
            feature
            for surface_id in surface_ids
            if surfaces[surface_id]["provider"] == provider_id
            for feature in surfaces[surface_id]["features"]
        })
        providers[provider_id] = {
            "status": "PASS",
            "features": features,
            "reason": None,
        }
    return runtime_capabilities.validate_provider_observations({
        "schemaVersion": runtime_capabilities.PROVIDER_OBSERVATIONS_SCHEMA,
        "providers": copy.deepcopy(providers),
    })
