from __future__ import annotations

import copy
import re
from typing import Any, Iterable

from tools import agent_cycle, agent_cycle_resources
from tools.canonical import stable_hash

SCHEMA_VERSION = "AgentCycleObligationInventory 0.1"
REPOSITORY = agent_cycle_resources.REPOSITORY
CYCLE_RE = agent_cycle_resources.CYCLE_RE
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
OBLIGATION_KINDS = {
    "git-branch-disposition",
    "work-disposition",
    "write-lifecycle-disposition",
}
OBLIGATION_FIELDS = {"kind", "locator", "obligationHash"}
INVENTORY_FIELDS = {
    "schemaVersion",
    "repository",
    "cycleInstanceId",
    "workRef",
    "resourceSetHash",
    "coverage",
    "obligations",
    "enforcementEligible",
    "readOnly",
    "semanticAuthority",
    "authorizesMutation",
    "inventoryHash",
}


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(code)
    return value.strip()


def _hash(value: Any, code: str) -> str:
    if not isinstance(value, str) or HASH_RE.fullmatch(value) is None:
        raise RuntimeError(code)
    return value


def _locator(kind: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("AGENT_CYCLE_OBLIGATION_LOCATOR_INVALID")
    expected = {
        "git-branch-disposition": {"repository", "branch"},
        "work-disposition": {"workId"},
        "write-lifecycle-disposition": {
            "repository",
            "branch",
            "role",
            "sessionId",
        },
    }
    fields = expected.get(kind)
    if fields is None or set(value) != fields:
        raise RuntimeError("AGENT_CYCLE_OBLIGATION_LOCATOR_INVALID")
    out = copy.deepcopy(value)
    if kind in {"git-branch-disposition", "write-lifecycle-disposition"}:
        if out.get("repository") != REPOSITORY:
            raise RuntimeError("AGENT_CYCLE_OBLIGATION_REPOSITORY_INVALID")
        _text(out.get("branch"), "AGENT_CYCLE_OBLIGATION_BRANCH_INVALID")
    if kind == "work-disposition":
        try:
            agent_cycle.validate_work_ref({"workId": out.get("workId")})
        except RuntimeError as exc:
            raise RuntimeError("AGENT_CYCLE_OBLIGATION_WORK_INVALID") from exc
    if kind == "write-lifecycle-disposition":
        _text(out.get("role"), "AGENT_CYCLE_OBLIGATION_LIFECYCLE_INVALID")
        _text(out.get("sessionId"), "AGENT_CYCLE_OBLIGATION_LIFECYCLE_INVALID")
    return out


def obligation(kind: str, locator: dict[str, Any]) -> dict[str, Any]:
    if kind not in OBLIGATION_KINDS:
        raise RuntimeError("AGENT_CYCLE_OBLIGATION_KIND_INVALID")
    identity = {"kind": kind, "locator": _locator(kind, locator)}
    return {**identity, "obligationHash": stable_hash(identity)}


def validate_obligation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != OBLIGATION_FIELDS:
        raise RuntimeError("AGENT_CYCLE_OBLIGATION_FIELDS_INVALID")
    expected = obligation(value.get("kind"), value.get("locator"))
    if value != expected:
        raise RuntimeError("AGENT_CYCLE_OBLIGATION_NOT_CANONICAL")
    return value


def _canonical_obligations(
    resources: Iterable[dict[str, Any]], work_ref: dict[str, str] | None
) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}

    def add(item: dict[str, Any]) -> None:
        checked = validate_obligation(item)
        found[checked["obligationHash"]] = copy.deepcopy(checked)

    if work_ref is not None:
        normalized = agent_cycle.validate_work_ref(work_ref)
        assert normalized is not None
        add(obligation("work-disposition", {"workId": normalized["workId"]}))

    for raw in resources:
        item = agent_cycle_resources.validate_resource(raw)
        kind = item["kind"]
        locator = item["locator"]
        if kind in {"git-branch", "git-path"}:
            add(
                obligation(
                    "git-branch-disposition",
                    {
                        "repository": locator["repository"],
                        "branch": locator["branch"],
                    },
                )
            )
        elif kind == "domain-subject":
            if (
                locator["domain"] == "continuation"
                and locator["subjectKind"] == "continuation"
            ):
                add(
                    obligation(
                        "work-disposition", {"workId": locator["subjectId"]}
                    )
                )
        elif kind == "lease-scope":
            add(
                obligation(
                    "write-lifecycle-disposition",
                    {
                        "repository": locator["repository"],
                        "branch": locator["branch"],
                        "role": locator["role"],
                        "sessionId": locator["sessionId"],
                    },
                )
            )
        elif kind == "coordination-lease":
            # Exact lease identity is evidence consumed by R3B2. The lifecycle
            # obligation is represented once at lease-scope granularity.
            continue
    return [found[key] for key in sorted(found)]


