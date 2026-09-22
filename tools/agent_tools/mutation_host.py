from __future__ import annotations

import copy
import re
from typing import Any, Callable

from tools import git_observation
from tools import remote_canonical_execution as remote
from tools.agent_commands import agent_owned_git
from tools.agent_tools import admission, contracts, guard_proofs, resolver
from tools.canonical import stable_hash

OUTCOME_SCHEMA = "AgentToolGovernedMutationHostOutcome 0.1"
DIRECT_HOST_ID = "agent-tool-mutation-host"
MUTABLE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")


class GovernedMutationHostError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _code(exc: BaseException) -> str:
    value = getattr(exc, "code", None)
    if isinstance(value, str) and value:
        return value
    text = str(exc)
    return text.split(":", 1)[0] if text else exc.__class__.__name__


class MutationTrackingTransport:
    def __init__(self, transport: Any) -> None:
        self.transport = transport
        self.mutable_calls: list[dict[str, str]] = []

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        payload: Any = None,
        include_headers: bool = False,
    ) -> Any:
        method = method.upper()
        if method in MUTABLE_METHODS:
            self.mutable_calls.append({"method": method, "endpoint": endpoint})
        return self.transport.request(
            method,
            endpoint,
            payload=payload,
            include_headers=include_headers,
        )


def observe_branch_head(plan: dict[str, Any], transport: Any) -> str | None:
    try:
        if "path" in plan["target"]:
            observed = git_observation.observe_file(
                plan["target"]["branch"],
                plan["target"]["path"],
                transport=transport,
            )
        else:
            observed = git_observation.observe_branch(
                plan["target"]["branch"],
                transport=transport,
            )
    except Exception:
        return None
    value = observed.get("branchHead") if isinstance(observed, dict) else None
    return value if isinstance(value, str) else None


def _command_from_plan(plan: dict[str, Any]) -> dict[str, Any]:
    contracts.validate_plan(plan)
    if (
        plan["effectClass"] != admission.MUTATION_EFFECT
        or plan["mode"] != "mutation-execute"
        or plan["status"] != "READY"
        or plan["toolId"] != "git.files.mutate"
        or plan["actor"].get("role") != "manager-gitops"
    ):
        raise GovernedMutationHostError("AGENT_TOOL_MUTATION_HOST_PLAN_UNSUPPORTED")
    concrete = plan.get("concrete")
    if (
        not isinstance(concrete, dict)
        or concrete.get("kind") != "remote-canonical-command"
    ):
        raise GovernedMutationHostError("AGENT_TOOL_MUTATION_HOST_COMMAND_REQUIRED")
    command = remote.validate_command(concrete.get("command"))
    if concrete.get("commandHash") != remote.command_hash(command):
        raise GovernedMutationHostError(
            "AGENT_TOOL_MUTATION_HOST_COMMAND_HASH_MISMATCH"
        )
    if (
        command["kind"] != "git-direct"
        or command["target"].get("operation") != "mutate-files"
        or command["target"].get("branch") != plan["target"].get("branch")
    ):
        raise GovernedMutationHostError(
            "AGENT_TOOL_MUTATION_HOST_COMMAND_MISMATCH"
        )
    return command


