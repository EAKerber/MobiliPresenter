from __future__ import annotations

import copy
import re
from typing import Any, Iterable

from tools import agent_cycle, agent_cycle_resources
from tools.canonical import stable_hash
from tools.semantics.work import WorkStatus

SCHEMA_VERSION = "AgentCycleObligationInventory 0.1"
DISPOSITION_SCHEMA_VERSION = "AgentCycleObligationDispositionSet 0.1"
REPOSITORY = agent_cycle_resources.REPOSITORY
CYCLE_RE = agent_cycle_resources.CYCLE_RE
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
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
OBSERVATION_STATUSES = {"PASS", "UNKNOWN"}
DISPOSITION_FIELDS = {
    "obligationHash",
    "kind",
    "observationStatus",
    "reasonCodes",
    "domainState",
    "dispositionHash",
}
DISPOSITION_SET_FIELDS = {
    "schemaVersion",
    "repository",
    "cycleInstanceId",
    "resourceSetHash",
    "inventoryHash",
    "coverage",
    "observationStatus",
    "dispositions",
    "enforcementEligible",
    "readOnly",
    "semanticAuthority",
    "authorizesMutation",
    "dispositionSetHash",
}
WORK_STATE_FIELDS = {"authorityHead", "exists", "status"}
GIT_STATE_FIELDS = {
    "exists",
    "headSha",
    "workAuthorityHead",
    "activeWorkBindings",
}
LEASE_STATE_FIELDS = {"state", "reportHash"}
WORK_BINDING_FIELDS = {"workId", "workerId", "status", "branch", "prNumber"}
LEASE_STATES = {"NONE", "ACTIVE", "RELEASED", "EXPIRED", "UNKNOWN"}


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(code)
    return value.strip()


def _hash(value: Any, code: str) -> str:
    if not isinstance(value, str) or HASH_RE.fullmatch(value) is None:
        raise RuntimeError(code)
    return value


def _sha(value: Any, code: str) -> str:
    if not isinstance(value, str) or SHA_RE.fullmatch(value) is None:
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
    body = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "inventoryHash"
    }
    if value.get("inventoryHash") != stable_hash(body):
        raise RuntimeError("AGENT_CYCLE_OBLIGATION_INVENTORY_HASH_MISMATCH")
    if resource_set is not None:
        expected = build_inventory(resource_set, work_ref=work_ref)
        if value != expected:
            raise RuntimeError("AGENT_CYCLE_OBLIGATION_INVENTORY_BINDING_MISMATCH")
    return value


def _reason_codes(value: Any, status: str) -> list[str]:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item for item in value)
        or value != sorted(set(value))
    ):
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_REASON_CODES_INVALID")
    if status == "PASS" and value:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_REASON_CODES_INVALID")
    if status == "UNKNOWN" and not value:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_REASON_CODES_INVALID")
    return value


