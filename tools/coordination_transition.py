from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from tools import coordination
from tools import transition_protocol as protocol

DEFAULT_REPOSITORY = "EAKerber/MobiliPresenter"
DEFAULT_BRANCH = "coordination/leases"
DEFAULT_PATH = "ops/coordination/leases.json"
ACTIONS = {"intent", "acquire", "renew", "release"}
SUBJECT = {"kind": "coordination", "id": "leases"}


def _authority(
    repository: str = DEFAULT_REPOSITORY,
    branch: str = DEFAULT_BRANCH,
    state_path: str = DEFAULT_PATH,
) -> dict[str, Any]:
    return {
        "kind": "git-authority",
        "locator": {
            "repository": repository,
            "branch": branch,
            "path": state_path,
        },
    }


def _time(value: datetime | str, code: str = "COORDINATION_PLAN_TIME_INVALID") -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RuntimeError(code) from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise RuntimeError(code)
    if parsed.tzinfo is None:
        raise RuntimeError(code)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _stamp(value: datetime | str) -> str:
    return _time(value).isoformat().replace("+00:00", "Z")


def _head(value: Any) -> str:
    if not isinstance(value, str) or len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
        raise RuntimeError("COORDINATION_PLAN_HEAD_INVALID")
    return value


def _transition_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("COORDINATION_TRANSITION_ID_INVALID")
    return value.strip()


def _with_revision(candidate: dict[str, Any], head: str) -> dict[str, Any]:
    value = copy.deepcopy(candidate)
    value["revision"] = _head(head)
    coordination.validate_state(value)
    return value


def _build(
    *,
    action: str,
    before: dict[str, Any],
    candidate: dict[str, Any],
    intent: dict[str, Any],
    repository: str = DEFAULT_REPOSITORY,
    authority_branch: str = DEFAULT_BRANCH,
    state_path: str = DEFAULT_PATH,
) -> dict[str, Any]:
    if action not in ACTIONS:
        raise RuntimeError("COORDINATION_PLAN_ACTION_INVALID")
    coordination.validate_state(before)
    coordination.validate_state(candidate)
    return protocol.build_plan(
        domain="coordination",
        action=action,
        subject=SUBJECT,
        authority=_authority(repository, authority_branch, state_path),
        before=before,
        candidate=candidate,
        intent=intent,
        reversibility="compensatable",
    )


def plan_intent(
    before: dict[str, Any],
    *,
    authority_head: str,
    authority_now: datetime | str,
    owner: dict[str, Any],
    resources: list[str],
    reason: str,
    transition_id: str,
    ttl_seconds: int = coordination.DEFAULT_INTENT_TTL_SECONDS,
    repository: str = DEFAULT_REPOSITORY,
    authority_branch: str = DEFAULT_BRANCH,
    state_path: str = DEFAULT_PATH,
) -> dict[str, Any]:
    planned_at = _stamp(authority_now)
    tid = _transition_id(transition_id)
    candidate, _ = coordination.plan_intent(
        before, resources, owner, reason, planned_at, tid, ttl_seconds
    )
    candidate = _with_revision(candidate, authority_head)
    canonical_owner = coordination.validate_owner(owner)
    canonical_resources = coordination.normalize_resources(resources)
    return _build(
        action="intent",
        before=before,
        candidate=candidate,
        intent={
            "expectedAuthorityHead": _head(authority_head),
            "plannedAt": planned_at,
            "transitionId": tid,
            "owner": canonical_owner,
            "resources": canonical_resources,
            "reason": reason.strip(),
            "ttlSeconds": ttl_seconds,
        },
        repository=repository,
        authority_branch=authority_branch,
        state_path=state_path,
    )