def validate_outcome(
    value: Any,
    *,
    plan: dict[str, Any],
) -> dict[str, Any]:
    fields = {
        "schemaVersion",
        "requestHash",
        "planHash",
        "commandHash",
        "source",
        "status",
        "blockers",
        "executionProofSet",
        "remoteReceipt",
        "mutableCallCount",
        "observedBranchHead",
        "readOnly",
        "semanticAuthority",
        "authorizesMutation",
        "outcomeHash",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise GovernedMutationHostError("AGENT_TOOL_MUTATION_HOST_OUTCOME_INVALID")
    if value.get("schemaVersion") != OUTCOME_SCHEMA:
        raise GovernedMutationHostError("AGENT_TOOL_MUTATION_HOST_OUTCOME_INVALID")
    command = _command_from_plan(plan)
    if (
        value.get("requestHash") != plan["requestHash"]
        or value.get("planHash") != plan["planHash"]
        or value.get("commandHash") != remote.command_hash(command)
    ):
        raise GovernedMutationHostError(
            "AGENT_TOOL_MUTATION_HOST_OUTCOME_LINEAGE_MISMATCH"
        )
    remote.validate_execution_source(value.get("source"))
    status = value.get("status")
    blockers = value.get("blockers")
    if (
        status not in {"PASS", "BLOCKED", "UNKNOWN"}
        or not isinstance(blockers, list)
        or blockers != sorted(set(blockers))
        or any(not isinstance(item, str) or not item for item in blockers)
    ):
        raise GovernedMutationHostError("AGENT_TOOL_MUTATION_HOST_OUTCOME_INVALID")
    mutable_count = value.get("mutableCallCount")
    if (
        not isinstance(mutable_count, int)
        or isinstance(mutable_count, bool)
        or mutable_count < 0
    ):
        raise GovernedMutationHostError("AGENT_TOOL_MUTATION_HOST_OUTCOME_INVALID")
    observed_head = value.get("observedBranchHead")
    if observed_head is not None and (
        not isinstance(observed_head, str) or _SHA_RE.fullmatch(observed_head) is None
    ):
        raise GovernedMutationHostError("AGENT_TOOL_MUTATION_HOST_OUTCOME_INVALID")
    proof_set = value.get("executionProofSet")
    receipt = value.get("remoteReceipt")
    if proof_set is not None:
        guard_proofs.validate_proof_set(proof_set, plan=plan)
    if receipt is not None:
        remote.validate_receipt(receipt)
        if (
            receipt["command"] != command
            or receipt["commandHash"] != remote.command_hash(command)
        ):
            raise GovernedMutationHostError(
                "AGENT_TOOL_MUTATION_HOST_RECEIPT_MISMATCH"
            )
    if status == "PASS":
        if blockers or proof_set is None or receipt is None or mutable_count <= 0:
            raise GovernedMutationHostError(
                "AGENT_TOOL_MUTATION_HOST_PASS_INVALID"
            )
    else:
        if not blockers or receipt is not None:
            raise GovernedMutationHostError(
                "AGENT_TOOL_MUTATION_HOST_FAILURE_INVALID"
            )
    if (
        value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise GovernedMutationHostError("AGENT_TOOL_MUTATION_HOST_OUTCOME_INVALID")
    core = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "outcomeHash"
    }
    if value.get("outcomeHash") != stable_hash(core):
        raise GovernedMutationHostError(
            "AGENT_TOOL_MUTATION_HOST_OUTCOME_HASH_MISMATCH"
        )
    return value


def _build_outcome(
    plan: dict[str, Any],
    *,
    source: dict[str, Any],
    status: str,
    blockers: list[str],
    execution_proof_set: dict[str, Any] | None,
    remote_receipt: dict[str, Any] | None,
    mutable_call_count: int,
    observed_branch_head: str | None,
) -> dict[str, Any]:
    command = _command_from_plan(plan)
    source_value = remote.validate_execution_source(source)
    core = {
        "schemaVersion": OUTCOME_SCHEMA,
        "requestHash": plan["requestHash"],
        "planHash": plan["planHash"],
        "commandHash": remote.command_hash(command),
        "source": copy.deepcopy(source_value),
        "status": status,
        "blockers": sorted(set(blockers)),
        "executionProofSet": copy.deepcopy(execution_proof_set),
        "remoteReceipt": copy.deepcopy(remote_receipt),
        "mutableCallCount": mutable_call_count,
        "observedBranchHead": observed_branch_head,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    value = {**core, "outcomeHash": stable_hash(core)}
    return validate_outcome(value, plan=plan)


def execute_plan(
    plan: dict[str, Any],
    *,
    source: dict[str, Any],
    transport: Any | None = None,
    authority_factory: Callable[[Any], Any] | None = None,
    lifecycle_context: dict[str, Any] | None = None,
    lifecycle_result_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if transport is None:
        raise GovernedMutationHostError("BLOCKED_EXECUTION_SURFACE")
    command = _command_from_plan(plan)
    source_value = remote.validate_execution_source(source)
    tracked = MutationTrackingTransport(transport)
    execution_proofs: dict[str, Any] | None = None
    try:
        execution_proofs = admission.collect_guard_proofs(
            plan,
            transport=tracked,
            authority_factory=authority_factory,
            lifecycle_context=lifecycle_context,
            lifecycle_result_context=lifecycle_result_context,
        )
        admission.assert_execution_admitted(plan, execution_proofs)
        receipt = agent_owned_git.execute_agent_owned_git(
            command,
            source=source_value,
            transport=tracked,
            authority_factory=authority_factory,
        )
        remote.validate_receipt(receipt)
        observed_head = receipt["aggregateReadback"].get("branchHead")
        return _build_outcome(
            plan,
            source=source_value,
            status="PASS",
            blockers=[],
            execution_proof_set=execution_proofs,
            remote_receipt=receipt,
            mutable_call_count=len(tracked.mutable_calls),
            observed_branch_head=observed_head,
        )
    except Exception as exc:
        observed_head = observe_branch_head(plan, tracked)
        expected_head = command["expected"].get("branchHead")
        if not tracked.mutable_calls or observed_head == expected_head:
            status = "BLOCKED"
        else:
            status = "UNKNOWN"
        return _build_outcome(
            plan,
            source=source_value,
            status=status,
            blockers=[_code(exc)],
            execution_proof_set=execution_proofs,
            remote_receipt=None,
            mutable_call_count=len(tracked.mutable_calls),
            observed_branch_head=observed_head,
        )


def _agent_tool_result(
    plan: dict[str, Any],
    outcome: dict[str, Any],
) -> dict[str, Any]:
    outcome = validate_outcome(outcome, plan=plan)
    core = {
        "schemaVersion": contracts.RESULT_SCHEMA,
        "requestHash": plan["requestHash"],
        "planHash": plan["planHash"],
        "toolId": plan["toolId"],
        "status": outcome["status"],
        "value": copy.deepcopy(outcome),
        "blockers": copy.deepcopy(outcome["blockers"]),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    value = {**core, "resultHash": stable_hash(core)}
    return contracts.validate_result(value)


def execute_request(
    request: dict[str, Any],
    context: dict[str, Any],
    *,
    cycle_instance_id: str,
    lifecycle_result: dict[str, Any],
    lifecycle_result_ref: dict[str, str],
    invocation_id: str,
    transport: Any | None = None,
    authority_factory: Callable[[Any], Any] | None = None,
    policy: dict[str, Any] | None = None,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if transport is None:
        raise GovernedMutationHostError("BLOCKED_EXECUTION_SURFACE")
    resolved = resolver.resolve_request(
        request,
        context,
        policy=policy,
        registry=registry,
        transport=transport,
        execute=False,
    )
    plan = resolved["plan"]
    _command_from_plan(plan)
    source = remote.build_execution_source(
        kind="agent-tool-host",
        host=DIRECT_HOST_ID,
        source_sha=plan["begin"]["sourceSha"],
        invocation_id=invocation_id,
        ref={
            "kind": "agent-tool-request",
            "value": plan["requestHash"],
        },
    )
    outcome = execute_plan(
        plan,
        source=source,
        transport=transport,
        authority_factory=authority_factory,
        lifecycle_result_context={
            "cycleInstanceId": cycle_instance_id,
            "lifecycleResult": copy.deepcopy(lifecycle_result),
            "lifecycleResultRef": copy.deepcopy(lifecycle_result_ref),
        },
    )
    return {
        "plan": plan,
        "result": _agent_tool_result(plan, outcome),
    }