def _work_state(value: Any, status: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != WORK_STATE_FIELDS:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_WORK_STATE_INVALID")
    head = value.get("authorityHead")
    exists = value.get("exists")
    work_status = value.get("status")
    if head is None:
        if exists is not None or work_status is not None or status != "UNKNOWN":
            raise RuntimeError("AGENT_CYCLE_DISPOSITION_WORK_STATE_INVALID")
        return value
    _sha(head, "AGENT_CYCLE_DISPOSITION_WORK_STATE_INVALID")
    if type(exists) is not bool:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_WORK_STATE_INVALID")
    if exists:
        WorkStatus.parse(str(work_status or ""))
    elif work_status is not None:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_WORK_STATE_INVALID")
    return value


def _work_binding(value: Any, branch: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != WORK_BINDING_FIELDS:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_WORK_BINDING_INVALID")
    agent_cycle.validate_work_ref({"workId": value.get("workId")})
    WorkStatus.parse(str(value.get("status") or ""))
    if value.get("branch") != branch:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_WORK_BINDING_INVALID")
    worker = value.get("workerId")
    if worker is not None and (not isinstance(worker, str) or not worker):
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_WORK_BINDING_INVALID")
    pr_number = value.get("prNumber")
    if pr_number is not None and (
        not isinstance(pr_number, int)
        or isinstance(pr_number, bool)
        or pr_number <= 0
    ):
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_WORK_BINDING_INVALID")
    return value


def _git_state(value: Any, status: str, branch: str | None) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != GIT_STATE_FIELDS:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_GIT_STATE_INVALID")
    exists = value.get("exists")
    head = value.get("headSha")
    if exists is None:
        if head is not None:
            raise RuntimeError("AGENT_CYCLE_DISPOSITION_GIT_STATE_INVALID")
    elif type(exists) is not bool:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_GIT_STATE_INVALID")
    elif exists:
        _sha(head, "AGENT_CYCLE_DISPOSITION_GIT_STATE_INVALID")
    elif head is not None:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_GIT_STATE_INVALID")

    work_head = value.get("workAuthorityHead")
    bindings = value.get("activeWorkBindings")
    if work_head is None:
        if bindings is not None:
            raise RuntimeError("AGENT_CYCLE_DISPOSITION_GIT_STATE_INVALID")
    else:
        _sha(work_head, "AGENT_CYCLE_DISPOSITION_GIT_STATE_INVALID")
        if not isinstance(bindings, list):
            raise RuntimeError("AGENT_CYCLE_DISPOSITION_GIT_STATE_INVALID")
        inferred_branch = branch
        if inferred_branch is None and bindings:
            first_branch = bindings[0].get("branch") if isinstance(bindings[0], dict) else None
            if not isinstance(first_branch, str) or not first_branch:
                raise RuntimeError("AGENT_CYCLE_DISPOSITION_GIT_STATE_INVALID")
            inferred_branch = first_branch
        checked = [
            copy.deepcopy(_work_binding(item, inferred_branch or item.get("branch")))
            for item in bindings
        ]
        if (
            checked != sorted(checked, key=lambda item: item["workId"])
            or len(checked) != len({item["workId"] for item in checked})
        ):
            raise RuntimeError("AGENT_CYCLE_DISPOSITION_GIT_STATE_INVALID")
    if status == "PASS" and (exists is None or work_head is None):
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_GIT_STATE_INVALID")
    return value


def _lease_state(value: Any, status: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != LEASE_STATE_FIELDS:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_LEASE_STATE_INVALID")
    state = value.get("state")
    report_hash = value.get("reportHash")
    if report_hash is None:
        if state is not None or status != "UNKNOWN":
            raise RuntimeError("AGENT_CYCLE_DISPOSITION_LEASE_STATE_INVALID")
        return value
    _hash(report_hash, "AGENT_CYCLE_DISPOSITION_LEASE_STATE_INVALID")
    if state not in LEASE_STATES:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_LEASE_STATE_INVALID")
    return value


def disposition(
    obligation_value: dict[str, Any],
    *,
    observation_status: str,
    reason_codes: list[str],
    domain_state: dict[str, Any],
) -> dict[str, Any]:
    obligation_value = validate_obligation(obligation_value)
    if observation_status not in OBSERVATION_STATUSES:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_STATUS_INVALID")
    reasons = _reason_codes(reason_codes, observation_status)
    kind = obligation_value["kind"]
    if kind == "work-disposition":
        checked_state = _work_state(domain_state, observation_status)
    elif kind == "git-branch-disposition":
        checked_state = _git_state(
            domain_state,
            observation_status,
            obligation_value["locator"]["branch"],
        )
    elif kind == "write-lifecycle-disposition":
        checked_state = _lease_state(domain_state, observation_status)
    else:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_KIND_INVALID")
    body = {
        "obligationHash": obligation_value["obligationHash"],
        "kind": kind,
        "observationStatus": observation_status,
        "reasonCodes": copy.deepcopy(reasons),
        "domainState": copy.deepcopy(checked_state),
    }
    return {**body, "dispositionHash": stable_hash(body)}


def validate_disposition(
    value: Any, obligation_value: dict[str, Any] | None = None
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != DISPOSITION_FIELDS:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_FIELDS_INVALID")
    kind = value.get("kind")
    status = value.get("observationStatus")
    if kind not in OBLIGATION_KINDS or status not in OBSERVATION_STATUSES:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_INVALID")
    _hash(
        value.get("obligationHash"),
        "AGENT_CYCLE_DISPOSITION_OBLIGATION_HASH_INVALID",
    )
    _hash(value.get("dispositionHash"), "AGENT_CYCLE_DISPOSITION_HASH_INVALID")
    _reason_codes(value.get("reasonCodes"), status)
    locator = None
    if obligation_value is not None:
        checked_obligation = validate_obligation(obligation_value)
        if (
            checked_obligation["obligationHash"] != value["obligationHash"]
            or checked_obligation["kind"] != kind
        ):
            raise RuntimeError("AGENT_CYCLE_DISPOSITION_OBLIGATION_MISMATCH")
        locator = checked_obligation["locator"]
    if kind == "work-disposition":
        _work_state(value.get("domainState"), status)
    elif kind == "git-branch-disposition":
        _git_state(
            value.get("domainState"),
            status,
            locator["branch"] if locator is not None else None,
        )
    else:
        _lease_state(value.get("domainState"), status)
    body = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "dispositionHash"
    }
    if value["dispositionHash"] != stable_hash(body):
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_HASH_MISMATCH")
    return value


def build_disposition_set(
    inventory: dict[str, Any], dispositions: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    inventory = validate_inventory(inventory)
    obligations = {
        item["obligationHash"]: item for item in inventory["obligations"]
    }
    supplied: dict[str, dict[str, Any]] = {}
    for raw in dispositions:
        if not isinstance(raw, dict):
            raise RuntimeError("AGENT_CYCLE_DISPOSITION_LIST_INVALID")
        obligation_hash = raw.get("obligationHash")
        obligation_value = obligations.get(obligation_hash)
        if obligation_value is None or obligation_hash in supplied:
            raise RuntimeError("AGENT_CYCLE_DISPOSITION_COVERAGE_INVALID")
        supplied[obligation_hash] = copy.deepcopy(
            validate_disposition(raw, obligation_value)
        )
    if set(supplied) != set(obligations):
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_COVERAGE_INVALID")
    canonical = [supplied[key] for key in sorted(supplied)]
    body = {
        "schemaVersion": DISPOSITION_SCHEMA_VERSION,
        "repository": inventory["repository"],
        "cycleInstanceId": inventory["cycleInstanceId"],
        "resourceSetHash": inventory["resourceSetHash"],
        "inventoryHash": inventory["inventoryHash"],
        "coverage": copy.deepcopy(inventory["coverage"]),
        "observationStatus": (
            "PASS"
            if all(item["observationStatus"] == "PASS" for item in canonical)
            else "UNKNOWN"
        ),
        "dispositions": canonical,
        "enforcementEligible": False,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "dispositionSetHash": stable_hash(body)}


def validate_disposition_set(
    value: Any, inventory: dict[str, Any] | None = None
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != DISPOSITION_SET_FIELDS:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_SET_FIELDS_INVALID")
    if value.get("schemaVersion") != DISPOSITION_SCHEMA_VERSION:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_SET_SCHEMA_INVALID")
    if value.get("repository") != REPOSITORY:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_SET_REPOSITORY_INVALID")
    cycle_instance_id = value.get("cycleInstanceId")
    if (
        not isinstance(cycle_instance_id, str)
        or CYCLE_RE.fullmatch(cycle_instance_id) is None
    ):
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_SET_CYCLE_INVALID")
    _hash(
        value.get("resourceSetHash"),
        "AGENT_CYCLE_DISPOSITION_SET_RESOURCE_HASH_INVALID",
    )
    _hash(
        value.get("inventoryHash"),
        "AGENT_CYCLE_DISPOSITION_SET_INVENTORY_HASH_INVALID",
    )
    agent_cycle_resources.validate_coverage(value.get("coverage"))
    if value.get("observationStatus") not in OBSERVATION_STATUSES:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_SET_STATUS_INVALID")
    dispositions = value.get("dispositions")
    if not isinstance(dispositions, list):
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_LIST_INVALID")
    checked = [copy.deepcopy(validate_disposition(item)) for item in dispositions]
    if (
        checked != sorted(checked, key=lambda item: item["obligationHash"])
        or len(checked) != len({item["obligationHash"] for item in checked})
    ):
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_LIST_NOT_CANONICAL")
    expected_status = (
        "PASS"
        if all(item["observationStatus"] == "PASS" for item in checked)
        else "UNKNOWN"
    )
    if value.get("observationStatus") != expected_status:
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_SET_STATUS_MISMATCH")
    if (
        value.get("enforcementEligible") is not False
        or value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_SET_AUTHORITY_INVALID")
    body = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "dispositionSetHash"
    }
    if value.get("dispositionSetHash") != stable_hash(body):
        raise RuntimeError("AGENT_CYCLE_DISPOSITION_SET_HASH_MISMATCH")
    if inventory is not None:
        expected = build_disposition_set(inventory, dispositions)
        if value != expected:
            raise RuntimeError("AGENT_CYCLE_DISPOSITION_SET_BINDING_MISMATCH")
    return value
