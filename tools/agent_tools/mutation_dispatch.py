from __future__ import annotations

import copy
import re
from typing import Any

from tools import remote_canonical_execution as remote
from tools.agent_tools import contracts, guard_proofs
from tools.canonical import stable_hash

DISPATCH_SCHEMA = "AgentToolMutationDispatch 0.1"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
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


def _positive_int(value: Any, code: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
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
