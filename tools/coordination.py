from __future__ import annotations

import copy
import re
from datetime import datetime, timedelta, timezone
from typing import Any

SCHEMA_VERSION = "CoordinationState 0.1"
DEFAULT_TTL_SECONDS = 60 * 60
MAX_TTL_SECONDS = 4 * 60 * 60
DEFAULT_INTENT_TTL_SECONDS = 30 * 60

_GLOB_META = {"*", "?"}
_INVALID_BRANCH_CHARS = set(" ~^:?*[\\")


class CoordinationError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def empty_state(revision: str | None = None) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "revision": revision,
        "intents": [],
        "leases": [],
    }


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CoordinationError("COORDINATION_STATE_INVALID", f"{field} must be a non-empty string")
    return value


def validate_owner(owner: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(owner, dict):
        raise CoordinationError("OWNER_INVALID", "owner must be an object")
    role = _require_string(owner.get("role"), "owner.role").strip()
    session = _require_string(owner.get("session"), "owner.session").strip()
    branch = owner.get("branch")
    pr = owner.get("pr")
    if branch is not None:
        branch = _require_string(branch, "owner.branch").strip()
        _normalize_branch(branch)
    if pr is not None and (not isinstance(pr, int) or isinstance(pr, bool) or pr <= 0):
        raise CoordinationError("OWNER_INVALID", "owner.pr must be null or a positive integer")
    return {"role": role, "session": session, "branch": branch, "pr": pr}


def validate_state(state: dict[str, Any]) -> None:
    if not isinstance(state, dict):
        raise CoordinationError("COORDINATION_STATE_INVALID", "root must be an object")
    if state.get("schemaVersion") != SCHEMA_VERSION:
        raise CoordinationError("COORDINATION_STATE_INVALID", f"schemaVersion must be {SCHEMA_VERSION}")
    if state.get("revision") is not None and not isinstance(state.get("revision"), str):
        raise CoordinationError("COORDINATION_STATE_INVALID", "revision must be null or a string")
    for collection in ("intents", "leases"):
        if not isinstance(state.get(collection), list):
            raise CoordinationError("COORDINATION_STATE_INVALID", f"{collection} must be a list")
    for intent in state["intents"]:
        _validate_intent(intent)
    for lease in state["leases"]:
        _validate_lease(lease)


def _parse_time(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise CoordinationError("TIME_INVALID", "timestamp must be a non-empty string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CoordinationError("TIME_INVALID", value) from exc
    if parsed.tzinfo is None:
        raise CoordinationError("TIME_INVALID", "timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    if value.tzinfo is None:
        raise CoordinationError("TIME_INVALID", "naive datetime")
    utc = value.astimezone(timezone.utc).replace(microsecond=0)
    return utc.isoformat().replace("+00:00", "Z")


def _normalize_now(now: datetime | str) -> datetime:
    if isinstance(now, str):
        return _parse_time(now)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise CoordinationError("TIME_INVALID", "now must be timezone-aware datetime or RFC3339 string")
    return now.astimezone(timezone.utc).replace(microsecond=0)


def _normalize_repo_path(path: str, *, allow_glob: bool) -> str:
    if not isinstance(path, str) or not path:
        raise CoordinationError("RESOURCE_INVALID", "path is empty")
    if "\\" in path:
        raise CoordinationError("RESOURCE_INVALID", "backslash is not canonical; use /")
    if path.startswith("/") or path.endswith("/"):
        raise CoordinationError("RESOURCE_INVALID", "path must be repo-relative without leading/trailing slash")
    segments = path.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise CoordinationError("RESOURCE_INVALID", "path contains empty, . or .. segment")
    if "[" in path or "]" in path:
        raise CoordinationError("RESOURCE_INVALID", "character classes are outside glob grammar 0.1")
    has_meta = any(ch in path for ch in _GLOB_META)
    if allow_glob and not has_meta:
        raise CoordinationError("RESOURCE_INVALID", "path: resource must contain * or ?")
    if not allow_glob and has_meta:
        raise CoordinationError("RESOURCE_INVALID", "file: resource cannot contain glob metacharacters")
    return "/".join(segments)


def _normalize_branch(branch: str) -> str:
    if not isinstance(branch, str) or not branch:
        raise CoordinationError("RESOURCE_INVALID", "branch is empty")
    if branch.startswith("/") or branch.endswith("/") or branch.startswith(".") or branch.endswith("."):
        raise CoordinationError("RESOURCE_INVALID", "invalid branch boundary")
    if ".." in branch or "@{" in branch or "//" in branch:
        raise CoordinationError("RESOURCE_INVALID", "invalid branch sequence")
    if any(ch in _INVALID_BRANCH_CHARS or ord(ch) < 32 or ord(ch) == 127 for ch in branch):
        raise CoordinationError("RESOURCE_INVALID", "branch contains invalid character")
    return branch


def normalize_resource(resource: str) -> str:
    if not isinstance(resource, str) or ":" not in resource:
        raise CoordinationError("RESOURCE_INVALID", "resource must use file:, path: or branch:")
    kind, body = resource.split(":", 1)
    if kind == "file":
        return f"file:{_normalize_repo_path(body, allow_glob=False)}"
    if kind == "path":
        return f"path:{_normalize_repo_path(body, allow_glob=True)}"
    if kind == "branch":
        return f"branch:{_normalize_branch(body)}"
    raise CoordinationError("RESOURCE_INVALID", f"unsupported resource kind {kind!r}")


def normalize_resources(resources: list[str] | tuple[str, ...]) -> list[str]:
    if not isinstance(resources, (list, tuple)) or not resources:
        raise CoordinationError("RESOURCE_INVALID", "at least one resource is required")
    return sorted(set(normalize_resource(resource) for resource in resources))


def _split_resource(resource: str) -> tuple[str, str]:
    canonical = normalize_resource(resource)
    return canonical.split(":", 1)


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    canonical = _normalize_repo_path(pattern, allow_glob=True)
    out: list[str] = ["^"]
    i = 0
    while i < len(canonical):
        ch = canonical[i]
        if ch == "*":
            if i + 1 < len(canonical) and canonical[i + 1] == "*":
                i += 2
                if i < len(canonical) and canonical[i] == "/":
                    out.append("(?:.*/)?")
                    i += 1
                else:
                    out.append(".*")
                continue
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    out.append("$")
    return re.compile("".join(out))


def glob_matches_file(pattern: str, file_path: str) -> bool:
    canonical_file = _normalize_repo_path(file_path, allow_glob=False)
    return bool(glob_to_regex(pattern).fullmatch(canonical_file))


def _literal_prefix_segments(pattern: str) -> list[str]:
    segments: list[str] = []
    for segment in pattern.split("/"):
        if "*" in segment or "?" in segment:
            break
        segments.append(segment)
    return segments


def glob_may_overlap(pattern_a: str, pattern_b: str) -> bool:
    a = _normalize_repo_path(pattern_a, allow_glob=True)
    b = _normalize_repo_path(pattern_b, allow_glob=True)
    if a == b:
        return True
    prefix_a = _literal_prefix_segments(a)
    prefix_b = _literal_prefix_segments(b)
    for left, right in zip(prefix_a, prefix_b):
        if left != right:
            return False
    # The supported 0.1 implementation is intentionally conservative:
    # once either pattern reaches a wildcard, inability to prove disjointness
    # is treated as potential overlap.
    return True


def resources_conflict(left: str, right: str) -> bool:
    left_kind, left_body = _split_resource(left)
    right_kind, right_body = _split_resource(right)
    if "branch" in {left_kind, right_kind}:
        return left_kind == right_kind == "branch" and left_body == right_body
    if left_kind == right_kind == "file":
        return left_body == right_body
    if left_kind == "file" and right_kind == "path":
        return glob_matches_file(right_body, left_body)
    if left_kind == "path" and right_kind == "file":
        return glob_matches_file(left_body, right_body)
    if left_kind == right_kind == "path":
        return glob_may_overlap(left_body, right_body)
    raise CoordinationError("RESOURCE_INVALID", "unsupported resource comparison")


def _validate_reason(reason: str) -> str:
    value = _require_string(reason, "reason").strip()
    if len(value) > 500:
        raise CoordinationError("REASON_INVALID", "reason exceeds 500 characters")
    return value


def _validate_ttl(ttl_seconds: int, *, maximum: int = MAX_TTL_SECONDS) -> int:
    if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or ttl_seconds <= 0:
        raise CoordinationError("TTL_INVALID", "ttlSeconds must be a positive integer")
    if ttl_seconds > maximum:
        raise CoordinationError("TTL_INVALID", f"ttlSeconds exceeds {maximum}")
    return ttl_seconds


def _validate_intent(intent: dict[str, Any]) -> None:
    if not isinstance(intent, dict):
        raise CoordinationError("COORDINATION_STATE_INVALID", "intent must be an object")
    _require_string(intent.get("intentId"), "intent.intentId")
    normalize_resource(_require_string(intent.get("resource"), "intent.resource"))
    validate_owner(intent.get("owner"))
    _validate_reason(intent.get("reason"))
    _parse_time(_require_string(intent.get("createdAt"), "intent.createdAt"))
    _parse_time(_require_string(intent.get("expiresAt"), "intent.expiresAt"))


def _validate_lease(lease: dict[str, Any]) -> None:
    if not isinstance(lease, dict):
        raise CoordinationError("COORDINATION_STATE_INVALID", "lease must be an object")
    _require_string(lease.get("leaseId"), "lease.leaseId")
    normalize_resource(_require_string(lease.get("resource"), "lease.resource"))
    if lease.get("mode") != "exclusive-write":
        raise CoordinationError("COORDINATION_STATE_INVALID", "lease.mode must be exclusive-write")
    validate_owner(lease.get("owner"))
    _validate_reason(lease.get("reason"))
    _parse_time(_require_string(lease.get("acquiredAt"), "lease.acquiredAt"))
    _parse_time(_require_string(lease.get("renewedAt"), "lease.renewedAt"))
    _parse_time(_require_string(lease.get("expiresAt"), "lease.expiresAt"))
    _validate_ttl(lease.get("ttlSeconds"))


def _same_session(owner_a: dict[str, Any], owner_b: dict[str, Any]) -> bool:
    return validate_owner(owner_a)["session"] == validate_owner(owner_b)["session"]


def _is_expired(entry: dict[str, Any], now: datetime) -> bool:
    return _parse_time(entry["expiresAt"]) <= now


def compact_expired(state: dict[str, Any], now: datetime | str) -> dict[str, Any]:
    validate_state(state)
    current = _normalize_now(now)
    candidate = copy.deepcopy(state)
    candidate["intents"] = [entry for entry in candidate["intents"] if not _is_expired(entry, current)]
    candidate["leases"] = [entry for entry in candidate["leases"] if not _is_expired(entry, current)]
    return candidate


def active_leases(state: dict[str, Any], now: datetime | str) -> list[dict[str, Any]]:
    validate_state(state)
    current = _normalize_now(now)
    return [copy.deepcopy(entry) for entry in state["leases"] if not _is_expired(entry, current)]


def _event(
    action: str,
    transition_id: str,
    owner: dict[str, Any],
    resources: list[str],
    now: datetime,
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        "action": action,
        "transitionId": _require_string(transition_id, "transitionId").strip(),
        "owner": validate_owner(owner),
        "resources": list(resources),
        "at": _format_time(now),
    }
    payload.update(extra)
    return payload


def plan_intent(
    state: dict[str, Any],
    resources: list[str] | tuple[str, ...],
    owner: dict[str, Any],
    reason: str,
    now: datetime | str,
    transition_id: str,
    ttl_seconds: int = DEFAULT_INTENT_TTL_SECONDS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_state(state)
    current = _normalize_now(now)
    canonical_owner = validate_owner(owner)
    canonical_reason = _validate_reason(reason)
    canonical_resources = normalize_resources(resources)
    ttl = _validate_ttl(ttl_seconds)
    candidate = compact_expired(state, current)
    expires = _format_time(current + timedelta(seconds=ttl))
    for index, resource in enumerate(canonical_resources):
        candidate["intents"].append(
            {
                "intentId": f"{transition_id}:{index}",
                "resource": resource,
                "owner": copy.deepcopy(canonical_owner),
                "reason": canonical_reason,
                "createdAt": _format_time(current),
                "expiresAt": expires,
            }
        )
    candidate["intents"].sort(key=lambda entry: (entry["resource"], entry["intentId"]))
    event = _event("intent", transition_id, canonical_owner, canonical_resources, current, expiresAt=expires)
    validate_state(candidate)
    return candidate, event


def _conflicting_lease(
    leases: list[dict[str, Any]],
    resource: str,
    owner: dict[str, Any],
) -> dict[str, Any] | None:
    for lease in leases:
        if resources_conflict(resource, lease["resource"]):
            return lease
    return None


def plan_acquire(
    state: dict[str, Any],
    resources: list[str] | tuple[str, ...],
    owner: dict[str, Any],
    reason: str,
    now: datetime | str,
    transition_id: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_state(state)
    current = _normalize_now(now)
    canonical_owner = validate_owner(owner)
    canonical_reason = _validate_reason(reason)
    canonical_resources = normalize_resources(resources)
    ttl = _validate_ttl(ttl_seconds)
    candidate = compact_expired(state, current)
    existing = list(candidate["leases"])

    conflicts: list[dict[str, Any]] = []
    for resource in canonical_resources:
        lease = _conflicting_lease(existing, resource, canonical_owner)
        if lease is not None:
            conflicts.append(
                {
                    "requested": resource,
                    "held": lease["resource"],
                    "owner": copy.deepcopy(lease["owner"]),
                    "expiresAt": lease["expiresAt"],
                }
            )
    if conflicts:
        raise CoordinationError("LEASE_CONFLICT", repr(conflicts))

    acquired_at = _format_time(current)
    expires_at = _format_time(current + timedelta(seconds=ttl))
    new_entries = []
    for index, resource in enumerate(canonical_resources):
        new_entries.append(
            {
                "leaseId": f"{transition_id}:{index}",
                "resource": resource,
                "mode": "exclusive-write",
                "owner": copy.deepcopy(canonical_owner),
                "reason": canonical_reason,
                "acquiredAt": acquired_at,
                "renewedAt": acquired_at,
                "expiresAt": expires_at,
                "ttlSeconds": ttl,
            }
        )
    candidate["leases"].extend(new_entries)
    candidate["leases"].sort(key=lambda entry: (entry["resource"], entry["leaseId"]))
    event = _event(
        "acquire",
        transition_id,
        canonical_owner,
        canonical_resources,
        current,
        expiresAt=expires_at,
        leaseIds=[entry["leaseId"] for entry in new_entries],
    )
    validate_state(candidate)
    return candidate, event


def plan_renew_mine(
    state: dict[str, Any],
    owner: dict[str, Any],
    now: datetime | str,
    transition_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_state(state)
    current = _normalize_now(now)
    canonical_owner = validate_owner(owner)
    candidate = compact_expired(state, current)
    renewed_resources: list[str] = []
    for lease in candidate["leases"]:
        if _same_session(lease["owner"], canonical_owner):
            ttl = _validate_ttl(lease["ttlSeconds"])
            lease["renewedAt"] = _format_time(current)
            lease["expiresAt"] = _format_time(current + timedelta(seconds=ttl))
            renewed_resources.append(lease["resource"])
    if not renewed_resources:
        raise CoordinationError("LEASE_NOT_OWNER", "session owns no active leases")
    renewed_resources.sort()
    event = _event("renew", transition_id, canonical_owner, renewed_resources, current)
    validate_state(candidate)
    return candidate, event


def plan_release(
    state: dict[str, Any],
    owner: dict[str, Any],
    now: datetime | str,
    transition_id: str,
    resources: list[str] | tuple[str, ...] | None = None,
    *,
    mine: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_state(state)
    current = _normalize_now(now)
    canonical_owner = validate_owner(owner)
    if mine == (resources is not None):
        raise CoordinationError("RELEASE_INVALID", "choose exactly one of resources or mine=True")
    candidate = compact_expired(state, current)

    if mine:
        target_resources = sorted(
            lease["resource"] for lease in candidate["leases"] if _same_session(lease["owner"], canonical_owner)
        )
        if not target_resources:
            raise CoordinationError("LEASE_NOT_OWNER", "session owns no active leases")
    else:
        assert resources is not None
        target_resources = normalize_resources(resources)
        by_resource = {lease["resource"]: lease for lease in candidate["leases"]}
        for resource in target_resources:
            lease = by_resource.get(resource)
            if lease is None:
                raise CoordinationError("LEASE_NOT_FOUND", resource)
            if not _same_session(lease["owner"], canonical_owner):
                raise CoordinationError("LEASE_NOT_OWNER", resource)

    target_set = set(target_resources)
    candidate["leases"] = [
        lease for lease in candidate["leases"]
        if not (lease["resource"] in target_set and _same_session(lease["owner"], canonical_owner))
    ]
    event = _event("release-mine" if mine else "release", transition_id, canonical_owner, target_resources, current)
    validate_state(candidate)
    return candidate, event


def can_write(
    state: dict[str, Any],
    resource: str,
    owner: dict[str, Any],
    now: datetime | str,
) -> tuple[bool, dict[str, Any] | None]:
    validate_state(state)
    current = _normalize_now(now)
    canonical_owner = validate_owner(owner)
    canonical_resource = normalize_resource(resource)
    for lease in state["leases"]:
        if _is_expired(lease, current):
            continue
        if resources_conflict(canonical_resource, lease["resource"]):
            if _same_session(lease["owner"], canonical_owner):
                return True, copy.deepcopy(lease)
            return False, copy.deepcopy(lease)
    return True, None
