from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from tools import (
    agent_cycle,
    agent_cycle_close,
    agent_cycle_obligations,
    agent_cycle_resources,
)
from tools.canonical import stable_hash

SCHEMA_VERSION = "AgentCycleCloseReview 0.1"
REPOSITORY = agent_cycle_resources.REPOSITORY
STATUSES = {
    "CLEAN_TERMINATION",
    "CARRIED_FORWARD",
    "OUTSTANDING_OBLIGATIONS",
    "INSUFFICIENT_OBSERVATION",
}
OUTCOMES = {"DISCHARGED", "CARRIED_FORWARD", "OUTSTANDING", "UNKNOWN"}
FIELDS = {
    "schemaVersion",
    "repository",
    "cycleId",
    "cycleInstanceId",
    "contextHash",
    "closureHash",
    "receiptHash",
    "resourceSetHash",
    "inventoryHash",
    "dispositionSetHash",
    "coverage",
    "closureStatus",
    "mutationReadback",
    "obligations",
    "summary",
    "status",
    "reasonCodes",
    "cleanTerminationProven",
    "readOnly",
    "semanticAuthority",
    "authorizesMutation",
    "reviewHash",
}
OBLIGATION_FIELDS = {
    "obligationHash",
    "kind",
    "locator",
    "observationStatus",
    "outcome",
    "reasonCodes",
    "domainState",
    "dispositionHash",
    "assessmentHash",
}
MUTATION_READBACK_FIELDS = {
    "required",
    "status",
    "evidenceCount",
    "coveredDurableChanges",
    "uncoveredDurableChanges",
    "readbackHash",
}
SUMMARY_FIELDS = {
    "obligationCount",
    "dischargedCount",
    "carriedForwardCount",
    "outstandingCount",
    "unknownCount",
    "handoffCount",
    "durableChangeCount",
    "uncoveredDurableChangeCount",
}


