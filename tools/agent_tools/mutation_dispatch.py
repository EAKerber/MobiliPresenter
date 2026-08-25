from __future__ import annotations

import copy
import re
from typing import Any

from tools import remote_canonical_execution as remote
from tools.agent_tools import contracts, guard_proofs
from tools.canonical import stable_hash

DISPATCH_SCHEMA = "AgentToolMutationDispatch 0.1"
OUTCOME_KIND = "agent-tool-mutation-dispatch-outcome"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
CYCLE_RE = re.compile(r"^cycle-instance-[0-9a-f]{24}$")
FIELDS = {
    "schemaVersion",
    "cycleInstanceId",
    "requestHash",
    "planHash",
    "proofSetHash",
    "begin",
    "actor",
    "toolId",
    "targetPolicy",
    "command",
    "commandHash",
    "source",
    "semanticAuthority",
    "authorizesMutation",
    "dispatchHash",
}
SOURCE_FIELDS = {"issueNumber", "requestCommentId", "hostedRunId", "semanticHostSha"}
OUTCOME_FIELDS = {
    "kind",
    "admissionProofSetHash",
    "dispatchHash",
    "commandHash",
    "executionProofSetHash",
    "remoteReceiptHash",
    "remoteReceipt",
    "aggregateReadback",
    "mutationState",
    "mutableCallCount",
    "observedBranchHead",
}