def plan_acquire(
    before: dict[str, Any],
    *,
    authority_head: str,
    authority_now: datetime | str,
    owner: dict[str, Any],
    resources: list[str],
    reason: str,
    transition_id: str,
    ttl_seconds: int = coordination.DEFAULT_TTL_SECONDS,
    repository: str = DEFAULT_REPOSITORY,
    authority_branch: str = DEFAULT_BRANCH,
    state_path: str = DEFAULT_PATH,
) -> dict[str, Any]:
    planned_at = _stamp(authority_now)
    tid = _transition_id(transition_id)
    candidate, _ = coordination.plan_acquire(
        before, resources, owner, reason, planned_at, tid, ttl_seconds
    )
    candidate = _with_revision(candidate, authority_head)
    canonical_owner = coordination.validate_owner(owner)
    canonical_resources = coordination.normalize_resources(resources)
    return _build(
        action="acquire",
        before=before,
        candidate=candidate,
        intent={
            "expectedAuthorityHead": _head(authority_head),
            "plannedAt": planned_at,
            "transitionId": tid,
            "owner": canonical_owner,
            "resources": canonical_resources,
            "reason": reason.strip(),
            "ttlSeconds": ttl_seconds,
        },
        repository=repository,
        authority_branch=authority_branch,
        state_path=state_path,
    )


def plan_renew(
    before: dict[str, Any],
    *,
    authority_head: str,
    authority_now: datetime | str,
    owner: dict[str, Any],
    transition_id: str,
    repository: str = DEFAULT_REPOSITORY,
    authority_branch: str = DEFAULT_BRANCH,
    state_path: str = DEFAULT_PATH,
) -> dict[str, Any]:
    planned_at = _stamp(authority_now)
    tid = _transition_id(transition_id)
    candidate, event = coordination.plan_renew_mine(before, owner, planned_at, tid)
    candidate = _with_revision(candidate, authority_head)
    return _build(
        action="renew",
        before=before,
        candidate=candidate,
        intent={
            "expectedAuthorityHead": _head(authority_head),
            "plannedAt": planned_at,
            "transitionId": tid,
            "owner": coordination.validate_owner(owner),
            "resources": list(event["resources"]),
        },
        repository=repository,
        authority_branch=authority_branch,
        state_path=state_path,
    )


def plan_release(
    before: dict[str, Any],
    *,
    authority_head: str,
    authority_now: datetime | str,
    owner: dict[str, Any],
    transition_id: str,
    resources: list[str] | None = None,
    mine: bool = False,
    repository: str = DEFAULT_REPOSITORY,
    authority_branch: str = DEFAULT_BRANCH,
    state_path: str = DEFAULT_PATH,
) -> dict[str, Any]:
    planned_at = _stamp(authority_now)
    tid = _transition_id(transition_id)
    candidate, event = coordination.plan_release(
        before, owner, planned_at, tid, resources=resources, mine=mine
    )
    candidate = _with_revision(candidate, authority_head)
    return _build(
        action="release",
        before=before,
        candidate=candidate,
        intent={
            "expectedAuthorityHead": _head(authority_head),
            "plannedAt": planned_at,
            "transitionId": tid,
            "owner": coordination.validate_owner(owner),
            "resources": list(event["resources"]),
            "mine": bool(mine),
        },
        repository=repository,
        authority_branch=authority_branch,
        state_path=state_path,
    )


def rebuild(
    plan: dict[str, Any],
    before: dict[str, Any],
    *,
    repository: str = DEFAULT_REPOSITORY,
    authority_branch: str = DEFAULT_BRANCH,
    state_path: str = DEFAULT_PATH,
) -> dict[str, Any]:
    protocol.validate_plan(plan)
    coordination.validate_state(before)
    action = plan["action"]
    intent = plan["intent"]
    common = {
        "before": before,
        "authority_head": intent.get("expectedAuthorityHead"),
        "authority_now": intent.get("plannedAt"),
        "owner": intent.get("owner"),
        "transition_id": intent.get("transitionId"),
        "repository": repository,
        "authority_branch": authority_branch,
        "state_path": state_path,
    }
    if action == "intent":
        return plan_intent(
            **common,
            resources=intent.get("resources"),
            reason=intent.get("reason"),
            ttl_seconds=intent.get("ttlSeconds"),
        )
    if action == "acquire":
        return plan_acquire(
            **common,
            resources=intent.get("resources"),
            reason=intent.get("reason"),
            ttl_seconds=intent.get("ttlSeconds"),
        )
    if action == "renew":
        return plan_renew(**common)
    if action == "release":
        return plan_release(
            **common,
            resources=None if intent.get("mine") else intent.get("resources"),
            mine=bool(intent.get("mine")),
        )
    raise RuntimeError("COORDINATION_PLAN_ACTION_INVALID")


