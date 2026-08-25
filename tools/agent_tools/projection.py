from __future__ import annotations

import copy
from typing import Any

from tools.canonical import stable_hash
from tools.agent_tools import policy as tool_policy
from tools.semantics.registry import load_registry, validate_registry

PROJECTION_SCHEMA = "AgentToolProjection 0.1"
PROJECTION_FIELDS = {
    "schemaVersion", "role", "declaredIntent", "available", "plannable", "conditional",
    "policyHash", "projectionHash",
}


def _capability_sets(brief: dict[str, Any]) -> tuple[set[str], set[str]]:
    projection = brief.get("capabilityProjection")
    if not isinstance(projection, dict):
        raise RuntimeError("AGENT_TOOL_CAPABILITY_PROJECTION_INVALID")
    available = set(projection.get("required") or []) | set(projection.get("relevantAvailable") or [])
    unavailable = set(projection.get("conditional") or []) | set(projection.get("requiredUnavailable") or [])
    available -= unavailable
    return available, unavailable


def build_projection(
    semantic_context: dict[str, Any],
    semantic_brief: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    semantic = load_registry() if registry is None else registry
    catalog = tool_policy.load_policy() if policy is None else tool_policy.validate_policy(policy, registry=semantic)
    errors = validate_registry(semantic)
    if errors:
        raise RuntimeError(errors[0])
    role = semantic_context.get("role")
    intent = semantic_context.get("declaredIntent")
    if role not in semantic["facetVocabulary"]["roles"] or intent not in semantic["facetVocabulary"]["intentClasses"]:
        raise RuntimeError("AGENT_TOOL_PROJECTION_CONTEXT_INVALID")
    available_caps, _ = _capability_sets(semantic_brief)
    available: list[dict[str, Any]] = []
    plannable: list[dict[str, Any]] = []
    conditional: list[dict[str, Any]] = []
    for tool_id, item in catalog["tools"].items():
        role_policy = item["roles"].get(role)
        if not isinstance(role_policy, dict) or intent not in role_policy["allowedIntents"]:
            continue
        mode = tool_policy.effective_mode(item, role_policy)
        entry = {
            "toolId": tool_id,
            "effectClass": item["effectClass"],
            "mode": mode,
            "requiredCapabilities": copy.deepcopy(role_policy["requiredCapabilities"]),
        }
        if mode == "plan-only":
            plannable.append(entry)
            continue
        missing = sorted(set(role_policy["requiredCapabilities"]) - available_caps)
        if not missing:
            available.append(entry)
        else:
            conditional.append({**entry, "reasonCode": f"CAPABILITY_NOT_AVAILABLE:{missing[0]}"})
    for values in (available, plannable, conditional):
        values.sort(key=lambda entry: entry["toolId"])
    core = {
        "schemaVersion": PROJECTION_SCHEMA,
        "role": role,
        "declaredIntent": intent,
        "available": available,
        "plannable": plannable,
        "conditional": conditional,
        "policyHash": tool_policy.policy_hash(catalog, registry=semantic),
    }
    result = {**core, "projectionHash": stable_hash(core)}
    validate_projection(result)
    return result


def validate_projection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != PROJECTION_FIELDS:
        raise RuntimeError("AGENT_TOOL_PROJECTION_FIELDS_INVALID")
    if value.get("schemaVersion") != PROJECTION_SCHEMA:
        raise RuntimeError("AGENT_TOOL_PROJECTION_SCHEMA_UNSUPPORTED")
    for field in ("role", "declaredIntent", "policyHash", "projectionHash"):
        if not isinstance(value.get(field), str) or not value[field]:
            raise RuntimeError("AGENT_TOOL_PROJECTION_VALUE_INVALID")
    for field in ("available", "plannable", "conditional"):
        items = value.get(field)
        if not isinstance(items, list) or items != sorted(items, key=lambda entry: entry.get("toolId", "")):
            raise RuntimeError("AGENT_TOOL_PROJECTION_LIST_INVALID")
        ids: list[str] = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("toolId"), str):
                raise RuntimeError("AGENT_TOOL_PROJECTION_ENTRY_INVALID")
            ids.append(item["toolId"])
        if len(ids) != len(set(ids)):
            raise RuntimeError("AGENT_TOOL_PROJECTION_DUPLICATE")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "projectionHash"}
    if value["projectionHash"] != stable_hash(core):
        raise RuntimeError("AGENT_TOOL_PROJECTION_HASH_MISMATCH")
    return value
