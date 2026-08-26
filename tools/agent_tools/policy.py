from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from tools.canonical import stable_hash
from tools.semantics.registry import ROOT, load_registry, validate_registry

POLICY_SCHEMA = "AgentToolPolicyCatalog 0.2"
POLICY_PATH = ROOT / "ops" / "semantics" / "agent-tool-policies.json"
TOOL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
EFFECT_CLASSES = {
    "read-only",
    "transport-side-effect",
    "shared-durable-mutation",
    "specialized-maintenance",
}
MODES = {"read-only-execute", "plan-only", "mutation-execute"}
GUARDS = {
    "agent-write-lifecycle-bound",
    "coordination-conflict-guarded",
    "coordination-lease-owned",
    "git-cas",
    "specialized",
}
TOP_FIELDS = {"schemaVersion", "entryProfiles", "targetPolicies", "tools"}
PROFILE_FIELDS = {"lifecyclePhase", "objects", "operations", "scope"}
TARGET_POLICY_FIELDS = {"kind", "branchPrefixes", "forbiddenBranches", "pathPrefixes"}
TOOL_FIELDS = {"adapter", "effectClass", "mode", "roles"}
ROLE_POLICY_FIELDS = {
    "allowedIntents", "guards", "requiredCapabilities", "targetPolicy",
}
ROLE_POLICY_OPTIONAL_FIELDS = {"mode", "modesByIntent"}