def _active_owned_resources(
    before: dict[str, Any],
    owner: dict[str, Any],
    authority_now: datetime,
) -> set[str]:
    canonical_owner = coordination.validate_owner(owner)
    active = coordination.active_leases(before, authority_now)
    return {
        lease["resource"]
        for lease in active
        if coordination.validate_owner(lease["owner"])["session"] == canonical_owner["session"]
    }


def validate_plan(
    plan: dict[str, Any],
    before: dict[str, Any] | None = None,
    *,
    repository: str = DEFAULT_REPOSITORY,
    authority_branch: str = DEFAULT_BRANCH,
    state_path: str = DEFAULT_PATH,
    bind_before: bool = False,
    authority_now: datetime | str | None = None,
) -> dict[str, Any]:
    protocol.validate_plan(plan)
    if plan["domain"] != "coordination":
        raise RuntimeError("COORDINATION_PLAN_DOMAIN_INVALID")
    if plan["subject"] != SUBJECT:
        raise RuntimeError("COORDINATION_PLAN_SUBJECT_INVALID")
    if plan["authority"] != _authority(repository, authority_branch, state_path):
        raise RuntimeError("COORDINATION_PLAN_AUTHORITY_INVALID")
    if plan["action"] not in ACTIONS:
        raise RuntimeError("COORDINATION_PLAN_ACTION_INVALID")
    intent = plan["intent"]
    required = {"expectedAuthorityHead", "plannedAt", "transitionId", "owner", "resources"}
    if not required.issubset(intent):
        raise RuntimeError("COORDINATION_PLAN_INTENT_INVALID")
    _head(intent["expectedAuthorityHead"])
    planned_at = _time(intent["plannedAt"])
    coordination.validate_owner(intent["owner"])
    if not isinstance(intent["resources"], list):
        raise RuntimeError("COORDINATION_PLAN_INTENT_INVALID")
    _transition_id(intent["transitionId"])
    coordination.validate_state(plan["candidate"])

    if bind_before:
        if before is None:
            raise RuntimeError("COORDINATION_PLAN_BEFORE_REQUIRED")
        coordination.validate_state(before)
        if protocol.state_hash(before) != plan["beforeStateHash"]:
            raise RuntimeError("COORDINATION_PLAN_STALE")
        if rebuild(
            plan,
            before,
            repository=repository,
            authority_branch=authority_branch,
            state_path=state_path,
        ) != plan:
            raise RuntimeError("COORDINATION_PLAN_SEMANTIC_MISMATCH")

    if authority_now is not None:
        now = _time(authority_now, "COORDINATION_APPLY_TIME_INVALID")
        if now < planned_at:
            raise RuntimeError("COORDINATION_REMOTE_TIME_REGRESSION")
        action = plan["action"]
        if action in {"intent", "acquire"}:
            collection = "intents" if action == "intent" else "leases"
            prefixes = f"{intent['transitionId']}:"
            planned_entries = [
                entry for entry in plan["candidate"][collection]
                if str(entry.get("intentId" if action == "intent" else "leaseId", "")).startswith(prefixes)
            ]
            if not planned_entries or any(_time(entry["expiresAt"]) <= now for entry in planned_entries):
                raise RuntimeError("COORDINATION_PLAN_EXPIRED")
        elif action == "renew":
            if before is None:
                raise RuntimeError("COORDINATION_PLAN_BEFORE_REQUIRED")
            active_owned = _active_owned_resources(before, intent["owner"], now)
            if not set(intent["resources"]).issubset(active_owned):
                raise RuntimeError("COORDINATION_RENEW_TARGET_EXPIRED")
    return plan
