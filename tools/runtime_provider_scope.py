"""Pure provider-scope derivation over RuntimeCapabilityInspection.

A provider scope answers whether one observed provider can satisfy an entire set of
runtime-observed logical capabilities. It never selects a provider, performs
transport discovery, or authorizes mutation.
"""
from __future__ import annotations

from typing import Any

from tools import runtime_capabilities

_POSSIBLE_OUTCOMES = {"SATISFIED", "UNOBSERVED_OR_INCOMPLETE"}


def _required_capabilities(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise RuntimeError("RUNTIME_PROVIDER_SCOPE_CAPABILITIES_REQUIRED")
    normalized: list[str] = []
    for capability_id in value:
        if not isinstance(capability_id, str) or not capability_id.strip():
            raise RuntimeError("RUNTIME_PROVIDER_SCOPE_CAPABILITY_INVALID")
        capability_id = capability_id.strip()
        if capability_id in normalized:
            raise RuntimeError("RUNTIME_PROVIDER_SCOPE_CAPABILITIES_NOT_CANONICAL")
        normalized.append(capability_id)
    unknown = sorted(set(normalized) - set(runtime_capabilities.CAPABILITIES))
    if unknown:
        raise RuntimeError(
            f"RUNTIME_PROVIDER_SCOPE_CAPABILITY_NOT_RUNTIME_OBSERVED:{unknown[0]}"
        )
    return sorted(normalized)


def resolve_provider_scope(
    inspection: dict[str, Any], required_capabilities: list[str]
) -> dict[str, Any]:
    """Derive complete and still-possible single-provider carriers.

    PASS means at least one *single* provider already satisfies every requested
    runtime-observed capability. UNKNOWN means no complete provider is known yet,
    but an incomplete provider observation could still become a complete carrier.
    FAIL means the current complete evidence leaves no single supported provider
    capable of satisfying the whole set.

    This result is evidence only. It does not choose among complete providers and
    never authorizes mutation.
    """
    value = runtime_capabilities.validate_inspection(inspection)
    capabilities = _required_capabilities(required_capabilities)

    complete: set[str] | None = None
    possible: set[str] | None = None
    for capability_id in capabilities:
        item = value["capabilities"][capability_id]
        satisfied = set(item["satisfiedProviders"])
        outcomes = {
            evaluation["provider"]: evaluation["outcome"]
            for evaluation in item["providerEvaluations"]
        }
        capability_possible = {
            provider_id
            for provider_id in item["supportedProviders"]
            if outcomes.get(provider_id) in _POSSIBLE_OUTCOMES
        }
        complete = satisfied if complete is None else complete & satisfied
        possible = (
            capability_possible
            if possible is None
            else possible & capability_possible
        )

    complete_providers = sorted(complete or set())
    possible_providers = sorted(possible or set())
    if complete_providers:
        status = "PASS"
        reason_code = "PROVIDER_SCOPE_SATISFIED"
    elif possible_providers:
        status = "UNKNOWN"
        reason_code = "PROVIDER_SCOPE_OBSERVATION_INCOMPLETE"
    else:
        status = "FAIL"
        reason_code = "NO_SINGLE_PROVIDER_SATISFIES_SCOPE"

    return {
        "requiredCapabilities": capabilities,
        "status": status,
        "reasonCode": reason_code,
        "completeProviders": complete_providers,
        "possibleProviders": possible_providers,
        "inspectionHash": value["inspectionHash"],
        "authorizesMutation": False,
    }