def _strings(value: Any, code: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise RuntimeError(code)
    if len(value) != len(set(value)) or value != sorted(value):
        raise RuntimeError(code)
    if not allow_empty and not value:
        raise RuntimeError(code)
    return list(value)


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError("AGENT_TOOL_POLICY_MISSING") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("AGENT_TOOL_POLICY_JSON_INVALID") from exc
    return validate_policy(value)


def effective_mode(
    tool: dict[str, Any],
    role_policy: dict[str, Any],
    declared_intent: str | None = None,
) -> str:
    modes_by_intent = role_policy.get("modesByIntent")
    if modes_by_intent is not None:
        if declared_intent is None:
            raise RuntimeError("AGENT_TOOL_MODE_INTENT_REQUIRED")
        if not isinstance(modes_by_intent, dict):
            raise RuntimeError("AGENT_TOOL_MODE_BY_INTENT_INVALID")
        mode = modes_by_intent.get(declared_intent, tool.get("mode"))
    else:
        mode = role_policy.get("mode", tool.get("mode"))
    if mode not in MODES:
        raise RuntimeError("AGENT_TOOL_MODE_INVALID")
    return mode


def validate_policy(
    value: Any,
    *,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != TOP_FIELDS:
        raise RuntimeError("AGENT_TOOL_POLICY_FIELDS_INVALID")
    if value.get("schemaVersion") != POLICY_SCHEMA:
        raise RuntimeError("AGENT_TOOL_POLICY_SCHEMA_UNSUPPORTED")
    semantic = load_registry() if registry is None else registry
    errors = validate_registry(semantic)
    if errors:
        raise RuntimeError(errors[0])
    vocabulary = semantic["facetVocabulary"]
    roles = set(vocabulary["roles"])
    intents = set(vocabulary["intentClasses"])
    lifecycle = set(vocabulary["lifecyclePhases"])
    objects = set(vocabulary["objects"])
    operations = set(vocabulary["operations"])
    scopes = set(vocabulary["scopes"])

    profiles = value.get("entryProfiles")
    if not isinstance(profiles, dict) or not profiles or list(profiles) != sorted(profiles):
        raise RuntimeError("AGENT_TOOL_ENTRY_PROFILES_INVALID")
    for role, entries in profiles.items():
        if role not in roles or not isinstance(entries, dict) or not entries or list(entries) != sorted(entries):
            raise RuntimeError("AGENT_TOOL_ENTRY_PROFILE_ROLE_INVALID")
        for intent, profile in entries.items():
            if intent not in intents or not isinstance(profile, dict) or set(profile) != PROFILE_FIELDS:
                raise RuntimeError("AGENT_TOOL_ENTRY_PROFILE_INVALID")
            if profile["lifecyclePhase"] not in lifecycle:
                raise RuntimeError("AGENT_TOOL_ENTRY_PROFILE_LIFECYCLE_INVALID")
            for field, allowed in (
                ("objects", objects), ("operations", operations), ("scope", scopes)
            ):
                items = _strings(profile[field], "AGENT_TOOL_ENTRY_PROFILE_LIST_INVALID")
                if not set(items).issubset(allowed):
                    raise RuntimeError("AGENT_TOOL_ENTRY_PROFILE_VOCABULARY_INVALID")

    targets = value.get("targetPolicies")
    if not isinstance(targets, dict) or not targets or list(targets) != sorted(targets):
        raise RuntimeError("AGENT_TOOL_TARGET_POLICIES_INVALID")
    for policy_id, target_policy in targets.items():
        if not TOOL_ID_RE.fullmatch(str(policy_id)):
            raise RuntimeError("AGENT_TOOL_TARGET_POLICY_ID_INVALID")
        if not isinstance(target_policy, dict) or set(target_policy) != TARGET_POLICY_FIELDS:
            raise RuntimeError("AGENT_TOOL_TARGET_POLICY_FIELDS_INVALID")
        if target_policy.get("kind") not in {"none", "git-file"}:
            raise RuntimeError("AGENT_TOOL_TARGET_POLICY_KIND_INVALID")
        _strings(target_policy["branchPrefixes"], "AGENT_TOOL_TARGET_POLICY_LIST_INVALID", allow_empty=True)
        _strings(target_policy["forbiddenBranches"], "AGENT_TOOL_TARGET_POLICY_LIST_INVALID", allow_empty=True)
        _strings(target_policy["pathPrefixes"], "AGENT_TOOL_TARGET_POLICY_LIST_INVALID", allow_empty=True)

    tools = value.get("tools")
    if not isinstance(tools, dict) or not tools or list(tools) != sorted(tools):
        raise RuntimeError("AGENT_TOOL_CATALOG_INVALID")
    capabilities = semantic["logicalCapabilities"]
    for tool_id, tool in tools.items():
        if not TOOL_ID_RE.fullmatch(str(tool_id)):
            raise RuntimeError("AGENT_TOOL_ID_INVALID")
        if not isinstance(tool, dict) or set(tool) != TOOL_FIELDS:
            raise RuntimeError("AGENT_TOOL_FIELDS_INVALID")
        if not isinstance(tool.get("adapter"), str) or not tool["adapter"]:
            raise RuntimeError("AGENT_TOOL_ADAPTER_INVALID")
        if tool.get("effectClass") not in EFFECT_CLASSES or tool.get("mode") not in MODES - {"mutation-execute"}:
            raise RuntimeError("AGENT_TOOL_EFFECT_INVALID")
        role_map = tool.get("roles")
        if not isinstance(role_map, dict) or not role_map or list(role_map) != sorted(role_map):
            raise RuntimeError("AGENT_TOOL_ROLE_POLICY_INVALID")
        for role, role_policy in role_map.items():
            if role not in roles or not isinstance(role_policy, dict):
                raise RuntimeError("AGENT_TOOL_ROLE_POLICY_FIELDS_INVALID")
            fields = set(role_policy)
            if not ROLE_POLICY_FIELDS.issubset(fields) or not fields.issubset(ROLE_POLICY_FIELDS | ROLE_POLICY_OPTIONAL_FIELDS):
                raise RuntimeError("AGENT_TOOL_ROLE_POLICY_FIELDS_INVALID")
            if "mode" in role_policy and "modesByIntent" in role_policy:
                raise RuntimeError("AGENT_TOOL_ROLE_MODE_AMBIGUOUS")
            allowed_intents = _strings(role_policy["allowedIntents"], "AGENT_TOOL_ALLOWED_INTENTS_INVALID")
            if not set(allowed_intents).issubset(intents):
                raise RuntimeError("AGENT_TOOL_ALLOWED_INTENT_UNKNOWN")
            modes_by_intent = role_policy.get("modesByIntent")
            if modes_by_intent is not None:
                if (
                    not isinstance(modes_by_intent, dict)
                    or not modes_by_intent
                    or list(modes_by_intent) != sorted(modes_by_intent)
                    or not set(modes_by_intent).issubset(set(allowed_intents))
                    or any(mode not in MODES for mode in modes_by_intent.values())
                ):
                    raise RuntimeError("AGENT_TOOL_MODE_BY_INTENT_INVALID")
            guards = _strings(role_policy["guards"], "AGENT_TOOL_GUARDS_INVALID", allow_empty=True)
            if not set(guards).issubset(GUARDS):
                raise RuntimeError("AGENT_TOOL_GUARD_UNKNOWN")
            required = _strings(role_policy["requiredCapabilities"], "AGENT_TOOL_CAPABILITIES_INVALID")
            for capability_id in required:
                item = capabilities.get(capability_id)
                if not isinstance(item, dict):
                    raise RuntimeError("AGENT_TOOL_CAPABILITY_UNKNOWN")
                if role not in item["facets"]["roles"]:
                    raise RuntimeError("AGENT_TOOL_CAPABILITY_ROLE_MISMATCH")
            if role_policy["targetPolicy"] not in targets:
                raise RuntimeError("AGENT_TOOL_TARGET_POLICY_UNKNOWN")

            for declared_intent in allowed_intents:
                mode = effective_mode(tool, role_policy, declared_intent)
                if tool["effectClass"] == "read-only" and mode != "read-only-execute":
                    raise RuntimeError("AGENT_TOOL_MODE_EFFECT_MISMATCH")
                if tool["effectClass"] == "shared-durable-mutation" and mode not in {"plan-only", "mutation-execute"}:
                    raise RuntimeError("AGENT_TOOL_MODE_EFFECT_MISMATCH")
                if mode == "mutation-execute":
                    required_guards = {"agent-write-lifecycle-bound", "coordination-lease-owned", "git-cas"}
                    if not required_guards.issubset(set(guards)):
                        raise RuntimeError("AGENT_TOOL_MUTATION_GUARDS_REQUIRED")
                    if "remote.canonical.execute" not in required:
                        raise RuntimeError("AGENT_TOOL_MUTATION_CANONICAL_HOST_REQUIRED")
    return value


def entry_profile(role: str, declared_intent: str, *, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    value = load_policy() if policy is None else validate_policy(policy)
    try:
        profile = value["entryProfiles"][role][declared_intent]
    except KeyError as exc:
        raise RuntimeError("AGENT_CYCLE_ENTRY_PROFILE_REQUIRED") from exc
    return deepcopy(profile)


def policy_hash(
    value: dict[str, Any] | None = None,
    *,
    registry: dict[str, Any] | None = None,
) -> str:
    policy = load_policy() if value is None else validate_policy(value, registry=registry)
    return stable_hash(policy)