def _load_json(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_INPUT_INVALID") from exc


def _canonical_reasons(values: list[str]) -> list[str]:
    return sorted(set(values))


def _classify_work(disposition: dict[str, Any]) -> tuple[str, list[str]]:
    if disposition["observationStatus"] == "UNKNOWN":
        return "UNKNOWN", list(disposition["reasonCodes"])
    state = disposition["domainState"]
    if state["exists"] is False:
        return "OUTSTANDING", ["WORK_DISPOSITION_MISSING_AT_CLOSE"]
    status = state["status"]
    if status == "DONE":
        return "DISCHARGED", ["WORK_DONE"]
    if status == "HANDOFF":
        return "CARRIED_FORWARD", ["WORK_HANDOFF"]
    if status == "WAITING":
        return "CARRIED_FORWARD", ["WORK_WAITING"]
    return "CARRIED_FORWARD", ["WORK_ACTIVE"]


def _classify_git(disposition: dict[str, Any]) -> tuple[str, list[str]]:
    if disposition["observationStatus"] == "UNKNOWN":
        return "UNKNOWN", list(disposition["reasonCodes"])
    state = disposition["domainState"]
    if state["exists"] is False:
        return "DISCHARGED", ["GIT_BRANCH_ABSENT"]
    bindings = state["activeWorkBindings"]
    if bindings:
        return "CARRIED_FORWARD", ["GIT_BRANCH_BOUND_TO_ACTIVE_WORK"]
    return "OUTSTANDING", ["GIT_BRANCH_UNBOUND_AT_CLOSE"]


def _classify_lifecycle(disposition: dict[str, Any]) -> tuple[str, list[str]]:
    if disposition["observationStatus"] == "UNKNOWN":
        return "UNKNOWN", list(disposition["reasonCodes"])
    state = disposition["domainState"]["state"]
    if state == "NONE":
        return "DISCHARGED", ["AGENT_WRITE_LIFECYCLE_NONE_AT_CLOSE"]
    if state == "RELEASED":
        return "DISCHARGED", ["AGENT_WRITE_LIFECYCLE_RELEASED_AT_CLOSE"]
    if state == "ACTIVE":
        return "OUTSTANDING", ["AGENT_WRITE_LIFECYCLE_ACTIVE_AT_CLOSE"]
    if state == "EXPIRED":
        return "OUTSTANDING", ["AGENT_WRITE_LIFECYCLE_EXPIRED_AT_CLOSE"]
    return "UNKNOWN", ["AGENT_WRITE_LIFECYCLE_UNKNOWN_AT_CLOSE"]


def _assess_obligation(
    obligation: dict[str, Any], disposition: dict[str, Any]
) -> dict[str, Any]:
    kind = obligation["kind"]
    if kind == "work-disposition":
        outcome, reasons = _classify_work(disposition)
    elif kind == "git-branch-disposition":
        outcome, reasons = _classify_git(disposition)
    elif kind == "write-lifecycle-disposition":
        outcome, reasons = _classify_lifecycle(disposition)
    else:
        raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_OBLIGATION_KIND_UNSUPPORTED")
    body = {
        "obligationHash": obligation["obligationHash"],
        "kind": kind,
        "locator": copy.deepcopy(obligation["locator"]),
        "observationStatus": disposition["observationStatus"],
        "outcome": outcome,
        "reasonCodes": _canonical_reasons(reasons),
        "domainState": copy.deepcopy(disposition["domainState"]),
        "dispositionHash": disposition["dispositionHash"],
    }
    return {**body, "assessmentHash": stable_hash(body)}


def _mutation_readback(closure: dict[str, Any]) -> dict[str, Any]:
    receipt = closure["receipt"]
    aggregate = receipt["aggregateReadback"]
    durable = receipt["delta"]["durableChanges"]
    return {
        "required": bool(durable),
        "status": aggregate["status"],
        "evidenceCount": aggregate["evidenceCount"],
        "coveredDurableChanges": copy.deepcopy(aggregate["coveredDurableChanges"]),
        "uncoveredDurableChanges": copy.deepcopy(aggregate["uncoveredDurableChanges"]),
        "readbackHash": aggregate["readbackHash"],
    }


def _status(
    *,
    closure_status: str,
    coverage: dict[str, Any],
    obligations: list[dict[str, Any]],
    mutation_readback: dict[str, Any],
) -> str:
    if (
        closure_status == "BLOCKED"
        or mutation_readback["uncoveredDurableChanges"]
        or any(item["outcome"] == "OUTSTANDING" for item in obligations)
    ):
        return "OUTSTANDING_OBLIGATIONS"
    if (
        closure_status == "UNKNOWN"
        or coverage.get("status") != "PASS"
        or mutation_readback["status"] != "PASS"
        or any(item["outcome"] == "UNKNOWN" for item in obligations)
    ):
        return "INSUFFICIENT_OBSERVATION"
    if any(item["outcome"] == "CARRIED_FORWARD" for item in obligations):
        return "CARRIED_FORWARD"
    return "CLEAN_TERMINATION"


def build_review(
    *,
    context: dict[str, Any],
    manifest: dict[str, Any],
    closure: dict[str, Any],
    resource_set: dict[str, Any],
    inventory: dict[str, Any],
    disposition_set: dict[str, Any],
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    # Lazy import keeps hosted_agent_cycle -> close review free of an import cycle.
    from tools import hosted_agent_cycle

    agent_cycle.validate_context(context)
    hosted_agent_cycle.validate_begin_manifest(manifest, context)
    agent_cycle_close.validate_closure(closure, context, evidence=evidence or [])
    agent_cycle_resources.validate_resource_set(resource_set)
    expected_work_ref = (
        context.get("workRef")
        if context.get("schemaVersion") == agent_cycle.SCHEMA_VERSION
        else None
    )
    agent_cycle_obligations.validate_inventory(
        inventory,
        resource_set,
        work_ref=expected_work_ref,
    )
    agent_cycle_obligations.validate_disposition_set(disposition_set, inventory)

    cycle_instance_id = manifest.get("cycleInstanceId")
    if not isinstance(cycle_instance_id, str):
        raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_CYCLE_INSTANCE_REQUIRED")
    if (
        manifest["cycleId"] != closure["cycleId"]
        or manifest["contextHash"] != closure["beforeContextHash"]
        or resource_set["cycleInstanceId"] != cycle_instance_id
        or inventory["cycleInstanceId"] != cycle_instance_id
        or disposition_set["cycleInstanceId"] != cycle_instance_id
    ):
        raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_BINDING_MISMATCH")

    obligations_by_hash = {
        item["obligationHash"]: item for item in inventory["obligations"]
    }
    disposition_by_hash = {
        item["obligationHash"]: item for item in disposition_set["dispositions"]
    }
    assessed = [
        _assess_obligation(obligations_by_hash[key], disposition_by_hash[key])
        for key in sorted(obligations_by_hash)
    ]
    mutation = _mutation_readback(closure)
    status = _status(
        closure_status=closure["status"],
        coverage=disposition_set["coverage"],
        obligations=assessed,
        mutation_readback=mutation,
    )

    reasons: list[str] = []
    if disposition_set["coverage"].get("status") != "PASS":
        reason = disposition_set["coverage"].get("reasonCode")
        if isinstance(reason, str) and reason:
            reasons.append(reason)
    reasons.extend(closure["receipt"].get("blockers") or [])
    for item in assessed:
        if item["outcome"] != "DISCHARGED":
            reasons.extend(item["reasonCodes"])

    summary = {
        "obligationCount": len(assessed),
        "dischargedCount": sum(item["outcome"] == "DISCHARGED" for item in assessed),
        "carriedForwardCount": sum(item["outcome"] == "CARRIED_FORWARD" for item in assessed),
        "outstandingCount": sum(item["outcome"] == "OUTSTANDING" for item in assessed),
        "unknownCount": sum(item["outcome"] == "UNKNOWN" for item in assessed),
        "handoffCount": sum(
            item["kind"] == "work-disposition"
            and item["domainState"].get("status") == "HANDOFF"
            for item in assessed
        ),
        "durableChangeCount": len(closure["receipt"]["delta"]["durableChanges"]),
        "uncoveredDurableChangeCount": len(mutation["uncoveredDurableChanges"]),
    }
    body = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": context["repository"],
        "cycleId": closure["cycleId"],
        "cycleInstanceId": cycle_instance_id,
        "contextHash": context["contextHash"],
        "closureHash": closure["closureHash"],
        "receiptHash": closure["receipt"]["receiptHash"],
        "resourceSetHash": resource_set["resourceSetHash"],
        "inventoryHash": inventory["inventoryHash"],
        "dispositionSetHash": disposition_set["dispositionSetHash"],
        "coverage": copy.deepcopy(disposition_set["coverage"]),
        "closureStatus": closure["status"],
        "mutationReadback": mutation,
        "obligations": assessed,
        "summary": summary,
        "status": status,
        "reasonCodes": _canonical_reasons(reasons),
        "cleanTerminationProven": status == "CLEAN_TERMINATION",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    value = {**body, "reviewHash": stable_hash(body)}
    validate_review(value)
    return value


def validate_review(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_FIELDS_INVALID")
    if value.get("schemaVersion") != SCHEMA_VERSION or value.get("repository") != REPOSITORY:
        raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_SCHEMA_INVALID")
    if value.get("status") not in STATUSES:
        raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_STATUS_INVALID")
    if (
        value.get("cleanTerminationProven") is not (value["status"] == "CLEAN_TERMINATION")
        or value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_AUTHORITY_INVALID")
    agent_cycle_resources.validate_coverage(value.get("coverage"))
    mutation = value.get("mutationReadback")
    if not isinstance(mutation, dict) or set(mutation) != MUTATION_READBACK_FIELDS:
        raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_MUTATION_READBACK_INVALID")
    obligations = value.get("obligations")
    if not isinstance(obligations, list):
        raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_OBLIGATIONS_INVALID")
    hashes: list[str] = []
    for item in obligations:
        if not isinstance(item, dict) or set(item) != OBLIGATION_FIELDS:
            raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_OBLIGATION_INVALID")
        if item.get("outcome") not in OUTCOMES:
            raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_OBLIGATION_INVALID")
        reasons = item.get("reasonCodes")
        if (
            not isinstance(reasons, list)
            or reasons != sorted(set(reasons))
            or any(not isinstance(reason, str) or not reason for reason in reasons)
        ):
            raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_OBLIGATION_INVALID")
        assessment_hash = item.get("assessmentHash")
        body = {key: copy.deepcopy(entry) for key, entry in item.items() if key != "assessmentHash"}
        if assessment_hash != stable_hash(body):
            raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_OBLIGATION_HASH_MISMATCH")
        hashes.append(item["obligationHash"])
    if hashes != sorted(hashes) or len(hashes) != len(set(hashes)):
        raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_OBLIGATIONS_NOT_CANONICAL")
    summary = value.get("summary")
    if not isinstance(summary, dict) or set(summary) != SUMMARY_FIELDS:
        raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_SUMMARY_INVALID")
    if any(not isinstance(item, int) or isinstance(item, bool) or item < 0 for item in summary.values()):
        raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_SUMMARY_INVALID")
    reasons = value.get("reasonCodes")
    if (
        not isinstance(reasons, list)
        or reasons != sorted(set(reasons))
        or any(not isinstance(item, str) or not item for item in reasons)
    ):
        raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_REASONS_INVALID")
    body = {key: copy.deepcopy(item) for key, item in value.items() if key != "reviewHash"}
    if value.get("reviewHash") != stable_hash(body):
        raise RuntimeError("AGENT_CYCLE_CLOSE_REVIEW_HASH_MISMATCH")
    return value


def review_from_files(
    *,
    context_path: str,
    manifest_path: str,
    closure_path: str,
    resource_path: str,
    inventory_path: str,
    disposition_path: str,
    evidence_paths: list[str] | None = None,
) -> dict[str, Any]:
    return build_review(
        context=_load_json(context_path),
        manifest=_load_json(manifest_path),
        closure=_load_json(closure_path),
        resource_set=_load_json(resource_path),
        inventory=_load_json(inventory_path),
        disposition_set=_load_json(disposition_path),
        evidence=agent_cycle_close.load_evidence(evidence_paths),
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="agent close-review")
    parser.add_argument("--context", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--closure", required=True)
    parser.add_argument("--resources", required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--dispositions", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        value = review_from_files(
            context_path=args.context,
            manifest_path=args.manifest,
            closure_path=args.closure,
            resource_path=args.resources,
            inventory_path=args.inventory,
            disposition_path=args.dispositions,
            evidence_paths=args.evidence,
        )
        if args.output:
            Path(args.output).write_text(
                json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        if args.as_json:
            print(json.dumps(value, indent=2, ensure_ascii=False))
        else:
            summary = value["summary"]
            print(
                "AGENT CYCLE CLOSE REVIEW\n"
                f"  status: {value['status']}\n"
                f"  clean-termination-proven: {str(value['cleanTerminationProven']).lower()}\n"
                f"  obligations: {summary['obligationCount']}\n"
                f"  carried-forward: {summary['carriedForwardCount']}\n"
                f"  outstanding: {summary['outstandingCount']}\n"
                f"  unknown: {summary['unknownCount']}\n"
                f"  review: {value['reviewHash']}"
            )
        return 0
    except RuntimeError as exc:
        payload = {"ok": False, "error": str(exc)}
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"BLOCKED\n{exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
