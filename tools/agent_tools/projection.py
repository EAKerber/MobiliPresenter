from __future__ import annotations

import copy
from typing import Any

from tools.canonical import stable_hash
from tools.agent_tools import policy as tool_policy
from tools.semantics.registry import load_registry, validate_registry

PROJECTION_SCHEMA = "AgentToolProjection 0.2"
LEGACY_PROJECTION_SCHEMA = "AgentToolProjection 0.1"
PROJECTION_FIELDS_V01 = {
    "schemaVersion", "role", "declaredIntent", "available", "plannable", "conditional",
    "policyHash", "projectionHash",
}
PROJECTION_FIELDS_V02 = PROJECTION_FIELDS_V01 | {"discoverable"}
# Public current-contract alias retained for semantic-contract consumers.
PROJECTION_FIELDS = PROJECTION_FIELDS_V02
ENTRY_FIELDS = {"toolId", "effectClass", "mode", "requiredCapabilities"}
CONDITIONAL_ENTRY_FIELDS = ENTRY_FIELDS | {"reasonCode"}
DISCOVERABLE_ENTRY_FIELDS = {
    "toolId", "effectClass", "currentIntentAllowed", "allowedIntents", "requiredCapabilities",
}


def _capability_sets(brief: dict[str, Any]) -> tuple[set[str], set[str]]:
    projection = brief.get("capabilityProjection")
    if not isinstance(projection, dict):
        raise RuntimeError("AGENT_TOOL_CAPABILITY_PROJECTION_INVALID")
    available = set(projection.get("required") or []) | set(projection.get("relevantAvailable") or [])
    unavailable = set(projection.get("conditional") or []) | set(projection.get("requiredUnavailable") or [])
    available -= unavailable
    return available, unavailable


def _discoverable_entry(
    tool_id: str,
    item: dict[str, Any],
    role_policy: dict[str, Any],
    intent: str,
) -> dict[str, Any]:
    return {
        "toolId": tool_id,
        "effectClass": item["effectClass"],
        "currentIntentAllowed": intent in role_policy["allowedIntents"],
        "allowedIntents": copy.deepcopy(role_policy["allowedIntents"]),
        "requiredCapabilities": copy.deepcopy(role_policy["requiredCapabilities"]),
    }


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
    available_caps, unavailable_caps = _capability_sets(semantic_brief)
    available: list[dict[str, Any]] = []
    plannable: list[dict[str, Any]] = []
    conditional: list[dict[str, Any]] = []
    discoverable: list[dict[str, Any]] = []
    for tool_id, item in catalog["tools"].items():
        role_policy = item["roles"].get(role)
        if not isinstance(role_policy, dict):
            continue
        discoverable.append(_discoverable_entry(tool_id, item, role_policy, intent))
        if intent not in role_policy["allowedIntents"]:
            continue
        mode = tool_policy.effective_mode(item, role_policy, intent)
        entry = {
            "toolId": tool_id,
            "effectClass": item["effectClass"],
            "mode": mode,
            "requiredCapabilities": copy.deepcopy(role_policy["requiredCapabilities"]),
        }
        if mode == "plan-only":
            plannable.append(entry)
            continue
        required = set(role_policy["requiredCapabilities"])
        missing = sorted(required - available_caps)
        if not missing:
            available.append(entry)
            continue
        conditional_missing = sorted(required & unavailable_caps)
        reason_capability = conditional_missing[0] if conditional_missing else missing[0]
        conditional.append({**entry, "reasonCode": f"CAPABILITY_NOT_AVAILABLE:{reason_capability}"})
    for values in (available, plannable, conditional, discoverable):
        values.sort(key=lambda entry: entry["toolId"])
    core = {
        "schemaVersion": PROJECTION_SCHEMA,
        "role": role,
        "declaredIntent": intent,
        "available": available,
        "plannable": plannable,
        "conditional": conditional,
        "discoverable": discoverable,
        "policyHash": tool_policy.policy_hash(catalog, registry=semantic),
    }
    result = {**core, "projectionHash": stable_hash(core)}
    validate_projection(result)
    return result


def _validate_string_list(value: Any, code: str) -> list[str]:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item for item in value)
        or value != sorted(set(value))
    ):
        raise RuntimeError(code)
    return value


