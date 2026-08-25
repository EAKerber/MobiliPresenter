from __future__ import annotations

import copy
from typing import Any

from tools.canonical import stable_hash
from tools.agent_tools import admission
from tools.agent_tools import contracts
from tools.agent_tools import policy as tool_policy
from tools.agent_tools import projection as tool_projection
from tools.agent_tools.adapters import ADAPTERS
from tools.agent_tools.target_policy import validate_target
from tools.semantics.registry import load_registry, validate_registry


def _eligible_surfaces(capability_ids: list[str], registry: dict[str, Any]) -> list[str]:
    surfaces: set[str] = set()
    for capability_id in capability_ids:
        item = registry["logicalCapabilities"].get(capability_id)
        if not isinstance(item, dict):
            raise RuntimeError("AGENT_TOOL_CAPABILITY_UNKNOWN")
        surfaces.update(item["toolSurfaces"])
    return sorted(surfaces)


def _bind_to_context(request: dict[str, Any], context: dict[str, Any]) -> None:
    if request["begin"]["contextHash"] != context.get("contextHash"):
        raise RuntimeError("AGENT_TOOL_BEGIN_CONTEXT_MISMATCH")
    semantic = context.get("semanticContext")
    if not isinstance(semantic, dict):
        raise RuntimeError("AGENT_TOOL_CONTEXT_INVALID")
    if request["actor"]["role"] != semantic.get("role"):
        raise RuntimeError("AGENT_TOOL_ROLE_CONTEXT_MISMATCH")


def resolve_request(
    request: dict[str, Any],
    context: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    registry: dict[str, Any] | None = None,
    transport: Any | None = None,
    execute: bool = True,
) -> dict[str, Any]:
    request = contracts.validate_request(request)
    _bind_to_context(request, context)
    semantic = load_registry() if registry is None else registry
    errors = validate_registry(semantic)
    if errors:
        raise RuntimeError(errors[0])
    catalog = tool_policy.load_policy() if policy is None else tool_policy.validate_policy(policy, registry=semantic)
    tool = catalog["tools"].get(request["toolId"])
    if not isinstance(tool, dict):
        raise RuntimeError("AGENT_TOOL_NOT_DECLARED")
    role_policy = tool["roles"].get(request["actor"]["role"])
    if not isinstance(role_policy, dict):
        raise RuntimeError("AGENT_TOOL_ROLE_FORBIDDEN")
    intent = context["semanticContext"].get("declaredIntent")
    if intent not in role_policy["allowedIntents"]:
        raise RuntimeError("AGENT_TOOL_INTENT_FORBIDDEN")
    mode = tool_policy.effective_mode(tool, role_policy, intent)
    projection = tool_projection.build_projection(
        context["semanticContext"], context["semanticBrief"], policy=catalog, registry=semantic
    )
    available_ids = {item["toolId"] for item in projection["available"]}
    plannable_ids = {item["toolId"] for item in projection["plannable"]}
    conditional_ids = {item["toolId"] for item in projection["conditional"]}
    if mode == "read-only-execute" and request["toolId"] not in available_ids:
        raise RuntimeError("AGENT_TOOL_NOT_AVAILABLE")
    if mode == "plan-only" and request["toolId"] not in plannable_ids:
        raise RuntimeError("AGENT_TOOL_NOT_PLANNABLE")
    if mode == "mutation-execute" and request["toolId"] not in available_ids | conditional_ids:
        raise RuntimeError("AGENT_TOOL_NOT_AVAILABLE")
    target_policy_id = role_policy["targetPolicy"]
    validate_target(catalog["targetPolicies"][target_policy_id], request["target"])
    adapter = ADAPTERS.get(tool["adapter"])
    if adapter is None:
        raise RuntimeError("AGENT_TOOL_ADAPTER_UNAVAILABLE")
    concrete = adapter.build_concrete(
        request,
        context,
        transport=transport,
        role_policy=role_policy,
        registry=semantic,
    )
    request_digest = contracts.request_hash(request)
    plan_core = {
        "schemaVersion": contracts.PLAN_SCHEMA,
        "requestHash": request_digest,
        "begin": copy.deepcopy(request["begin"]),
        "actor": copy.deepcopy(request["actor"]),
        "toolId": request["toolId"],
        "effectClass": tool["effectClass"],
        "mode": mode,
        "adapter": tool["adapter"],
        "requiredCapabilities": copy.deepcopy(role_policy["requiredCapabilities"]),
        "eligibleToolSurfaces": _eligible_surfaces(role_policy["requiredCapabilities"], semantic),
        "targetPolicy": target_policy_id,
        "guards": copy.deepcopy(role_policy["guards"]),
        "target": copy.deepcopy(request["target"]),
        "input": copy.deepcopy(request["input"]),
        "concrete": concrete,
        "status": "PLANNED" if mode == "plan-only" else "READY",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    plan = {**plan_core, "planHash": stable_hash(plan_core)}
    contracts.validate_plan(plan)
    if mode == "mutation-execute" and execute:
        raise RuntimeError("AGENT_TOOL_MUTATION_REQUIRES_HOSTED_ADMISSION")
    if mode == "plan-only" or not execute:
        value: Any = copy.deepcopy(concrete)
        status = "PLANNED"
    else:
        admission.assert_execution_admitted(plan)
        value = adapter.execute(
            request,
            context,
            transport=transport,
            role_policy=role_policy,
            registry=semantic,
        )
        status = "PASS"
    result_core = {
        "schemaVersion": contracts.RESULT_SCHEMA,
        "requestHash": request_digest,
        "planHash": plan["planHash"],
        "toolId": request["toolId"],
        "status": status,
        "value": value,
        "blockers": [],
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    result = {**result_core, "resultHash": stable_hash(result_core)}
    contracts.validate_result(result)
    return {"plan": plan, "result": result}