def _positive_int(value: Any, code: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise RuntimeError(code)
    return value


def _nonnegative_int(value: Any, code: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RuntimeError(code)
    return value


def _hash(value: Any, code: str) -> str:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        raise RuntimeError(code)
    return value


def _source(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != SOURCE_FIELDS:
        raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_SOURCE_INVALID")
    result = {
        "issueNumber": _positive_int(value.get("issueNumber"), "AGENT_TOOL_MUTATION_DISPATCH_SOURCE_INVALID"),
        "requestCommentId": _positive_int(value.get("requestCommentId"), "AGENT_TOOL_MUTATION_DISPATCH_SOURCE_INVALID"),
        "hostedRunId": _positive_int(value.get("hostedRunId"), "AGENT_TOOL_MUTATION_DISPATCH_SOURCE_INVALID"),
        "semanticHostSha": value.get("semanticHostSha"),
    }
    if not isinstance(result["semanticHostSha"], str) or not re.fullmatch(r"[0-9a-f]{40}", result["semanticHostSha"]):
        raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_SOURCE_INVALID")
    return result


def validate_dispatch(
    value: Any,
    *,
    plan: dict[str, Any] | None = None,
    proof_set: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_FIELDS_INVALID")
    if value.get("schemaVersion") != DISPATCH_SCHEMA:
        raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_SCHEMA_UNSUPPORTED")
    if not isinstance(value.get("cycleInstanceId"), str) or not CYCLE_RE.fullmatch(value["cycleInstanceId"]):
        raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_CYCLE_INVALID")
    for field in ("requestHash", "planHash", "proofSetHash", "commandHash", "dispatchHash"):
        _hash(value.get(field), "AGENT_TOOL_MUTATION_DISPATCH_HASH_INVALID")
    contracts._begin(value.get("begin"))
    contracts._actor(value.get("actor"))
    if not isinstance(value.get("toolId"), str) or not value["toolId"]:
        raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_TOOL_INVALID")
    if not isinstance(value.get("targetPolicy"), str) or not value["targetPolicy"]:
        raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_TARGET_POLICY_INVALID")
    source = _source(value.get("source"))
    command = remote.validate_command(value.get("command"))
    if value["commandHash"] != remote.command_hash(command):
        raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_COMMAND_HASH_MISMATCH")
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_MUST_NOT_AUTHORIZE")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "dispatchHash"}
    if value["dispatchHash"] != stable_hash(core):
        raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_HASH_MISMATCH")

    if plan is not None:
        contracts.validate_plan(plan)
        if plan["effectClass"] != "shared-durable-mutation" or plan["mode"] != "mutation-execute" or plan["status"] != "READY":
            raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_PLAN_NOT_EXECUTABLE")
        if plan["actor"].get("role") != "manager-gitops":
            raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_ROLE_FORBIDDEN")
        concrete = plan.get("concrete")
        if not isinstance(concrete, dict) or concrete.get("kind") != "remote-canonical-command":
            raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_COMMAND_REQUIRED")
        if (
            value["requestHash"] != plan["requestHash"]
            or value["planHash"] != plan["planHash"]
            or value["begin"] != plan["begin"]
            or value["actor"] != plan["actor"]
            or value["toolId"] != plan["toolId"]
            or value["targetPolicy"] != plan["targetPolicy"]
            or value["command"] != concrete.get("command")
            or value["commandHash"] != concrete.get("commandHash")
            or source["semanticHostSha"] != plan["begin"]["sourceSha"]
        ):
            raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_PLAN_MISMATCH")
        target = command["target"]
        if target.get("branch") != plan["target"].get("branch") or target.get("path") != plan["target"].get("path"):
            raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_PLAN_MISMATCH")

    if proof_set is not None:
        if plan is None:
            raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_PLAN_REQUIRED")
        guard_proofs.validate_proof_set(proof_set, plan=plan)
        if value["proofSetHash"] != proof_set["proofSetHash"]:
            raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_PROOF_MISMATCH")
    return value


def build_dispatch(
    plan: dict[str, Any],
    proof_set: dict[str, Any],
    *,
    cycle_instance_id: str,
    issue_number: int,
    request_comment_id: int,
    hosted_run_id: int,
) -> dict[str, Any]:
    contracts.validate_plan(plan)
    guard_proofs.validate_proof_set(proof_set, plan=plan)
    concrete = plan.get("concrete")
    if not isinstance(concrete, dict):
        raise RuntimeError("AGENT_TOOL_MUTATION_DISPATCH_COMMAND_REQUIRED")
    core = {
        "schemaVersion": DISPATCH_SCHEMA,
        "cycleInstanceId": cycle_instance_id,
        "requestHash": plan["requestHash"],
        "planHash": plan["planHash"],
        "proofSetHash": proof_set["proofSetHash"],
        "begin": copy.deepcopy(plan["begin"]),
        "actor": copy.deepcopy(plan["actor"]),
        "toolId": plan["toolId"],
        "targetPolicy": plan["targetPolicy"],
        "command": copy.deepcopy(concrete.get("command")),
        "commandHash": concrete.get("commandHash"),
        "source": {
            "issueNumber": issue_number,
            "requestCommentId": request_comment_id,
            "hostedRunId": hosted_run_id,
            "semanticHostSha": plan["begin"]["sourceSha"],
        },
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    value = {**core, "dispatchHash": stable_hash(core)}
    return validate_dispatch(value, plan=plan, proof_set=proof_set)


def validate_execution_result(
    value: Any,
    *,
    plan: dict[str, Any],
    dispatch: dict[str, Any],
) -> dict[str, Any]:
    contracts.validate_plan(plan)
    validate_dispatch(dispatch, plan=plan)
    contracts.validate_result(value)
    if (
        value["requestHash"] != dispatch["requestHash"]
        or value["planHash"] != dispatch["planHash"]
        or value["toolId"] != dispatch["toolId"]
    ):
        raise RuntimeError("AGENT_TOOL_MUTATION_RESULT_LINEAGE_MISMATCH")
    outcome = value.get("value")
    if not isinstance(outcome, dict) or set(outcome) != OUTCOME_FIELDS:
        raise RuntimeError("AGENT_TOOL_MUTATION_RESULT_VALUE_INVALID")
    if outcome.get("kind") != OUTCOME_KIND:
        raise RuntimeError("AGENT_TOOL_MUTATION_RESULT_VALUE_INVALID")
    for field, expected in (
        ("admissionProofSetHash", dispatch["proofSetHash"]),
        ("dispatchHash", dispatch["dispatchHash"]),
        ("commandHash", dispatch["commandHash"]),
    ):
        if outcome.get(field) != expected:
            raise RuntimeError("AGENT_TOOL_MUTATION_RESULT_LINEAGE_MISMATCH")
    execution_hash = outcome.get("executionProofSetHash")
    if execution_hash is not None:
        _hash(execution_hash, "AGENT_TOOL_MUTATION_RESULT_EXECUTION_PROOF_INVALID")
    receipt_hash = outcome.get("remoteReceiptHash")
    if receipt_hash is not None:
        _hash(receipt_hash, "AGENT_TOOL_MUTATION_RESULT_RECEIPT_INVALID")
    receipt_value = outcome.get("remoteReceipt")
    if receipt_value is not None:
        remote.validate_receipt(receipt_value)
        if (
            receipt_value["commandHash"] != dispatch["commandHash"]
            or receipt_value["command"] != dispatch["command"]
            or receipt_value["receiptHash"] != receipt_hash
        ):
            raise RuntimeError("AGENT_TOOL_MUTATION_RESULT_RECEIPT_MISMATCH")
    mutable_count = _nonnegative_int(
        outcome.get("mutableCallCount"), "AGENT_TOOL_MUTATION_RESULT_MUTABLE_COUNT_INVALID"
    )
    observed_head = outcome.get("observedBranchHead")
    if observed_head is not None and (
        not isinstance(observed_head, str) or not GIT_SHA_RE.fullmatch(observed_head)
    ):
        raise RuntimeError("AGENT_TOOL_MUTATION_RESULT_BRANCH_HEAD_INVALID")
    status = value["status"]
    mutation_state = outcome.get("mutationState")
    if status == "PASS":
        if (
            value["blockers"]
            or mutation_state != "APPLIED"
            or receipt_hash is None
            or receipt_value is None
            or execution_hash is None
            or mutable_count <= 0
            or not isinstance(outcome.get("aggregateReadback"), dict)
        ):
            raise RuntimeError("AGENT_TOOL_MUTATION_RESULT_PASS_INVALID")
        if outcome["aggregateReadback"] != receipt_value["aggregateReadback"]:
            raise RuntimeError("AGENT_TOOL_MUTATION_RESULT_RECEIPT_MISMATCH")
    elif status == "BLOCKED":
        if (
            not value["blockers"]
            or mutation_state != "NOT_APPLIED"
            or receipt_hash is not None
            or receipt_value is not None
            or outcome.get("aggregateReadback") is not None
        ):
            raise RuntimeError("AGENT_TOOL_MUTATION_RESULT_BLOCKED_INVALID")
    elif status == "UNKNOWN":
        if (
            not value["blockers"]
            or mutation_state != "UNKNOWN"
            or receipt_hash is not None
            or receipt_value is not None
            or outcome.get("aggregateReadback") is not None
        ):
            raise RuntimeError("AGENT_TOOL_MUTATION_RESULT_UNKNOWN_INVALID")
    else:
        raise RuntimeError("AGENT_TOOL_MUTATION_RESULT_STATUS_INVALID")
    return value


def build_execution_result(
    plan: dict[str, Any],
    dispatch: dict[str, Any],
    *,
    status: str,
    blockers: list[str],
    execution_proof_set: dict[str, Any] | None = None,
    receipt: dict[str, Any] | None = None,
    mutable_call_count: int = 0,
    observed_branch_head: str | None = None,
) -> dict[str, Any]:
    contracts.validate_plan(plan)
    validate_dispatch(dispatch, plan=plan)
    blockers = sorted(set(blockers))
    execution_hash: str | None = None
    if execution_proof_set is not None:
        guard_proofs.validate_proof_set(execution_proof_set, plan=plan)
        execution_hash = execution_proof_set["proofSetHash"]
    receipt_hash: str | None = None
    aggregate: dict[str, Any] | None = None
    receipt_value: dict[str, Any] | None = None
    if receipt is not None:
        remote.validate_receipt(receipt)
        if (
            receipt["commandHash"] != dispatch["commandHash"]
            or receipt["command"] != dispatch["command"]
        ):
            raise RuntimeError("AGENT_TOOL_MUTATION_RESULT_RECEIPT_MISMATCH")
        receipt_hash = receipt["receiptHash"]
        receipt_value = copy.deepcopy(receipt)
        aggregate = copy.deepcopy(receipt["aggregateReadback"])
    if status == "PASS":
        mutation_state = "APPLIED"
    elif status == "BLOCKED":
        mutation_state = "NOT_APPLIED"
    elif status == "UNKNOWN":
        mutation_state = "UNKNOWN"
    else:
        raise RuntimeError("AGENT_TOOL_MUTATION_RESULT_STATUS_INVALID")
    outcome = {
        "kind": OUTCOME_KIND,
        "admissionProofSetHash": dispatch["proofSetHash"],
        "dispatchHash": dispatch["dispatchHash"],
        "commandHash": dispatch["commandHash"],
        "executionProofSetHash": execution_hash,
        "remoteReceiptHash": receipt_hash,
        "remoteReceipt": receipt_value,
        "aggregateReadback": aggregate,
        "mutationState": mutation_state,
        "mutableCallCount": _nonnegative_int(
            mutable_call_count, "AGENT_TOOL_MUTATION_RESULT_MUTABLE_COUNT_INVALID"
        ),
        "observedBranchHead": observed_branch_head,
    }
    core = {
        "schemaVersion": contracts.RESULT_SCHEMA,
        "requestHash": dispatch["requestHash"],
        "planHash": dispatch["planHash"],
        "toolId": dispatch["toolId"],
        "status": status,
        "value": outcome,
        "blockers": blockers,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    result = {**core, "resultHash": stable_hash(core)}
    return validate_execution_result(result, plan=plan, dispatch=dispatch)


def remote_receipt_from_execution_result(value: dict[str, Any]) -> dict[str, Any] | None:
    contracts.validate_result(value)
    outcome = value.get("value")
    if not isinstance(outcome, dict) or outcome.get("kind") != OUTCOME_KIND:
        return None
    receipt = outcome.get("remoteReceipt")
    if receipt is None:
        return None
    remote.validate_receipt(receipt)
    if value["status"] != "PASS" or outcome.get("remoteReceiptHash") != receipt["receiptHash"]:
        raise RuntimeError("AGENT_TOOL_MUTATION_RESULT_RECEIPT_INVALID")
    return receipt
