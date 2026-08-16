"""Pure deterministic envelope for planned state transitions and verified receipts."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

PLAN_SCHEMA = "TransitionPlan 0.1"
RECEIPT_SCHEMA = "TransitionReceipt 0.1"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
REVERSIBILITY = {"revertible", "compensatable", "irreversible"}


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def state_hash(value: dict[str, Any] | None) -> str | None:
    return None if value is None else stable_hash(value)


def _identifier(value: Any, code: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise RuntimeError(code)
    return value


def _subject(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"kind", "id"}:
        raise RuntimeError("TRANSITION_SUBJECT_INVALID")
    return {
        "kind": _identifier(value.get("kind"), "TRANSITION_SUBJECT_INVALID"),
        "id": _identifier(value.get("id"), "TRANSITION_SUBJECT_INVALID"),
    }


def _authority(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"kind", "locator"}:
        raise RuntimeError("TRANSITION_AUTHORITY_INVALID")
    kind = _identifier(value.get("kind"), "TRANSITION_AUTHORITY_INVALID")
    locator = value.get("locator")
    if not isinstance(locator, dict) or not locator:
        raise RuntimeError("TRANSITION_AUTHORITY_INVALID")
    for key, item in locator.items():
        if not isinstance(key, str) or not key or not isinstance(item, (str, int)) or isinstance(item, bool):
            raise RuntimeError("TRANSITION_AUTHORITY_INVALID")
        if isinstance(item, str) and not item:
            raise RuntimeError("TRANSITION_AUTHORITY_INVALID")
    return {"kind": kind, "locator": copy.deepcopy(locator)}


def _core(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(value) for key, value in plan.items() if key != "planHash"}


def build_plan(
    *,
    domain: str,
    action: str,
    subject: dict[str, Any],
    authority: dict[str, Any],
    before: dict[str, Any] | None,
    candidate: dict[str, Any],
    intent: dict[str, Any],
    reversibility: str = "revertible",
) -> dict[str, Any]:
    domain = _identifier(domain, "TRANSITION_DOMAIN_INVALID")
    action = _identifier(action, "TRANSITION_ACTION_INVALID")
    canonical_subject = _subject(subject)
    canonical_authority = _authority(authority)
    if not isinstance(candidate, dict):
        raise RuntimeError("TRANSITION_CANDIDATE_INVALID")
    if not isinstance(intent, dict):
        raise RuntimeError("TRANSITION_INTENT_INVALID")
    if reversibility not in REVERSIBILITY:
        raise RuntimeError("TRANSITION_REVERSIBILITY_INVALID")
    core = {
        "schemaVersion": PLAN_SCHEMA,
        "domain": domain,
        "action": action,
        "subject": canonical_subject,
        "authority": canonical_authority,
        "beforeStateHash": state_hash(before),
        "afterStateHash": state_hash(candidate),
        "intent": copy.deepcopy(intent),
        "candidate": copy.deepcopy(candidate),
        "reversibility": reversibility,
    }
    return {**core, "planHash": stable_hash(core)}


def validate_plan(plan: Any) -> dict[str, Any]:
    expected = {
        "schemaVersion", "domain", "action", "subject", "authority",
        "beforeStateHash", "afterStateHash", "intent", "candidate",
        "reversibility", "planHash",
    }
    if not isinstance(plan, dict) or set(plan) != expected:
        raise RuntimeError("TRANSITION_PLAN_FIELDS_INVALID")
    if plan.get("schemaVersion") != PLAN_SCHEMA:
        raise RuntimeError("TRANSITION_PLAN_SCHEMA_UNSUPPORTED")
    _identifier(plan.get("domain"), "TRANSITION_DOMAIN_INVALID")
    _identifier(plan.get("action"), "TRANSITION_ACTION_INVALID")
    _subject(plan.get("subject"))
    _authority(plan.get("authority"))
    before_hash = plan.get("beforeStateHash")
    if before_hash is not None and (not isinstance(before_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", before_hash)):
        raise RuntimeError("TRANSITION_BEFORE_HASH_INVALID")
    after_hash = plan.get("afterStateHash")
    if not isinstance(after_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", after_hash):
        raise RuntimeError("TRANSITION_AFTER_HASH_INVALID")
    if not isinstance(plan.get("intent"), dict):
        raise RuntimeError("TRANSITION_INTENT_INVALID")
    if not isinstance(plan.get("candidate"), dict):
        raise RuntimeError("TRANSITION_CANDIDATE_INVALID")
    if plan.get("reversibility") not in REVERSIBILITY:
        raise RuntimeError("TRANSITION_REVERSIBILITY_INVALID")
    if state_hash(plan["candidate"]) != after_hash:
        raise RuntimeError("TRANSITION_CANDIDATE_HASH_MISMATCH")
    plan_hash = plan.get("planHash")
    if not isinstance(plan_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_hash):
        raise RuntimeError("TRANSITION_PLAN_HASH_INVALID")
    if stable_hash(_core(plan)) != plan_hash:
        raise RuntimeError("TRANSITION_PLAN_HASH_MISMATCH")
    return plan


def require_expected_plan(plan: dict[str, Any], expected_plan: str | None) -> None:
    validate_plan(plan)
    if not expected_plan:
        raise RuntimeError("TRANSITION_EXPECTED_PLAN_REQUIRED")
    if expected_plan != plan["planHash"]:
        raise RuntimeError("TRANSITION_EXPECTED_PLAN_MISMATCH")


def verify_before_state(plan: dict[str, Any], current: dict[str, Any] | None) -> None:
    validate_plan(plan)
    if state_hash(current) != plan["beforeStateHash"]:
        raise RuntimeError("TRANSITION_PLAN_STALE")


def _receipt_core(
    plan: dict[str, Any],
    readback: dict[str, Any],
    authority_revision: str | None,
) -> dict[str, Any]:
    return {
        "schemaVersion": RECEIPT_SCHEMA,
        "planHash": plan["planHash"],
        "domain": plan["domain"],
        "action": plan["action"],
        "subject": copy.deepcopy(plan["subject"]),
        "authority": copy.deepcopy(plan["authority"]),
        "beforeStateHash": plan["beforeStateHash"],
        "afterStateHash": plan["afterStateHash"],
        "readbackStateHash": state_hash(readback),
        "authorityRevision": authority_revision,
        "verified": True,
    }


def build_receipt(
    plan: dict[str, Any],
    readback: dict[str, Any],
    *,
    authority_revision: str | None = None,
) -> dict[str, Any]:
    validate_plan(plan)
    if not isinstance(readback, dict):
        raise RuntimeError("TRANSITION_READBACK_INVALID")
    if state_hash(readback) != plan["afterStateHash"]:
        raise RuntimeError("TRANSITION_READBACK_MISMATCH")
    if authority_revision is not None and (not isinstance(authority_revision, str) or not authority_revision):
        raise RuntimeError("TRANSITION_AUTHORITY_REVISION_INVALID")
    core = _receipt_core(plan, readback, authority_revision)
    return {**core, "receiptHash": stable_hash(core)}


def validate_receipt(receipt: Any, plan: dict[str, Any] | None = None) -> dict[str, Any]:
    expected = {
        "schemaVersion", "planHash", "domain", "action", "subject", "authority",
        "beforeStateHash", "afterStateHash", "readbackStateHash", "authorityRevision",
        "verified", "receiptHash",
    }
    if not isinstance(receipt, dict) or set(receipt) != expected:
        raise RuntimeError("TRANSITION_RECEIPT_FIELDS_INVALID")
    if receipt.get("schemaVersion") != RECEIPT_SCHEMA:
        raise RuntimeError("TRANSITION_RECEIPT_SCHEMA_UNSUPPORTED")
    _identifier(receipt.get("domain"), "TRANSITION_DOMAIN_INVALID")
    _identifier(receipt.get("action"), "TRANSITION_ACTION_INVALID")
    _subject(receipt.get("subject"))
    _authority(receipt.get("authority"))
    for key in ("planHash", "afterStateHash", "readbackStateHash", "receiptHash"):
        if not isinstance(receipt.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", receipt[key]):
            raise RuntimeError("TRANSITION_RECEIPT_HASH_INVALID")
    before_hash = receipt.get("beforeStateHash")
    if before_hash is not None and (not isinstance(before_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", before_hash)):
        raise RuntimeError("TRANSITION_RECEIPT_HASH_INVALID")
    revision = receipt.get("authorityRevision")
    if revision is not None and (not isinstance(revision, str) or not revision):
        raise RuntimeError("TRANSITION_AUTHORITY_REVISION_INVALID")
    if receipt.get("verified") is not True or receipt["readbackStateHash"] != receipt["afterStateHash"]:
        raise RuntimeError("TRANSITION_RECEIPT_NOT_VERIFIED")
    core = {key: copy.deepcopy(value) for key, value in receipt.items() if key != "receiptHash"}
    if stable_hash(core) != receipt["receiptHash"]:
        raise RuntimeError("TRANSITION_RECEIPT_HASH_MISMATCH")
    if plan is not None:
        validate_plan(plan)
        for key in ("planHash", "domain", "action", "subject", "authority", "beforeStateHash", "afterStateHash"):
            if receipt[key] != plan[key]:
                raise RuntimeError("TRANSITION_RECEIPT_PLAN_MISMATCH")
    return receipt
