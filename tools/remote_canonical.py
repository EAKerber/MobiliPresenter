"""Read-only request contract and deterministic dispatch to canonical domain planners.

RP1A deliberately stops at a validated TransitionPlan.  It imports no authority
executor or remote transport and cannot apply a mutation.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from tools import coordination_transition as coordination_planner
from tools import continuation_transition as continuation_planner
from tools import transition_protocol as protocol
from tools.canonical import stable_hash

REQUEST_SCHEMA = "RemoteCanonicalRequest 0.1"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
CAPABILITY_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
REQUEST_FIELDS = {
    "schemaVersion",
    "requestId",
    "domain",
    "action",
    "subject",
    "declaredIntent",
    "actor",
    "expectedAuthorities",
    "scope",
    "planner",
    "requiredCapabilities",
    "payload",
    "semanticAuthority",
    "authorizesMutation",
    "requestHash",
}
OBSERVATION_FIELDS = {"authority", "revision", "state", "authorityNow"}

COORDINATION_AUTHORITY = {
    "kind": "git-authority",
    "locator": {
        "repository": coordination_planner.DEFAULT_REPOSITORY,
        "branch": coordination_planner.DEFAULT_BRANCH,
        "path": coordination_planner.DEFAULT_PATH,
    },
}
CONTINUATION_AUTHORITY = {
    "kind": "git-authority",
    "locator": {
        "repository": continuation_planner.DEFAULT_REPOSITORY,
        "branch": continuation_planner.DEFAULT_BRANCH,
        "path": continuation_planner.DEFAULT_DIR,
    },
}


def _identifier(value: Any, code: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise RuntimeError(code)
    return value


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(code)
    return value.strip()


def _authority(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"kind", "locator"}:
        raise RuntimeError("REMOTE_AUTHORITY_INVALID")
    kind = _identifier(value.get("kind"), "REMOTE_AUTHORITY_INVALID")
    locator = value.get("locator")
    if not isinstance(locator, dict) or not locator:
        raise RuntimeError("REMOTE_AUTHORITY_INVALID")
    normalized: dict[str, str | int] = {}
    for key in sorted(locator):
        item = locator[key]
        if not isinstance(key, str) or not key:
            raise RuntimeError("REMOTE_AUTHORITY_INVALID")
        if isinstance(item, bool) or not isinstance(item, (str, int)):
            raise RuntimeError("REMOTE_AUTHORITY_INVALID")
        if isinstance(item, str) and not item:
            raise RuntimeError("REMOTE_AUTHORITY_INVALID")
        normalized[key] = item
    return {"kind": kind, "locator": normalized}


def _authority_key(value: dict[str, Any]) -> str:
    return stable_hash(_authority(value))


def _authority_list(value: Any, *, allow_empty: bool, code: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise RuntimeError(code)
    result = [_authority(item) for item in value]
    keys = [_authority_key(item) for item in result]
    if len(keys) != len(set(keys)):
        raise RuntimeError(code)
    return [item for _, item in sorted(zip(keys, result), key=lambda pair: pair[0])]


def _expected_authorities(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise RuntimeError("REMOTE_EXPECTED_AUTHORITIES_INVALID")
    result: list[dict[str, Any]] = []
    keys: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {"authority", "revision"}:
            raise RuntimeError("REMOTE_EXPECTED_AUTHORITY_INVALID")
        authority = _authority(item["authority"])
        revision = _text(item.get("revision"), "REMOTE_EXPECTED_AUTHORITY_REVISION_INVALID")
        key = _authority_key(authority)
        if key in keys:
            raise RuntimeError("REMOTE_EXPECTED_AUTHORITY_DUPLICATE")
        keys.add(key)
        result.append({"authority": authority, "revision": revision})
    return sorted(result, key=lambda item: _authority_key(item["authority"]))


def _actor(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"role", "workerId", "sessionId"}:
        raise RuntimeError("REMOTE_ACTOR_INVALID")
    return {
        "role": _text(value.get("role"), "REMOTE_ACTOR_INVALID"),
        "workerId": _text(value.get("workerId"), "REMOTE_ACTOR_INVALID"),
        "sessionId": _text(value.get("sessionId"), "REMOTE_ACTOR_INVALID"),
    }


def _subject(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"kind", "id"}:
        raise RuntimeError("REMOTE_SUBJECT_INVALID")
    return {
        "kind": _identifier(value.get("kind"), "REMOTE_SUBJECT_INVALID"),
        "id": _identifier(value.get("id"), "REMOTE_SUBJECT_INVALID"),
    }


def _planner(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"id", "contract"}:
        raise RuntimeError("REMOTE_PLANNER_INVALID")
    planner_id = _text(value.get("id"), "REMOTE_PLANNER_INVALID")
    contract = _text(value.get("contract"), "REMOTE_PLANNER_INVALID")
    if contract != protocol.PLAN_SCHEMA:
        raise RuntimeError("REMOTE_PLANNER_CONTRACT_UNSUPPORTED")
    return {"id": planner_id, "contract": contract}


def _capabilities(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise RuntimeError("REMOTE_REQUIRED_CAPABILITIES_INVALID")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not CAPABILITY_RE.fullmatch(item):
            raise RuntimeError("REMOTE_REQUIRED_CAPABILITIES_INVALID")
        if item in result:
            raise RuntimeError("REMOTE_REQUIRED_CAPABILITIES_INVALID")
        result.append(item)
    return sorted(result)


def _scope(value: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(value, dict) or set(value) != {"allowedAuthorities", "forbiddenAuthorities"}:
        raise RuntimeError("REMOTE_SCOPE_INVALID")
    allowed = _authority_list(
        value.get("allowedAuthorities"), allow_empty=False, code="REMOTE_SCOPE_ALLOWED_INVALID"
    )
    forbidden = _authority_list(
        value.get("forbiddenAuthorities"), allow_empty=True, code="REMOTE_SCOPE_FORBIDDEN_INVALID"
    )
    allowed_keys = {_authority_key(item) for item in allowed}
    forbidden_keys = {_authority_key(item) for item in forbidden}
    if allowed_keys & forbidden_keys:
        raise RuntimeError("REMOTE_SCOPE_OVERLAP")
    return {"allowedAuthorities": allowed, "forbiddenAuthorities": forbidden}


def _core(value: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(item) for key, item in value.items() if key != "requestHash"}


def build_request(
    *,
    request_id: str,
    domain: str,
    action: str,
    subject: dict[str, Any],
    declared_intent: dict[str, Any],
    actor: dict[str, Any],
    expected_authorities: list[dict[str, Any]],
    allowed_authorities: list[dict[str, Any]],
    forbidden_authorities: list[dict[str, Any]],
    planner: dict[str, Any],
    required_capabilities: list[str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(declared_intent, dict):
        raise RuntimeError("REMOTE_DECLARED_INTENT_INVALID")
    if not isinstance(payload, dict):
        raise RuntimeError("REMOTE_PAYLOAD_INVALID")
    expected = _expected_authorities(expected_authorities)
    scope = _scope(
        {
            "allowedAuthorities": allowed_authorities,
            "forbiddenAuthorities": forbidden_authorities,
        }
    )
    body = {
        "schemaVersion": REQUEST_SCHEMA,
        "requestId": _identifier(request_id, "REMOTE_REQUEST_ID_INVALID"),
        "domain": _identifier(domain, "REMOTE_DOMAIN_INVALID"),
        "action": _identifier(action, "REMOTE_ACTION_INVALID"),
        "subject": _subject(subject),
        "declaredIntent": copy.deepcopy(declared_intent),
        "actor": _actor(actor),
        "expectedAuthorities": expected,
        "scope": scope,
        "planner": _planner(planner),
        "requiredCapabilities": _capabilities(required_capabilities),
        "payload": copy.deepcopy(payload),
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    request = {**body, "requestHash": stable_hash(body)}
    return validate_request(request)


def validate_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != REQUEST_FIELDS:
        raise RuntimeError("REMOTE_REQUEST_FIELDS_INVALID")
    if value.get("schemaVersion") != REQUEST_SCHEMA:
        raise RuntimeError("REMOTE_REQUEST_SCHEMA_UNSUPPORTED")
    _identifier(value.get("requestId"), "REMOTE_REQUEST_ID_INVALID")
    _identifier(value.get("domain"), "REMOTE_DOMAIN_INVALID")
    _identifier(value.get("action"), "REMOTE_ACTION_INVALID")
    if _subject(value.get("subject")) != value["subject"]:
        raise RuntimeError("REMOTE_SUBJECT_NOT_CANONICAL")
    if not isinstance(value.get("declaredIntent"), dict):
        raise RuntimeError("REMOTE_DECLARED_INTENT_INVALID")
    if _actor(value.get("actor")) != value["actor"]:
        raise RuntimeError("REMOTE_ACTOR_NOT_CANONICAL")
    expected = _expected_authorities(value.get("expectedAuthorities"))
    if expected != value["expectedAuthorities"]:
        raise RuntimeError("REMOTE_EXPECTED_AUTHORITIES_NOT_CANONICAL")
    scope = _scope(value.get("scope"))
    if scope != value["scope"]:
        raise RuntimeError("REMOTE_SCOPE_NOT_CANONICAL")
    expected_keys = {_authority_key(item["authority"]) for item in expected}
    allowed_keys = {_authority_key(item) for item in scope["allowedAuthorities"]}
    if expected_keys != allowed_keys:
        raise RuntimeError("REMOTE_SCOPE_MUST_MATCH_EXPECTED_AUTHORITIES")
    if _planner(value.get("planner")) != value["planner"]:
        raise RuntimeError("REMOTE_PLANNER_NOT_CANONICAL")
    capabilities = _capabilities(value.get("requiredCapabilities"))
    if capabilities != value["requiredCapabilities"]:
        raise RuntimeError("REMOTE_REQUIRED_CAPABILITIES_NOT_CANONICAL")
    if not isinstance(value.get("payload"), dict):
        raise RuntimeError("REMOTE_PAYLOAD_INVALID")
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise RuntimeError("REMOTE_REQUEST_MUST_NOT_AUTHORIZE")
    request_hash = value.get("requestHash")
    if not isinstance(request_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", request_hash):
        raise RuntimeError("REMOTE_REQUEST_HASH_INVALID")
    if stable_hash(_core(value)) != request_hash:
        raise RuntimeError("REMOTE_REQUEST_HASH_MISMATCH")
    return value


def _payload(request: dict[str, Any], fields: set[str]) -> dict[str, Any]:
    payload = request["payload"]
    if set(payload) != fields:
        raise RuntimeError("REMOTE_PAYLOAD_FIELDS_INVALID")
    return payload


def _coordination_plan(request: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
    before = observation["state"]
    authority_now = observation.get("authorityNow")
    if not isinstance(authority_now, str) or not authority_now:
        raise RuntimeError("REMOTE_TRUSTED_AUTHORITY_TIME_REQUIRED")
    head = observation["revision"]
    action = request["action"]
    if action in {"intent", "acquire"}:
        payload = _payload(
            request, {"owner", "resources", "reason", "transitionId", "ttlSeconds"}
        )
        planner = coordination_planner.plan_intent if action == "intent" else coordination_planner.plan_acquire
        plan = planner(
            before,
            authority_head=head,
            authority_now=authority_now,
            owner=payload["owner"],
            resources=payload["resources"],
            reason=payload["reason"],
            transition_id=payload["transitionId"],
            ttl_seconds=payload["ttlSeconds"],
        )
    elif action == "renew":
        payload = _payload(request, {"owner", "transitionId"})
        plan = coordination_planner.plan_renew(
            before,
            authority_head=head,
            authority_now=authority_now,
            owner=payload["owner"],
            transition_id=payload["transitionId"],
        )
    elif action == "release":
        payload = _payload(request, {"owner", "transitionId", "resources", "mine"})
        plan = coordination_planner.plan_release(
            before,
            authority_head=head,
            authority_now=authority_now,
            owner=payload["owner"],
            transition_id=payload["transitionId"],
            resources=payload["resources"],
            mine=payload["mine"],
        )
    else:
        raise RuntimeError("REMOTE_DOMAIN_PLANNER_UNAVAILABLE")
    coordination_planner.validate_plan(
        plan, before, bind_before=True, authority_now=authority_now
    )
    return plan


def _continuation_plan(request: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
    items = observation["state"]
    if not isinstance(items, dict):
        raise RuntimeError("REMOTE_CONTINUATION_INVENTORY_INVALID")
    continuation_planner.validate_work_inventory(items)
    cid = request["subject"]["id"]
    before = items.get(cid)
    inventory = [copy.deepcopy(items[key]) for key in sorted(items)]
    action = request["action"]
    if action == "create":
        payload = _payload(
            request,
            {"workerId", "remaining", "nextAction", "branch", "prNumber", "dependsOn"},
        )
        plan = continuation_planner.create(
            cid,
            payload["workerId"],
            payload["remaining"],
            payload["nextAction"],
            payload["branch"],
            payload["prNumber"],
            depends_on=payload["dependsOn"],
        )
    elif action == "advance":
        payload = _payload(
            request, {"completed", "nextAction", "lastGoodSha", "checkpoint"}
        )
        plan = continuation_planner.advance(
            before,
            payload["completed"],
            payload["nextAction"],
            payload["lastGoodSha"],
            payload["checkpoint"],
            inventory=inventory,
        )
    elif action == "wait":
        payload = _payload(request, {"blockers"})
        plan = continuation_planner.wait(before, payload["blockers"])
    elif action == "handoff":
        payload = _payload(request, {"targetWorkerId", "nextAction"})
        plan = continuation_planner.handoff(
            before, payload["targetWorkerId"], payload["nextAction"]
        )
    elif action == "resume":
        payload = _payload(request, {"workerId"})
        plan = continuation_planner.resume(before, payload["workerId"])
    elif action == "done":
        _payload(request, set())
        plan = continuation_planner.done(before, inventory=inventory)
    elif action == "bind-execution":
        payload = _payload(request, {"branch", "prNumber"})
        plan = continuation_planner.bind_execution(
            before, payload["branch"], payload["prNumber"]
        )
    elif action == "restart":
        payload = _payload(request, {"remaining", "nextAction"})
        plan = continuation_planner.restart(
            before, payload["remaining"], payload["nextAction"]
        )
    else:
        raise RuntimeError("REMOTE_DOMAIN_PLANNER_UNAVAILABLE")
    continuation_planner.validate_plan(
        plan, before, bind_before=True, inventory=inventory
    )
    return plan


@dataclass(frozen=True)
class PlannerAdapter:
    planner_id: str
    contract: str
    required_capabilities: tuple[str, ...]
    authority: dict[str, Any]
    plan: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


def _adapter(
    planner_id: str,
    capability: str,
    authority: dict[str, Any],
    planner: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
) -> PlannerAdapter:
    return PlannerAdapter(
        planner_id=planner_id,
        contract=protocol.PLAN_SCHEMA,
        required_capabilities=(capability,),
        authority=_authority(authority),
        plan=planner,
    )


_COORDINATION_ADAPTER = _adapter(
    "tools.coordination_transition",
    "coordination.mutate",
    COORDINATION_AUTHORITY,
    _coordination_plan,
)
_CONTINUATION_ADAPTER = _adapter(
    "tools.continuation_transition",
    "work.lifecycle.mutate",
    CONTINUATION_AUTHORITY,
    _continuation_plan,
)

DEFAULT_REGISTRY: dict[tuple[str, str], PlannerAdapter] = {
    **{
        ("coordination", action): _COORDINATION_ADAPTER
        for action in ("intent", "acquire", "renew", "release")
    },
    **{
        ("continuation", action): _CONTINUATION_ADAPTER
        for action in (
            "create",
            "advance",
            "wait",
            "handoff",
            "resume",
            "done",
            "bind-execution",
            "restart",
        )
    },
}


def supported_routes() -> list[dict[str, str]]:
    return [
        {"domain": domain, "action": action}
        for domain, action in sorted(DEFAULT_REGISTRY)
    ]


def _normalize_observations(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise RuntimeError("REMOTE_OBSERVATIONS_REQUIRED")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != OBSERVATION_FIELDS:
            raise RuntimeError("REMOTE_OBSERVATION_FIELDS_INVALID")
        authority = _authority(item["authority"])
        key = _authority_key(authority)
        if key in seen:
            raise RuntimeError("REMOTE_OBSERVATION_DUPLICATE")
        seen.add(key)
        revision = _text(item.get("revision"), "REMOTE_OBSERVATION_REVISION_INVALID")
        state = item.get("state")
        if not isinstance(state, dict):
            raise RuntimeError("REMOTE_OBSERVATION_STATE_INVALID")
        authority_now = item.get("authorityNow")
        if authority_now is not None and (
            not isinstance(authority_now, str) or not authority_now.strip()
        ):
            raise RuntimeError("REMOTE_OBSERVATION_TIME_INVALID")
        result.append(
            {
                "authority": authority,
                "revision": revision,
                "state": copy.deepcopy(state),
                "authorityNow": authority_now.strip() if isinstance(authority_now, str) else None,
            }
        )
    return sorted(result, key=lambda item: _authority_key(item["authority"]))


def plan_request(
    request: dict[str, Any],
    observations: list[dict[str, Any]],
    *,
    registry: Mapping[tuple[str, str], PlannerAdapter] | None = None,
) -> dict[str, Any]:
    validate_request(request)
    routes = DEFAULT_REGISTRY if registry is None else registry
    adapter = routes.get((request["domain"], request["action"]))
    if adapter is None:
        raise RuntimeError("REMOTE_DOMAIN_PLANNER_UNAVAILABLE")
    if request["planner"] != {
        "id": adapter.planner_id,
        "contract": adapter.contract,
    }:
        raise RuntimeError("REMOTE_PLANNER_MISMATCH")
    if request["requiredCapabilities"] != sorted(adapter.required_capabilities):
        raise RuntimeError("REMOTE_CAPABILITY_SET_MISMATCH")

    expected = request["expectedAuthorities"]
    if len(expected) != 1 or expected[0]["authority"] != adapter.authority:
        raise RuntimeError("REMOTE_PLANNER_AUTHORITY_MISMATCH")
    normalized_observations = _normalize_observations(observations)
    expected_keys = [_authority_key(item["authority"]) for item in expected]
    observed_keys = [_authority_key(item["authority"]) for item in normalized_observations]
    if observed_keys != expected_keys:
        raise RuntimeError("REMOTE_OBSERVATION_SET_MISMATCH")
    observation = normalized_observations[0]
    if observation["revision"] != expected[0]["revision"]:
        raise RuntimeError("REMOTE_AUTHORITY_DRIFT")

    plan = adapter.plan(request, observation)
    protocol.validate_plan(plan)
    if plan["domain"] != request["domain"]:
        raise RuntimeError("REMOTE_PLAN_DOMAIN_MISMATCH")
    if plan["action"] != request["action"]:
        raise RuntimeError("REMOTE_PLAN_ACTION_MISMATCH")
    if plan["subject"] != request["subject"]:
        raise RuntimeError("REMOTE_PLAN_SUBJECT_MISMATCH")
    if plan["authority"] != adapter.authority:
        raise RuntimeError("REMOTE_PLAN_AUTHORITY_MISMATCH")
    return copy.deepcopy(plan)