def build_inventory(
    resource_set: dict[str, Any], *, work_ref: dict[str, str] | None = None
) -> dict[str, Any]:
    resource_set = agent_cycle_resources.validate_resource_set(resource_set)
    normalized_work = agent_cycle.validate_work_ref(work_ref)
    body = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": resource_set["repository"],
        "cycleInstanceId": resource_set["cycleInstanceId"],
        "workRef": copy.deepcopy(normalized_work),
        "resourceSetHash": resource_set["resourceSetHash"],
        "coverage": copy.deepcopy(resource_set["coverage"]),
        "obligations": _canonical_obligations(
            resource_set["resources"], normalized_work
        ),
        "enforcementEligible": False,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "inventoryHash": stable_hash(body)}


def validate_inventory(
    value: Any,
    resource_set: dict[str, Any] | None = None,
    *,
    work_ref: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != INVENTORY_FIELDS:
        raise RuntimeError("AGENT_CYCLE_OBLIGATION_INVENTORY_FIELDS_INVALID")
    if value.get("schemaVersion") != SCHEMA_VERSION:
        raise RuntimeError("AGENT_CYCLE_OBLIGATION_INVENTORY_SCHEMA_INVALID")
    if value.get("repository") != REPOSITORY:
        raise RuntimeError("AGENT_CYCLE_OBLIGATION_INVENTORY_REPOSITORY_INVALID")
    cycle_instance_id = value.get("cycleInstanceId")
    if not isinstance(cycle_instance_id, str) or CYCLE_RE.fullmatch(cycle_instance_id) is None:
        raise RuntimeError("AGENT_CYCLE_OBLIGATION_INVENTORY_CYCLE_INVALID")
    _hash(value.get("resourceSetHash"), "AGENT_CYCLE_OBLIGATION_RESOURCE_SET_HASH_INVALID")
    normalized_work = agent_cycle.validate_work_ref(value.get("workRef"))
    if normalized_work != value.get("workRef"):
        raise RuntimeError("AGENT_CYCLE_OBLIGATION_WORK_REF_INVALID")
    agent_cycle_resources.validate_coverage(value.get("coverage"))
    obligations = value.get("obligations")
    if not isinstance(obligations, list):
        raise RuntimeError("AGENT_CYCLE_OBLIGATION_LIST_INVALID")
    checked = [copy.deepcopy(validate_obligation(item)) for item in obligations]
    expected_order = sorted(checked, key=lambda item: item["obligationHash"])
    if checked != expected_order or len(checked) != len(
        {item["obligationHash"] for item in checked}
    ):
        raise RuntimeError("AGENT_CYCLE_OBLIGATION_LIST_NOT_CANONICAL")
    if (
        value.get("enforcementEligible") is not False
        or value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise RuntimeError("AGENT_CYCLE_OBLIGATION_INVENTORY_AUTHORITY_INVALID")
    body = {key: copy.deepcopy(item) for key, item in value.items() if key != "inventoryHash"}
    if value.get("inventoryHash") != stable_hash(body):
        raise RuntimeError("AGENT_CYCLE_OBLIGATION_INVENTORY_HASH_MISMATCH")

    if resource_set is not None:
        expected = build_inventory(resource_set, work_ref=work_ref)
        if value != expected:
            raise RuntimeError("AGENT_CYCLE_OBLIGATION_INVENTORY_BINDING_MISMATCH")
    return value