def _validate_current_entry(item: Any, *, conditional: bool) -> None:
    expected = CONDITIONAL_ENTRY_FIELDS if conditional else ENTRY_FIELDS
    if not isinstance(item, dict) or set(item) != expected:
        raise RuntimeError("AGENT_TOOL_PROJECTION_ENTRY_INVALID")
    if not isinstance(item.get("toolId"), str) or not item["toolId"]:
        raise RuntimeError("AGENT_TOOL_PROJECTION_ENTRY_INVALID")
    if not isinstance(item.get("effectClass"), str) or not item["effectClass"]:
        raise RuntimeError("AGENT_TOOL_PROJECTION_ENTRY_INVALID")
    if item.get("mode") not in {"plan-only", "read-only-execute", "mutation-execute"}:
        raise RuntimeError("AGENT_TOOL_PROJECTION_ENTRY_INVALID")
    _validate_string_list(
        item.get("requiredCapabilities"), "AGENT_TOOL_PROJECTION_CAPABILITIES_INVALID"
    )
    if conditional and (
        not isinstance(item.get("reasonCode"), str) or not item["reasonCode"]
    ):
        raise RuntimeError("AGENT_TOOL_PROJECTION_ENTRY_INVALID")


def _validate_discoverable_entry(item: Any, *, intent: str) -> None:
    if not isinstance(item, dict) or set(item) != DISCOVERABLE_ENTRY_FIELDS:
        raise RuntimeError("AGENT_TOOL_PROJECTION_DISCOVERABLE_ENTRY_INVALID")
    if not isinstance(item.get("toolId"), str) or not item["toolId"]:
        raise RuntimeError("AGENT_TOOL_PROJECTION_DISCOVERABLE_ENTRY_INVALID")
    if not isinstance(item.get("effectClass"), str) or not item["effectClass"]:
        raise RuntimeError("AGENT_TOOL_PROJECTION_DISCOVERABLE_ENTRY_INVALID")
    allowed = _validate_string_list(
        item.get("allowedIntents"), "AGENT_TOOL_PROJECTION_ALLOWED_INTENTS_INVALID"
    )
    _validate_string_list(
        item.get("requiredCapabilities"), "AGENT_TOOL_PROJECTION_CAPABILITIES_INVALID"
    )
    current = item.get("currentIntentAllowed")
    if not isinstance(current, bool) or current != (intent in allowed):
        raise RuntimeError("AGENT_TOOL_PROJECTION_CURRENT_INTENT_INVALID")


def _validate_sorted_unique(items: Any, *, field: str, intent: str) -> None:
    if not isinstance(items, list) or items != sorted(items, key=lambda entry: entry.get("toolId", "")):
        raise RuntimeError("AGENT_TOOL_PROJECTION_LIST_INVALID")
    ids: list[str] = []
    for item in items:
        if field == "discoverable":
            _validate_discoverable_entry(item, intent=intent)
        else:
            _validate_current_entry(item, conditional=field == "conditional")
        ids.append(item["toolId"])
    if len(ids) != len(set(ids)):
        raise RuntimeError("AGENT_TOOL_PROJECTION_DUPLICATE")


def validate_projection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("AGENT_TOOL_PROJECTION_FIELDS_INVALID")
    version = value.get("schemaVersion")
    expected = (
        PROJECTION_FIELDS_V02
        if version == PROJECTION_SCHEMA
        else PROJECTION_FIELDS_V01
        if version == LEGACY_PROJECTION_SCHEMA
        else None
    )
    if expected is None:
        raise RuntimeError("AGENT_TOOL_PROJECTION_SCHEMA_UNSUPPORTED")
    if set(value) != expected:
        raise RuntimeError("AGENT_TOOL_PROJECTION_FIELDS_INVALID")
    for field in ("role", "declaredIntent", "policyHash", "projectionHash"):
        if not isinstance(value.get(field), str) or not value[field]:
            raise RuntimeError("AGENT_TOOL_PROJECTION_VALUE_INVALID")
    intent = value["declaredIntent"]
    for field in ("available", "plannable", "conditional"):
        _validate_sorted_unique(value.get(field), field=field, intent=intent)
    if version == PROJECTION_SCHEMA:
        _validate_sorted_unique(value.get("discoverable"), field="discoverable", intent=intent)
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "projectionHash"}
    if value["projectionHash"] != stable_hash(core):
        raise RuntimeError("AGENT_TOOL_PROJECTION_HASH_MISMATCH")
    return value
